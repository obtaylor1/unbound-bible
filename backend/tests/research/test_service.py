import hashlib
import json
from types import SimpleNamespace

import pytest

from app.ai.contracts import ChatResult, ProviderError
from app.research.retrieval import ResearchEvidence
from app.research.schemas import (
    ClaimClassification,
    GroundingStatus,
    ResearchDepth,
    ResearchMode,
    ResearchQueryRequest,
    SourceScope,
)
from app.research.service import MAX_PROMPT_CHARS, ResearchService


class RecordingProvider:
    name = 'recording-provider'

    def __init__(self, content: str):
        self.content = content
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        return ChatResult(
            content=self.content,
            provider='normalized-provider',
            model='research-model-1',
        )


class FailingProvider:
    name = 'offline-provider'

    def __init__(self):
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        raise ProviderError('secret upstream detail', code='secret-code', retryable=True)


class RecordingSession:
    def __init__(self, *, fail_commit=False):
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_commit = fail_commit

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError('database password leaked by driver')

    def rollback(self):
        self.rollbacks += 1


def request(**overrides):
    values = {
        'question': 'What happened after the flood?',
        'source_scopes': [
            SourceScope.BIBLICAL_CANON,
            SourceScope.ETHIOPIAN_TRADITION,
        ],
        'depth': ResearchDepth.STUDY,
        'mode': ResearchMode.TIMELINE,
        'mode_parameters': {'from': 'flood', 'to': 'babel'},
    }
    values.update(overrides)
    return ResearchQueryRequest(**values)


def evidence():
    return [
        ResearchEvidence(
            id='scripture:1',
            title='Genesis — Genesis 9:1',
            reference='Genesis 9:1',
            text='God blessed Noah and his sons.',
            source_type='canonical-scripture',
            tradition='Protestant',
            translation='KJV',
            date_or_era='1611',
            original_language='Hebrew',
            open_target='/api/v1/texts/Genesis/9/1/details',
            score=42.5,
        )
    ]


def provider_document(*, claims=None, **overrides):
    value = {
        'summary': {
            'title': 'Summary',
            'claims': claims if claims is not None else [{
                'id': 'claim-1',
                'statement': 'The evidence describes a blessing of Noah and his sons.',
                'classification': 'canonical-scripture',
                'confidence': 'high',
                'source_ids': ['scripture:1'],
            }],
        },
    }
    value.update(overrides)
    return json.dumps(value)


@pytest.mark.asyncio
async def test_no_evidence_returns_insufficient_without_calling_provider_and_audits():
    provider = RecordingProvider(provider_document())
    session = RecordingSession()
    user = SimpleNamespace(id='user-id')

    result = await ResearchService(
        retriever=lambda *_: [], provider=provider, session=session, user=user
    ).query(request())

    assert result.grounding_status == GroundingStatus.INSUFFICIENT
    assert result.sources == []
    assert provider.calls == []
    assert result.provider == 'none'
    assert result.model == 'none'
    assert result.summary.claims[0].classification == ClaimClassification.AI_SYNTHESIS
    assert result.summary.claims[0].confidence == 'low'
    assert result.unknowns is not None
    assert 'library' in result.unknowns.claims[0].statement.lower()
    assert session.commits == 1
    operation = session.added[0]
    assert operation.user_id == 'user-id'
    assert operation.question_hash == hashlib.sha256(
        request().question.strip().encode()
    ).hexdigest()
    assert operation.validation_errors == ['no_verified_evidence']
    assert operation.source_ids == []


@pytest.mark.asyncio
async def test_provider_failure_returns_evidence_only_with_safe_server_text_and_audit():
    provider = FailingProvider()
    session = RecordingSession()

    result = await ResearchService(
        retriever=lambda *_: evidence(), provider=provider, session=session
    ).query(request())

    assert result.grounding_status == GroundingStatus.EVIDENCE_ONLY
    assert [source.id for source in result.sources] == ['scripture:1']
    assert result.provider == 'offline-provider'
    assert result.model == 'unavailable'
    response_text = result.model_dump_json()
    assert 'secret upstream detail' not in response_text
    assert 'secret-code' not in response_text
    assert result.unknowns is not None
    assert session.added[0].validation_errors == ['provider_unavailable']
    assert session.commits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('content', ['not json', '{"summary": {"title": 3}}'])
