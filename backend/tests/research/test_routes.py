from copy import deepcopy
import uuid

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.ai.contracts import ProviderError
from app.ai.models import AIOperation
from app.application import create_application
import app.application_state as application_state_module
from app.auth.dependencies import get_session
from app.research.models import ResearchNode
from app.research.retrieval import ResearchEvidence
from app.research.service import ResearchServiceError


def _register(client: TestClient, email: str, username: str) -> dict[str, str]:
    tokens = client.post('/api/v1/auth/register', json={
        'email': email,
        'username': username,
        'password': 'correct-horse-battery-staple',
    }).json()
    return {'Authorization': f"Bearer {tokens['access_token']}"}


def _seed_genesis(app) -> None:
    with app.state.database_engine.begin() as connection:
        connection.execute(text('''
            CREATE TABLE biblical_texts (
                id INTEGER PRIMARY KEY, book TEXT, chapter INTEGER,
                verse INTEGER, text TEXT, translation TEXT
            )
        '''))
        connection.execute(text('''
            INSERT INTO biblical_texts
                (id, book, chapter, verse, text, translation)
            VALUES (1, 'Genesis', 4, 1, 'Eve bore Cain.', 'KJV')
        '''))


def _seed_eden_to_abel(app) -> list[int]:
    rows = []
    row_id = 1
    for chapter, verses in (
        (2, range(8, 26)),
        (3, range(22, 25)),
        (4, range(1, 6)),
        (4, range(8, 9)),
    ):
        for verse in verses:
            rows.append({
                'id': row_id,
                'book': 'Genesis',
                'chapter': chapter,
                'verse': verse,
                'text': f'KJV Genesis {chapter}:{verse}',
                'translation': 'KJV',
            })
            row_id += 1
    rows.extend([
        {
            'id': 100,
            'book': 'Luke',
            'chapter': 3,
            'verse': 38,
            'text': 'Adam lexical distraction',
            'translation': 'KJV',
        },
        {
            'id': 101,
            'book': '1 Chronicles',
            'chapter': 1,
            'verse': 1,
            'text': 'Adam lexical distraction',
            'translation': 'KJV',
        },
    ])
    with app.state.database_engine.begin() as connection:
        connection.execute(text('''
            CREATE TABLE biblical_texts (
                id INTEGER PRIMARY KEY, book TEXT, chapter INTEGER,
                verse INTEGER, text TEXT, translation TEXT
            )
        '''))
        connection.execute(text('''
            INSERT INTO biblical_texts
                (id, book, chapter, verse, text, translation)
            VALUES (:id, :book, :chapter, :verse, :text, :translation)
        '''), rows)
    return [row['id'] for row in rows if row['id'] < 100]


def test_query_endpoint_is_mounted_returns_defaults_and_commits_audit(test_settings):
    app = create_application(test_settings)
    with TestClient(app) as client:
        response = client.post(
            '/api/v1/research/query',
            json={'question': 'What is not in the library?'},
        )

    assert response.status_code == 200
    data = response.json()
    assert data['settings'] == {
        'source_scopes': ['biblical-canon'],
        'depth': 'deep-research',
        'mode_parameters': {},
    }
    assert data['grounding_status'] == 'insufficient'
    assert data['trail_node'] is None
    with app.state.session_factory() as session:
        assert session.scalar(select(AIOperation)) is not None
        assert session.scalar(select(ResearchNode)) is None


def test_between_event_query_returns_only_complete_verified_interval(
    test_settings, monkeypatch,
):
    class OfflineProvider:
        name = 'offline'

        async def complete(self, _messages):
            raise ProviderError('private provider detail')

    monkeypatch.setattr(
        'app.research.router.create_chat_provider', lambda *_args: OfflineProvider()
    )
    app = create_application(test_settings)
    expected_ids = _seed_eden_to_abel(app)
    with TestClient(app) as client:
        response = client.post('/api/v1/research/query', json={
            'question': 'What happened between Eden and Abel?',
            'mode': 'what-happened-between',
            'source_scopes': ['biblical-canon', 'ancient-sources'],
            'depth': 'deep-research',
            'mode_parameters': {
                'from_event_id': 'eden',
                'to_event_id': 'abel-killed',
            },
        })

    assert response.status_code == 200
    data = response.json()
    assert data['grounding_status'] == 'evidence-only'
    assert [source['id'] for source in data['sources']] == [
        f'scripture:{row_id}' for row_id in expected_ids
    ]
    assert len(data['sources']) == 27
    assert {source['source_type'] for source in data['sources']} == {
        'canonical-scripture'
    }
    assert all(source['reference'].startswith('Genesis ') for source in data['sources'])


