import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.ai.contracts import ProviderError
from app.ai.models import AIOperation
from app.application import create_application
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
            'places',
        }
        assert event['source_ids'] == ['scripture:1']
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
            node.response_snapshot = {'summary': {'narrative': sentinel}}
            session.commit()
        child = client.post(
            '/api/v1/research/query', headers=owner,
            json={'question': 'What happened next?', 'parent_node_id': root['id']},
        )

    assert child.status_code == 200
    assert seen_questions[-1] == 'What happened next?'
    assert sentinel not in '\n'.join(
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