async def test_invalid_provider_response_returns_evidence_only_and_audits(content):
    provider = RecordingProvider(content)
    session = RecordingSession()

    result = await ResearchService(
        retriever=lambda *_: evidence(), provider=provider, session=session
    ).query(request())

    assert result.grounding_status == GroundingStatus.EVIDENCE_ONLY
    assert [source.id for source in result.sources] == ['scripture:1']
    assert result.provider == 'normalized-provider'
    assert result.model == 'research-model-1'
    assert session.added[0].validation_errors == ['invalid_structured_response']


@pytest.mark.asyncio
async def test_grounded_response_contains_only_validated_claims_and_audits_warnings():
    content = provider_document(
        claims=[
            {
                'id': 'valid',
                'statement': 'Noah and his sons are named in the evidence.',
                'classification': 'canonical-scripture',
                'confidence': 'high',
                'source_ids': ['scripture:1'],
            },
            {
                'id': 'invented',
                'statement': 'Provider prose containing a confidential invention.',
                'classification': 'historical',
                'confidence': 'high',
                'source_ids': ['made-up:99'],
            },
        ],
        timeline=[{
            'title': 'Blessing',
            'description': 'Noah and his sons were blessed.',
            'source_ids': ['scripture:1'],
            'confidence': 'high',
        }],
    )
    provider = RecordingProvider(content)
    session = RecordingSession()

    result = await ResearchService(
        retriever=lambda *_: evidence(), provider=provider, session=session
    ).query(request())

    assert result.grounding_status == GroundingStatus.GROUNDED
    assert [claim.id for claim in result.summary.claims] == ['valid']
    assert result.timeline and result.timeline[0].source_ids == ['scripture:1']
    assert result.provider == 'normalized-provider'
    assert result.model == 'research-model-1'
    operation = session.added[0]
    assert operation.grounding_status == 'grounded'
    assert operation.source_ids == ['scripture:1']
    assert operation.validation_errors == ['unsupported_claim_removed']
    assert 'confidential invention' not in json.dumps(operation.validation_errors)


@pytest.mark.asyncio
async def test_all_factual_claims_removed_is_evidence_only_not_grounded():
    content = provider_document(claims=[{
        'id': 'synthesis',
        'statement': 'A general synthesis.',
        'classification': 'ai-synthesis',
        'confidence': 'high',
        'source_ids': ['scripture:1'],
    }, {
        'id': 'unsupported',
        'statement': 'An unsupported fact.',
        'classification': 'historical',
        'confidence': 'high',
        'source_ids': ['missing'],
    }])

    result = await ResearchService(
        retriever=lambda *_: evidence(),
        provider=RecordingProvider(content),
    ).query(request())

    assert result.grounding_status == GroundingStatus.EVIDENCE_ONLY
    assert [claim.id for claim in result.summary.claims] == ['synthesis']


@pytest.mark.asyncio
async def test_prompt_is_compact_strict_and_contains_request_settings_but_no_ai_prose():
    provider = RecordingProvider(provider_document())

    await ResearchService(
        retriever=lambda *_: evidence(), provider=provider
    ).query(request())

    messages = provider.calls[0]
    assert [message.role for message in messages] == ['system', 'user']
    system = messages[0].content
    assert 'Use only the supplied evidence. Return one JSON object matching the schema.' in system
    assert 'Every factual claim and event must cite source_ids from the evidence.' in system
    assert 'Do not treat prior AI text as evidence. State uncertainty when evidence is silent.' in system
    assert 'Do not add a source merely because its scope was enabled.' in system
    assert 'narrative and other free-form fields are forbidden' in system
    for key in (
        'summary', 'timeline', 'canonical_account', 'historical_context',
        'unknowns', 'ancient_accounts', 'language_notes', 'people', 'places',
        'related_questions',
    ):
        assert key in system
    user_message = messages[1].content
    assert request().question in user_message
    assert 'biblical-canon' in user_message
    assert 'ethiopian-tradition' in user_message
    assert 'study' in user_message
    assert 'timeline' in user_message
    assert 'God blessed Noah and his sons.' in user_message
    assert 'ResearchEvidence(' not in user_message
    assert 'prior answer' not in user_message.lower()