def test_between_event_query_rejects_invalid_or_missing_ranges_honestly(
    test_settings,
):
    app = create_application(test_settings)
    _seed_eden_to_abel(app)
    with TestClient(app) as client:
        reversed_response = client.post('/api/v1/research/query', json={
            'question': 'What happened between Abel and Eden?',
            'mode': 'what-happened-between',
            'mode_parameters': {
                'from_event_id': 'abel-killed',
                'to_event_id': 'eden',
            },
        })
        missing_response = client.post('/api/v1/research/query', json={
            'question': 'What happened between these events?',
            'mode': 'what-happened-between',
            'mode_parameters': {},
        })
        unknown_response = client.post('/api/v1/research/query', json={
            'question': 'What happened between unknown events?',
            'mode': 'what-happened-between',
            'mode_parameters': {
                'from_event_id': 'not-in-the-reviewed-catalog',
                'to_event_id': 'abel-killed',
            },
        })

    for response in (reversed_response, missing_response, unknown_response):
        assert response.status_code == 200
        assert response.json()['grounding_status'] == 'insufficient'
        assert response.json()['sources'] == []


def test_authenticated_query_creates_owned_root_child_and_trail(test_settings):
    app = create_application(test_settings)
    with TestClient(app) as client:
        owner = _register(client, 'owner@example.com', 'owner')
        stranger = _register(client, 'stranger@example.com', 'stranger')
        root = client.post(
            '/api/v1/research/query', headers=owner,
            json={'question': 'Who was Abel?'},
        )
        assert root.status_code == 200
        root_node = root.json()['trail_node']
        assert root_node['parent_node_id'] is None

        child = client.post(
            '/api/v1/research/query', headers=owner,
            json={
                'question': 'What happened next?',
                'parent_node_id': root_node['id'],
            },
        )
        assert child.status_code == 200
        child_node = child.json()['trail_node']
        assert child_node['parent_node_id'] == root_node['id']

        trail = client.get(
            f"/api/v1/research/trail/{root_node['id']}", headers=owner
        )
        assert trail.status_code == 200
        assert trail.json()['active']['id'] == root_node['id']
        assert trail.json()['ancestry'] == []
        assert [item['id'] for item in trail.json()['children']] == [child_node['id']]
        assert trail.json()['children_truncated'] is False
        assert client.get(
            f"/api/v1/research/trail/{root_node['id']}", headers=stranger
        ).status_code == 404
        assert client.post(
            '/api/v1/research/query', headers=stranger,
            json={'question': 'Compare it', 'parent_node_id': root_node['id']},
        ).status_code == 404


def test_guest_parent_is_rejected_without_creating_node(test_settings):
    app = create_application(test_settings)
    with TestClient(app) as client:
        response = client.post('/api/v1/research/query', json={
            'question': 'Continue the private trail',
            'parent_node_id': str(uuid.uuid4()),
        })

    assert response.status_code in {400, 422}
    with app.state.session_factory() as session:
        assert session.scalar(select(ResearchNode)) is None


def test_guest_query_accepts_bounded_context_without_creating_server_parent(
    test_settings,
):
    app = create_application(test_settings)
    with TestClient(app) as client:
        response = client.post('/api/v1/research/query', json={
            'question': 'What happened next?',
            'conversation_context': {
                'entity_names': ['Cain', 'Eden'],
                'source_references': ['Genesis 3–4'],
            },
        })

    assert response.status_code == 200
    assert response.json()['trail_node'] is None
    with app.state.session_factory() as session:
        assert session.scalar(select(ResearchNode)) is None


