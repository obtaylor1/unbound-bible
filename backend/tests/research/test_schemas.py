import uuid

import pytest
from pydantic import ValidationError

from app.research.schemas import (
    ClaimClassification,
    GroundingStatus,
    ResearchDepth,
    ResearchMode,
    ResearchQueryRequest,
    ResearchResponse,
    ResearchSettings,
    SourceScope,
    SourceType,
)


def claim(claim_id='claim-1', source_id='known'):
    return {
        'id': claim_id,
        'statement': 'A grounded claim.',
        'classification': 'canonical-scripture',
        'confidence': 'high',
        'source_ids': [source_id],
    }


def test_query_request_uses_grounded_deep_research_defaults():
    request = ResearchQueryRequest(
        question='What happened between Eden and Abel?'
    )

    assert request.source_scopes == ['biblical-canon']
    assert request.depth == 'deep-research'
    assert request.mode == 'what-happened-between'


def test_query_request_rejects_unknown_source_scope():
    with pytest.raises(ValidationError):
        ResearchQueryRequest(question='What happened?', source_scopes=['the-web'])


@pytest.mark.parametrize(
    'source_scopes',
    [
        [],
        ['biblical-canon'] * 2,
        ['biblical-canon'] * 9,
        ['all-sources', 'biblical-canon'],
    ],
)
def test_query_request_requires_one_to_eight_unique_compatible_scopes(
    source_scopes,
):
    with pytest.raises(ValidationError):
        ResearchQueryRequest(
            question='What happened?', source_scopes=source_scopes
        )


@pytest.mark.parametrize('model', [ResearchQueryRequest, ResearchSettings])
@pytest.mark.parametrize('mode_parameters', [
    {f'key-{index}': 'value' for index in range(9)},
    {'x' * 65: 'value'},
    {'   ': 'value'},
    {'from': '   '},
    {'from': 'x' * 1_000_000},
    {'from': 'Eden', ' from ': 'Abel'},
])
def test_mode_parameters_reject_unbounded_blank_or_normalized_duplicate_values(
    model, mode_parameters,
):
    values = {'mode_parameters': mode_parameters}
    if model is ResearchQueryRequest:
        values['question'] = 'What happened?'

    with pytest.raises(ValidationError):
        model(**values)


@pytest.mark.parametrize('model', [ResearchQueryRequest, ResearchSettings])
def test_mode_parameters_are_stripped_and_echo_only_normalized_values(model):
    values = {'mode_parameters': {' from ': ' Eden ', 'to': ' Abel '}}
    if model is ResearchQueryRequest:
        values['question'] = 'What happened?'

    result = model(**values)

    assert result.mode_parameters == {'from': 'Eden', 'to': 'Abel'}


@pytest.mark.parametrize(
    'referencing_field',
    [
        {'summary': {'title': 'Summary', 'claims': [
            claim(source_id='missing')
        ]}},
        {'timeline': [{
            'title': 'An event',
            'description': 'Something happened.',
            'source_ids': ['missing'],
        }]},
        {'people': [{
            'name': 'A person',
            'description': 'A description.',
            'source_ids': ['missing'],
        }]},
        {'places': [{
            'name': 'A place',
            'description': 'A description.',
            'source_ids': ['missing'],
        }]},
    ],
)
def test_research_response_rejects_unknown_source_ids(referencing_field):
    payload = {
        'id': uuid.uuid4(),
        'query': 'What happened?',
        'mode': 'what-happened-between',
        'settings': {},
        'summary': {'title': 'Summary', 'claims': []},
        'sources': [{
            'id': 'known',
            'title': 'Genesis',
            'reference': 'Genesis 1:1',
            'excerpt': 'In the beginning',
            'source_type': 'canonical-scripture',
        }],
        **referencing_field,
    }

    with pytest.raises(ValidationError, match='unknown source ID'):
        ResearchResponse.model_validate(payload)