@pytest.mark.asyncio
async def test_evidence_conversion_preserves_typed_provenance_and_open_target():
    result = await ResearchService(
        retriever=lambda *_: evidence(),
        provider=RecordingProvider(provider_document()),
    ).query(request())

    source = result.sources[0]
    assert source.source_type == 'canonical-scripture'
    assert source.tradition == 'Protestant'
    assert source.translation == 'KJV'
    assert source.date_or_era == '1611'
    assert source.original_language == 'Hebrew'
    assert source.text == 'God blessed Noah and his sons.'
    assert source.open_target == '/api/v1/texts/Genesis/9/1/details'


@pytest.mark.asyncio
async def test_retriever_receives_session_question_scopes_and_depth_exactly():
    calls = []
    session = RecordingSession()

    def retriever(*args):
        calls.append(args)
        return []

    payload = request()
    await ResearchService(
        retriever=retriever,
        provider=RecordingProvider(provider_document()),
        session=session,
    ).query(payload)

    assert calls == [(
        session,
        payload.question,
        payload.source_scopes,
        payload.depth,
    )]


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_without_exposing_database_secrets():
    session = RecordingSession(fail_commit=True)

    result = await ResearchService(
        retriever=lambda *_: [],
        provider=RecordingProvider(provider_document()),
        session=session,
    ).query(request())

    assert result.grounding_status == GroundingStatus.INSUFFICIENT
    assert 'database password' not in result.model_dump_json()
    assert session.commits == 1
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_retriever_generator_is_not_consumed_past_evidence_limit():
    consumed = 0

    def generated_evidence():
        nonlocal consumed
        for index in range(100):
            consumed += 1
            yield ResearchEvidence(
                id=f'scripture:{index}',
                title=f'Source {index}',
                reference=f'Genesis 1:{index + 1}',
                text='Evidence.',
                source_type='canonical-scripture',
                tradition='Protestant',
            )

    provider = RecordingProvider(provider_document())
    await ResearchService(
        retriever=lambda *_: generated_evidence(), provider=provider
    ).query(request())

    assert consumed == 32
    payload = json.loads(provider.calls[0][1].content)
    assert len(payload['evidence']) == 32


@pytest.mark.asyncio
async def test_prompt_is_valid_bounded_json_with_normalized_mode_parameters():
    raw_parameters = {
        f'{index:02d}-' + ('k' * 100): 'v' * 1_000_000
        for index in range(12)
    }
    payload_request = request(mode_parameters=raw_parameters)
    provider = RecordingProvider(provider_document())

    await ResearchService(
        retriever=lambda *_: evidence(), provider=provider
    ).query(payload_request)

    prompt = provider.calls[0][1].content
    parsed = json.loads(prompt)
    parameters = parsed['settings']['mode_parameters']
    assert len(prompt) <= MAX_PROMPT_CHARS
    assert len(parameters) == 8
    assert list(parameters) == sorted(parameters)
    assert all(len(key) <= 64 for key in parameters)
    assert all(len(value) <= 256 for value in parameters.values())
    assert payload_request.mode_parameters == raw_parameters


@pytest.mark.asyncio
async def test_evidence_records_are_added_only_while_json_prompt_fits_limit():
    oversized = [
        ResearchEvidence(
            id=f'scripture:{index}',
            title='T' * 1_000,
            reference='R' * 2_000,
            text='E' * 100_000,
            source_type='canonical-scripture',
            tradition='P' * 2_000,
            translation='KJV',
            date_or_era='D' * 2_000,
            original_language='L' * 2_000,
            open_target='O' * 2_000,
        )
        for index in range(32)
    ]
    provider = RecordingProvider(provider_document())

    result = await ResearchService(
        retriever=lambda *_: oversized, provider=provider
    ).query(request())

    prompt = provider.calls[0][1].content
    parsed = json.loads(prompt)
    assert len(prompt) <= MAX_PROMPT_CHARS
    assert len(parsed['evidence']) < 32
    assert all(len(item['text']) <= 2_000 for item in parsed['evidence'])
    assert [source.id for source in result.sources] == [
        item['id'] for item in parsed['evidence']
    ]