def test_events_returns_only_resolved_safe_fields_and_maps_errors(
    test_settings, monkeypatch,
):
    app = create_application(test_settings)
    _seed_genesis(app)
    with TestClient(app) as client:
        response = client.get('/api/v1/research/events', params={'q': "Cain's birth"})
        assert response.status_code == 200
        event = response.json()['events'][0]
        assert set(event) == {
            'id', 'title', 'description', 'reference', 'source_ids', 'people',
            'places', 'ordering_group', 'ordinal',
        }
        assert event['source_ids'] == ['scripture:1']
        assert event['ordering_group'] == 'eden-sequence'
        assert event['ordinal'] == 3
        assert client.get(
            '/api/v1/research/events', params={'q': 'x' * 257}
        ).status_code == 422

    from app.research.event_catalog import EventCatalogError

    def unavailable(*_args, **_kwargs):
        raise EventCatalogError('catalog_unavailable', 'unavailable')

    monkeypatch.setattr('app.research.router.list_events', unavailable)
    with TestClient(app) as client:
        assert client.get('/api/v1/research/events').status_code == 503


def test_research_query_keeps_existing_ai_rate_limit(test_settings):
    test_settings.ai_rate_limit = 1
    app = create_application(test_settings)
    with TestClient(app) as client:
        payload = {'question': 'Where is the evidence?'}
        assert client.post('/api/v1/research/query', json=payload).status_code == 200
        assert client.post('/api/v1/research/query', json=payload).status_code == 429


def test_provider_failure_still_atomically_audits_and_persists_authenticated_node(
    test_settings, monkeypatch,
):
    class OfflineProvider:
        name = 'offline'

        async def complete(self, _messages):
            raise ProviderError('private provider detail')

    evidence = ResearchEvidence(
        id='scripture:1', title='Genesis', reference='Genesis 4:1',
        text='Eve bore Cain.', source_type='canonical-scripture',
        tradition='Protestant', translation='KJV',
    )
    monkeypatch.setattr(
        'app.research.router.retrieve_research_evidence', lambda *_args: [evidence]
    )
    monkeypatch.setattr(
        'app.research.router.create_chat_provider', lambda *_args: OfflineProvider()
    )
    app = create_application(test_settings)
    with TestClient(app) as client:
        owner = _register(client, 'owner@example.com', 'owner')
        response = client.post(
            '/api/v1/research/query', headers=owner,
            json={'question': 'What happened in Genesis 4:1?'},
        )

    assert response.status_code == 200
    assert response.json()['grounding_status'] == 'evidence-only'
    assert response.json()['trail_node'] is not None
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AIOperation)) == 1
        assert session.scalar(select(func.count()).select_from(ResearchNode)) == 1


def test_network_failure_returns_evidence_only_and_persists_atomically(
    test_settings, monkeypatch,
):
    test_settings.ai_chat_provider = 'openai_compatible'
    evidence = ResearchEvidence(
        id='scripture:1', title='Genesis', reference='Genesis 4:1',
        text='Eve bore Cain.', source_type='canonical-scripture',
        tradition='Protestant', translation='KJV',
    )

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('private network address', request=request)

    shared_client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    monkeypatch.setattr(
        application_state_module, '_create_http_client', lambda: shared_client
    )
    monkeypatch.setattr(
        'app.research.router.retrieve_research_evidence', lambda *_args: [evidence]
    )
    app = create_application(test_settings)
    with TestClient(app) as client:
        owner = _register(client, 'owner@example.com', 'owner')
        response = client.post(
            '/api/v1/research/query', headers=owner,
            json={'question': 'What happened in Genesis 4:1?'},
        )

    assert response.status_code == 200
    assert response.json()['grounding_status'] == 'evidence-only'
    assert 'private network address' not in response.text
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AIOperation)) == 1
        assert session.scalar(select(func.count()).select_from(ResearchNode)) == 1


