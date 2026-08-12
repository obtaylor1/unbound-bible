from copy import deepcopy

import pytest

from app.research.retrieval import ResearchEvidence
from app.research.validation import (
    MAX_PROVIDER_CONTENT_CHARS,
    ResearchValidationError,
    parse_provider_json,
    validate_provider_document,
)


def evidence(*source_ids: str) -> list[ResearchEvidence]:
    return [
        ResearchEvidence(
            id=source_id,
            title=f'Source {source_id}',
            reference='Genesis 1:1',
            text='Source text.',
            source_type='canonical-scripture',
            tradition='biblical canon',
        )
        for source_id in source_ids
    ]


def claim(
    claim_id: str,
    source_ids: list[str],
    *,
    classification: str = 'canonical-scripture',
    confidence: str = 'high',
    statement: str = 'A claim.',
) -> dict:
    return {
        'id': claim_id,
        'statement': statement,
        'classification': classification,
        'confidence': confidence,
        'source_ids': source_ids,
    }


def document(**overrides) -> dict:
    value = {'summary': {'title': 'Summary', 'claims': []}}
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    ('content', 'expected'),
    [
        ('{"summary": {}}', {'summary': {}}),
        ('```json\n{"summary": {}}\n```', {'summary': {}}),
    ],
)
def test_parse_provider_json_accepts_object_and_one_outer_json_fence(
    content,
    expected,
):
    assert parse_provider_json(content) == expected


@pytest.mark.parametrize(
    'content',
    [
        'Here is the answer: {"summary": {}}',
        '[{"summary": {}}]',
        '{not JSON}',
        '```json\n```json\n{"summary": {}}\n```\n```',
        '```json\n{"summary": {}}\n```\n```json\n{}\n```',
    ],
)
def test_parse_provider_json_rejects_non_object_or_ambiguous_content(content):
    with pytest.raises(
        ResearchValidationError,
        match='Provider returned invalid structured research data',
    ):
        parse_provider_json(content)


def test_parse_provider_json_rejects_content_over_safe_bound():
    with pytest.raises(ResearchValidationError, match='exceeded the safe size limit'):
        parse_provider_json('x' * (MAX_PROVIDER_CONTENT_CHARS + 1))


def test_validation_removes_factual_claims_without_a_known_source():
    result = validate_provider_document(
        document(summary={
            'title': 'Summary',
            'claims': [claim('unknown', ['missing']), claim('empty', [])],
        }),
        evidence('known'),
    )

    assert result.summary.claims == []
    assert [warning.code for warning in result.validation_warnings] == [
        'unsupported_claim_removed',
        'unsupported_claim_removed',
    ]
    assert all(
        warning.message == 'An unsupported factual claim was removed.'
        for warning in result.validation_warnings
    )


def test_validation_allows_uncited_synthesis_and_uncertainty_at_low_confidence():
    result = validate_provider_document(
        document(
            summary={
                'title': 'Summary',
                'claims': [claim(
                    'synthesis',
                    [],
                    classification='ai-synthesis',
                    confidence='high',
                )],
            },
            historical_context={
                'title': 'Context',
                'claims': [claim(
                    'uncertain',
                    [],
                    classification='historical',
                    confidence='medium',
                    statement='It is uncertain when this occurred.',
                )],
            },
            unknowns={
                'title': 'Unknowns',
                'claims': [claim('unknown-detail', [], confidence='disputed')],
            },
        ),
        evidence('known'),
    )

    assert result.summary.claims[0].confidence == 'low'
    assert result.historical_context.claims[0].confidence == 'low'
    assert result.unknowns.claims[0].confidence == 'low'


def test_validation_filters_nested_references_and_unsupported_entries():
    grounded = claim('grounded', ['known'])
    partial = claim('partial', ['missing', 'known'], confidence='high')
    unsupported = claim('unsupported', ['missing'])
    result = validate_provider_document(
        document(
            summary={'title': 'Summary', 'claims': [grounded]},
            canonical_account={
                'title': 'Canon', 'claims': [partial, unsupported]
            },
            ancient_accounts=[
                {'title': 'Ancient', 'claims': [grounded]},
                {'title': '', 'claims': [grounded]},
            ],
            historical_context={'title': 'History', 'claims': [grounded]},
            language_notes=[{'title': 'Language', 'claims': [grounded]}],
            unknowns={'title': 'Unknowns', 'claims': [grounded]},
            timeline=[
                {
                    'title': 'Supported',
                    'description': 'Supported event.',
                    'source_ids': ['missing', 'known'],
                    'confidence': 'high',
                },
                {
                    'title': 'Unsupported',
                    'description': 'Unsupported event.',
                    'source_ids': ['missing'],
                },
            ],
            people=[
                {'name': 'Known person', 'source_ids': ['known', 'missing']},
                {'name': 'Unknown person', 'source_ids': ['missing']},
            ],
            places=[
                {'name': 'Known place', 'source_ids': ['known']},
                {'name': 'Unknown place', 'source_ids': []},
            ],
        ),
        evidence('known'),
    )

    assert result.canonical_account.claims[0].source_ids == ['known']
    assert result.canonical_account.claims[0].confidence == 'low'
    assert len(result.canonical_account.claims) == 1
    assert len(result.ancient_accounts) == 1
    assert result.historical_context.claims[0].source_ids == ['known']
    assert result.language_notes[0].claims[0].source_ids == ['known']
    assert result.unknowns.claims[0].source_ids == ['known']
    assert [event.title for event in result.timeline] == ['Supported']
    assert result.timeline[0].source_ids == ['known']
    assert result.timeline[0].confidence == 'low'
    assert [person.name for person in result.people] == ['Known person']
    assert result.people[0].source_ids == ['known']
    assert [place.name for place in result.places] == ['Known place']


def test_validation_normalizes_and_bounds_related_questions():
    result = validate_provider_document(
        document(related_questions=[
            ' First question? ',
            '',
            'first QUESTION?',
            'x' * 1_001,
            'Second?',
            'Third?',
            'Fourth?',
            'Fifth?',
            'Sixth?',
            42,
        ]),
        evidence('known'),
    )

    assert result.related_questions == [
        'First question?', 'Second?', 'Third?', 'Fourth?', 'Fifth?'
    ]


def test_validation_warnings_do_not_include_provider_prose():
    secret_prose = 'PRIVATE PROVIDER PROSE'
    result = validate_provider_document(
        document(summary={
            'title': 'Summary',
            'claims': [claim(
                'unsupported', ['missing'], statement=secret_prose
            )],
        }),
        evidence('known'),
    )

    rendered_warnings = str([
        warning.model_dump() for warning in result.validation_warnings
    ])
    assert secret_prose not in rendered_warnings


def test_validation_does_not_mutate_input_document():
    original = document(
        summary={
            'title': 'Summary',
            'claims': [claim('partial', ['known', 'missing'])],
        },
        related_questions=[' Trim me? '],
    )
    snapshot = deepcopy(original)

    validate_provider_document(original, evidence('known'))

    assert original == snapshot


@pytest.mark.parametrize(
    'bad_document',
    [
        {},
        {'summary': 'not a section'},
        {'summary': {'title': '', 'claims': []}},
    ],
)
def test_validation_rejects_malformed_required_summary(bad_document):
    with pytest.raises(
        ResearchValidationError,
        match='Provider returned invalid structured research data',
    ):
        validate_provider_document(bad_document, evidence('known'))
