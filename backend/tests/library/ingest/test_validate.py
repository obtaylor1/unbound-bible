from dataclasses import FrozenInstanceError

import pytest

from app.library.ingest.normalize import normalize_verse
from app.library.ingest.validate import (
    ValidationFinding,
    ValidationResult,
    validate_edition,
)


def verse(chapter, number, text='Scripture text'):
    return normalize_verse('Genesis', chapter, number, text)


def coverage(chapters=1, verse_counts=None):
    return {'genesis': {'chapters': chapters, 'verse_counts': verse_counts or {}}}


def test_duplicate_missing_and_placeholder_errors_have_exact_codes():
    result = validate_edition(
        [
            verse(1, 1),
            verse(1, 1, 'Other duplicate row'),
            verse(1, 3, '[Awaiting full Ge\'ez source text ...]'),
        ],
        coverage(verse_counts={'1': 3}),
    )

    assert {finding.code for finding in result.errors} == {
        'duplicate_verse', 'missing_verse', 'placeholder_text',
    }
    assert not result.publishable


def test_related_recension_warning_never_blocks_complete_edition():
    result = validate_edition(
        [verse(1, 1)], coverage(verse_counts={'1': 1}), warnings=('related_recension',)
    )

    assert result.publishable
    assert result.errors == ()
    assert [finding.code for finding in result.warnings] == ['related_recension']


def test_missing_expected_work_and_chapter_are_errors():
    result = validate_edition(
        [verse(1, 1)],
        {
            'genesis': {'chapters': 2, 'verse_counts': {'1': 1, '2': 1}},
            'exodus': {'chapters': 1, 'verse_counts': {'1': 1}},
        },
    )

    assert {(finding.code, finding.work_id, finding.chapter) for finding in result.errors} == {
        ('missing_chapter', 'genesis', 2),
        ('missing_work', 'exodus', None),
    }


def test_extra_chapter_and_verse_are_coverage_mismatches():
    result = validate_edition(
        [verse(1, 1), verse(1, 2), verse(2, 1)], coverage(verse_counts={'1': 1})
    )

    assert [finding.code for finding in result.errors] == [
        'observed_coverage_mismatch',
        'observed_coverage_mismatch',
    ]
    assert {(finding.chapter, finding.verse) for finding in result.errors} == {(1, 2), (2, 1)}


def test_unexpected_work_is_coverage_mismatch():
    unexpected = normalize_verse('Exodus', 1, 1, 'Extra work')

    result = validate_edition([verse(1, 1), unexpected], coverage(verse_counts={'1': 1}))

    assert [(finding.code, finding.work_id) for finding in result.errors] == [
        ('observed_coverage_mismatch', 'exodus')
    ]


def test_repeated_text_at_different_positions_is_warning_not_error():
    result = validate_edition(
        [verse(1, 1, 'Amen.'), verse(1, 2, 'Amen.')],
        coverage(verse_counts={'1': 2}),
    )

    assert result.publishable
    assert [finding.code for finding in result.warnings] == ['repeated_text_checksum']


@pytest.mark.parametrize('text', [
    'They that wait upon the Lord shall renew their strength.',
    'The Lord waited for the people to return.',
])
def test_placeholder_detection_does_not_flag_scripture_language(text):
    result = validate_edition([verse(1, 1, text)], coverage(verse_counts={'1': 1}))

    assert result.publishable
    assert 'placeholder_text' not in {finding.code for finding in result.findings}


def test_generator_input_is_materialized_once():
    def source():
        yield verse(1, 1)

    result = validate_edition(source(), coverage(verse_counts={'1': 1}))

    assert result.publishable


def test_findings_are_deterministic_and_error_first_independent_of_input_order():
    rows = [
        verse(1, 3, 'lorem ipsum'),
        verse(1, 1, 'Amen'),
        verse(1, 2, 'Amen'),
    ]
    expected = coverage(verse_counts={'1': 3})

    first = validate_edition(rows, expected, warnings=('related_recension',))
    second = validate_edition(reversed(rows), expected, warnings=('related_recension',))

    assert first == second
    assert [finding.severity for finding in first.findings] == ['error', 'warning', 'warning']
    assert [finding.code for finding in first.findings] == [
        'placeholder_text', 'repeated_text_checksum', 'related_recension'
    ]


def test_public_results_and_findings_are_immutable():
    result = validate_edition([verse(1, 1)], coverage(verse_counts={'1': 1}))

    with pytest.raises(FrozenInstanceError):
        result.findings = ()
    with pytest.raises(FrozenInstanceError):
        ValidationFinding('error', 'test', 'message').message = 'changed'
    with pytest.raises(ValueError, match='severity'):
        ValidationFinding('notice', 'test', 'message')
    with pytest.raises(ValueError, match='chapter requires'):
        ValidationFinding('error', 'test', 'message', chapter=1)
    with pytest.raises(ValueError, match='verse requires'):
        ValidationFinding('error', 'test', 'message', work_id='genesis', verse=1)
    with pytest.raises(ValueError, match='findings must be a tuple'):
        ValidationResult([])


@pytest.mark.parametrize('expected_works', [
    {'unknown-work': {'chapters': 1}},
    {'genesis': {'chapters': 1, 'unknown': True}},
    {'genesis': {'chapters': True}},
    {'genesis': {'chapters': 201}},
    {'genesis': {'chapters': 1, 'verse_counts': {'2': 1}}},
])
def test_invalid_expected_coverage_is_rejected(expected_works):
    with pytest.raises(ValueError, match='expected'):
        validate_edition([verse(1, 1)], expected_works)


@pytest.mark.parametrize('warnings', [object(), ('',), ('not a warning!',)])
def test_invalid_caller_warning_types_are_rejected(warnings):
    with pytest.raises(ValueError, match='warning'):
        validate_edition([verse(1, 1)], coverage(verse_counts={'1': 1}), warnings=warnings)


@pytest.mark.parametrize('unsafe_text', [
    '',
    'unsafe\x00text',
    'unsafe\ud800text',
    '<script>unsafe</script>',
    1,
])
def test_defensively_rejects_unsafe_text_before_checksumming(unsafe_text):
    rows = [verse(1, 1), verse(1, 2)]
    for row in rows:
        object.__setattr__(row, 'text', unsafe_text)

    result = validate_edition(rows, coverage(verse_counts={'1': 2}))

    assert [finding.code for finding in result.errors] == ['unsafe_text', 'unsafe_text']
    assert result.warnings == ()


@pytest.mark.parametrize(('field', 'unsafe_value'), [
    ('work_id', []),
    ('source_book', '<unsafe>'),
    ('chapter', '1'),
    ('verse', []),
    ('source_locator', 'unsafe\x00locator'),
])
def test_defensively_rejects_corrupt_row_scalars_before_grouping(field, unsafe_value):
    row = verse(1, 1)
    object.__setattr__(row, field, unsafe_value)

    result = validate_edition([row], coverage(verse_counts={'1': 1}))

    assert 'unsafe_row' in {finding.code for finding in result.errors}
    assert result.warnings == ()


def test_whole_bracketed_book_or_chapter_description_is_placeholder():
    result = validate_edition(
        [verse(1, 1, '[The Book of Genesis, Chapter 1]')], coverage(verse_counts={'1': 1})
    )

    assert [finding.code for finding in result.errors] == ['placeholder_text']


def test_missing_verses_without_declared_counts_include_start_and_interior_gaps():
    result = validate_edition([verse(1, 2), verse(1, 4)], coverage())

    assert [(finding.code, finding.verse) for finding in result.errors] == [
        ('missing_verse', 1), ('missing_verse', 3)
    ]