def test_oversized_evidence_is_bounded_in_response_and_stored_snapshot(
    test_settings, monkeypatch,
):
    class OfflineProvider:
        name = 'offline'

        async def complete(self, _messages):
            raise ProviderError('offline')

    oversized = ResearchEvidence(
        id='scripture:oversized',
        title='T' * 1_000_000,
        reference='R' * 1_000_000,
        text='E' * 1_000_000,
        source_type='canonical-scripture',
        tradition='P' * 1_000_000,
        translation='K' * 1_000_000,
        date_or_era='D' * 1_000_000,
        original_language='L' * 1_000_000,
        open_target='O' * 1_000_000,
    )
    monkeypatch.setattr(
        'app.research.router.retrieve_research_evidence', lambda *_args: [oversized]
    )
    monkeypatch.setattr(
        'app.research.router.create_chat_provider', lambda *_args: OfflineProvider()
    )
    app = create_application(test_settings)
    with TestClient(app) as client:
        owner = _register(client, 'owner@example.com', 'owner')
        response = client.post(
            '/api/v1/research/query', headers=owner,
            json={'question': 'Bound the source response'},
        )

    assert response.status_code == 200
    assert len(response.content) < 20_000
    assert len(response.json()['sources'][0]['text']) == 2_000
    with app.state.session_factory() as session:
        node = session.scalar(select(ResearchNode))
        assert len(node.response_snapshot['sources'][0]['text']) == 2_000
        assert len(str(node.response_snapshot)) < 20_000


def test_node_failure_rolls_back_pending_audit(test_settings, monkeypatch):
    def fail_node(*_args, **_kwargs):
        raise SQLAlchemyError('insert unavailable')

    monkeypatch.setattr('app.research.router.create_research_node', fail_node)
    app = create_application(test_settings)
    with TestClient(app) as client:
        owner = _register(client, 'owner@example.com', 'owner')
        response = client.post(
            '/api/v1/research/query', headers=owner,
            json={'question': 'Will this be atomic?'},
        )

    assert response.status_code == 503
    assert 'insert unavailable' not in response.text
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AIOperation)) == 0
        assert session.scalar(select(func.count()).select_from(ResearchNode)) == 0


def test_rollback_failure_preserves_safe_503_and_does_not_persist_pending_work(
    test_settings, monkeypatch,
):
    secret = 'database password from rollback driver'
    sessions = []

    class RollbackFailingSession:
        def __init__(self, inner):
            self.inner = inner
            self.rollback_calls = 0

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def rollback(self):
            self.rollback_calls += 1
            self.inner.rollback()
            raise RuntimeError(secret)

    def fail_node(*_args, **_kwargs):
        raise SQLAlchemyError('insert unavailable')

    app = create_application(test_settings)

    def broken_session():
        with app.state.session_factory() as session:
            proxy = RollbackFailingSession(session)
            sessions.append(proxy)
            yield proxy

    app.dependency_overrides[get_session] = broken_session
    monkeypatch.setattr(
        'app.research.router.retrieve_research_evidence', lambda *_args: []
    )
    monkeypatch.setattr('app.research.router.create_research_node', fail_node)
    with TestClient(app, raise_server_exceptions=False) as client:
        owner = _register(client, 'owner@example.com', 'owner')
        response = client.post(
            '/api/v1/research/query', headers=owner,
            json={'question': 'Will rollback stay safe?'},
        )

    assert response.status_code == 503
    assert response.json() == {
        'detail': {
            'code': 'research_unavailable',
            'message': 'Research is temporarily unavailable.',
        }
    }
    assert secret not in response.text
    assert sessions[-1].rollback_calls == 1
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AIOperation)) == 0
        assert session.scalar(select(func.count()).select_from(ResearchNode)) == 0


def test_audit_failure_does_not_create_or_commit_node(test_settings, monkeypatch):
    def fail_audit(*_args, **_kwargs):
        raise ResearchServiceError('private database detail')

    monkeypatch.setattr('app.research.service.ResearchService._audit', fail_audit)
    app = create_application(test_settings)
    with TestClient(app) as client:
        owner = _register(client, 'owner@example.com', 'owner')
        response = client.post(
            '/api/v1/research/query', headers=owner,
            json={'question': 'Will audit failure be safe?'},
        )

    assert response.status_code == 503
    assert 'private database detail' not in response.text
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AIOperation)) == 0
        assert session.scalar(select(func.count()).select_from(ResearchNode)) == 0