def test_planned_enum_values_serialize_as_api_strings():
    assert SourceScope.ETHIOPIAN_TRADITION.value == 'ethiopian-tradition'
    assert [depth.value for depth in ResearchDepth] == [
        'quick', 'study', 'deep-research', 'scholar'
    ]
    assert ResearchMode.BETWEEN.value == 'what-happened-between'
    assert set(classification.value for classification in ClaimClassification) == {
        'canonical-scripture',
        'ethiopian-canon',
        'ancient-text',
        'commentary',
        'tradition',
        'historical',
        'scholarship',
        'ai-synthesis',
    }
    assert {
        GroundingStatus.INSUFFICIENT.value,
        GroundingStatus.EVIDENCE_ONLY.value,
        GroundingStatus.GROUNDED.value,
    } == {'insufficient', 'evidence-only', 'grounded'}
    assert {source_type.value for source_type in SourceType} == {
        'canonical-scripture',
        'ethiopian-canon',
        'ancient-text',
        'manuscript',
        'historical-source',
        'early-christian-writing',
        'jewish-tradition',
        'church-tradition',
        'commentary',
        'scholarship',
        'ai-synthesis',
    }


def test_research_response_accepts_full_nested_grounded_payload():
    node_id = uuid.uuid4()
    response = ResearchResponse.model_validate({
        'id': uuid.uuid4(),
        'query': 'What happened between Eden and Abel?',
        'mode': 'what-happened-between',
        'settings': {
            'source_scopes': ['biblical-canon', 'ethiopian-tradition'],
            'depth': 'scholar',
            'mode_parameters': {'from': 'Eden', 'to': 'Abel'},
        },
        'summary': {'title': 'Summary', 'claims': [claim('summary')]},
        'timeline': [{
            'title': 'Outside Eden',
            'description': 'The family lived outside Eden.',
            'date_label': 'After Eden',
            'source_ids': ['known'],
            'confidence': 'high',
        }],
        'canonical_account': {
            'title': 'Canonical account', 'claims': [claim('canonical')]
        },
        'historical_context': {
            'title': 'Historical context', 'claims': [claim('history')]
        },
        'unknowns': {'title': 'Unknowns', 'claims': [claim('unknown')]},
        'ancient_accounts': [
            {'title': 'Ancient accounts', 'claims': [claim('ancient')]}
        ],
        'language_notes': [
            {'title': 'Language notes', 'claims': [claim('language')]}
        ],
        'people': [{
            'name': 'Abel', 'role': 'son', 'source_ids': ['known']
        }],
        'places': [{
            'name': 'Eden', 'location': 'unknown', 'source_ids': ['known']
        }],
        'trail_node': {
            'id': node_id,
            'question': 'What happened between Eden and Abel?',
            'label': 'Eden to Abel',
        },
        'sources': [{
            'id': 'known',
            'title': 'Genesis',
            'reference': 'Genesis 3–4',
            'excerpt': 'They left Eden.',
            'text': 'A longer source text.',
            'source_type': 'canonical-scripture',
            'tradition': 'biblical canon',
            'date_or_era': 'Ancient',
            'original_language': 'Hebrew',
            'translation': 'Example translation',
            'relevance': 'Primary canonical account',
            'open_target': 'bible://Genesis/3',
        }],
        'related_questions': ['What happened next?'],
        'grounding_status': 'grounded',
        'provider': 'test-provider',
        'model': 'test-model',
    })

    dumped = response.model_dump(mode='json')
    assert dumped['summary']['claims'][0]['statement'] == 'A grounded claim.'
    assert dumped['settings']['source_scopes'][1] == 'ethiopian-tradition'
    assert dumped['sources'][0]['source_type'] == 'canonical-scripture'


def test_research_response_rejects_duplicate_source_ids():
    source = {
        'id': 'duplicate',
        'title': 'Genesis',
        'reference': 'Genesis 1:1',
        'excerpt': 'In the beginning',
        'source_type': 'canonical-scripture',
    }

    with pytest.raises(ValidationError, match='duplicate source ID'):
        ResearchResponse.model_validate({
            'id': uuid.uuid4(),
            'query': 'What happened?',
            'mode': 'what-happened-between',
            'settings': {},
            'summary': {'title': 'Summary', 'claims': []},
            'sources': [source, source],
        })
