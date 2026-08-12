import uuid

import pytest
from pydantic import ValidationError

from app.research.schemas import ResearchQueryRequest, ResearchResponse


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


@pytest.mark.parametrize(
    'referencing_field',
    [
        {'summary': {'title': 'Summary', 'claims': [
            {'text': 'A claim', 'source_ids': ['missing']}
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
        'sources': [{'id': 'known', 'title': 'Genesis'}],
        **referencing_field,
    }

    with pytest.raises(ValidationError, match='unknown source ID'):
        ResearchResponse.model_validate(payload)