def test_parent_snapshot_prose_never_enters_follow_up_retrieval_or_prompt(
    test_settings, monkeypatch,
):
    sentinel = 'SENTINEL PRIOR RESPONSE PROSE MUST NEVER BE EVIDENCE'
    seen_questions = []
    seen_messages = []

    class OfflineProvider:
        name = 'offline'

        async def complete(self, messages):
            seen_messages.extend(messages)
            raise ProviderError('offline')

    evidence = ResearchEvidence(
        id='scripture:1', title='Genesis', reference='Genesis 4:1',
        text='Eve bore Cain.', source_type='canonical-scripture',
        tradition='Protestant', translation='KJV',
    )

    def retrieve(_session, question, _scopes, _depth):
        seen_questions.append(question)
        return [evidence]

    monkeypatch.setattr('app.research.router.retrieve_research_evidence', retrieve)
    monkeypatch.setattr(
        'app.research.router.create_chat_provider', lambda *_args: OfflineProvider()
    )
    app = create_application(test_settings)
    with TestClient(app) as client:
        owner = _register(client, 'owner@example.com', 'owner')
        root = client.post(
            '/api/v1/research/query', headers=owner,
            json={'question': 'Who was Cain?'},
        ).json()['trail_node']
        with app.state.session_factory() as session:
            node = session.get(ResearchNode, uuid.UUID(root['id']))
            snapshot = deepcopy(node.response_snapshot)
            snapshot['summary']['narrative'] = sentinel
            snapshot['people'] = [{
                'name': 'Cain', 'description': sentinel, 'role': 'son',
                'source_ids': ['scripture:1'],
            }]
            snapshot['places'] = [{
                'name': 'Eden', 'description': sentinel, 'location': 'garden',
                'source_ids': ['scripture:1'],
            }]
            node.response_snapshot = snapshot
            session.commit()
        child = client.post(
            '/api/v1/research/query', headers=owner,
            json={
                'question': 'What happened next?',
                'parent_node_id': root['id'],
                'conversation_context': {
                    'entity_names': ['CLIENT SENTINEL'],
                    'source_references': ['CLIENT REFERENCE'],
                },
            },
        )

    assert child.status_code == 200
    assert seen_questions[-1] == (
        'What happened next?\n'
        'Context entities: Cain; Eden\n'
        'Context source references: Genesis 4:1'
    )
    assert sentinel not in '\n'.join(
        message.content for message in seen_messages
    )
    assert sentinel not in seen_questions[-1]
    assert 'CLIENT SENTINEL' not in seen_questions[-1]
    assert 'CLIENT REFERENCE' not in '\n'.join(
        message.content for message in seen_messages
    )


def test_authenticated_root_ignores_client_conversation_context(
    test_settings, monkeypatch,
):
    seen_questions = []
    seen_messages = []

    class OfflineProvider:
        name = 'offline'

        async def complete(self, messages):
            seen_messages.extend(messages)
            raise ProviderError('offline')

    evidence = ResearchEvidence(
        id='scripture:1', title='Genesis', reference='Genesis 4:1',
        text='Eve bore Cain.', source_type='canonical-scripture',
        tradition='Protestant', translation='KJV',
    )

    def retrieve(_session, question, _scopes, _depth):
        seen_questions.append(question)
        return [evidence]

    monkeypatch.setattr('app.research.router.retrieve_research_evidence', retrieve)
    monkeypatch.setattr(
        'app.research.router.create_chat_provider', lambda *_args: OfflineProvider()
    )
    app = create_application(test_settings)
    with TestClient(app) as client:
        owner = _register(client, 'owner@example.com', 'owner')
        result = client.post(
            '/api/v1/research/query', headers=owner,
            json={
                'question': 'Who was Cain?',
                'conversation_context': {
                    'entity_names': ['CLIENT SENTINEL'],
                    'source_references': ['CLIENT REFERENCE'],
                },
            },
        )

    assert result.status_code == 200
    assert seen_questions == ['Who was Cain?']
    assert 'CLIENT SENTINEL' not in '\n'.join(
        message.content for message in seen_messages
    )
    assert 'CLIENT REFERENCE' not in '\n'.join(
        message.content for message in seen_messages
    )


def test_provider_configuration_failure_is_safe_503(test_settings, monkeypatch):
    def fail_provider(*_args):
        raise ValueError('secret provider configuration')

    monkeypatch.setattr('app.research.router.create_chat_provider', fail_provider)
    app = create_application(test_settings)
    with TestClient(app) as client:
        response = client.post(
            '/api/v1/research/query', json={'question': 'What happened?'},
        )

    assert response.status_code == 503
    assert 'secret provider configuration' not in response.text
