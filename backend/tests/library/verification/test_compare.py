from dataclasses import FrozenInstanceError

import pytest

from app.library.verification import (
    ComparisonCounts,
    ComparisonRules,
    CurrentPublicationIdentity,
    DifferenceClassification,
    SourceArtifactIdentity,
    SourceVerse,
    VerseDifference,
    VersePosition,
    WorkComparisonReport,
    compare_work,
)


SOURCE_SHA = 'a' * 64
PUBLICATION_SHA = 'b' * 64


def verse(chapter, number, text, work_id='genesis'):
    return SourceVerse(work_id=work_id, chapter=chapter, verse=number, text=text)


def compare(current, source, **overrides):
    values = {
        'work_id': 'genesis',
        'current': current,
        'source': source,
        'source_artifact_sha256': SOURCE_SHA,
        'current_publication_sha256': PUBLICATION_SHA,
        'parser_version': 'usfm-parser/1.0',
    }
    values.update(overrides)
    return compare_work(**values)


def direct_report(**overrides):
    values = {
        'schema_version': 1,
        'work_id': 'genesis',
        'source_artifact': SourceArtifactIdentity(SOURCE_SHA),
        'current_publication': CurrentPublicationIdentity(PUBLICATION_SHA),
        'parser_version': 'parser/1.0',
        'rules': ComparisonRules(),
        'totals': ComparisonCounts(exact=1),
        'declared_omissions': (),
        'differences': (),
    }
    values.update(overrides)
    return WorkComparisonReport(**values)


def test_compares_each_classification_and_counts_each_once():
    current = (
        verse(1, 1, 'In the beginning'),
        verse(1, 2, 'The  earth'),
        verse(1, 3, 'Current only'),
        verse(1, 5, 'Different words'),
    )
    source = (
        verse(1, 1, 'In the beginning'),
        verse(1, 2, 'The earth'),
        verse(1, 4, 'Source only'),
        verse(1, 5, 'Changed words'),
    )

    report = compare(current, source)

    assert (
        report.totals.exact,
        report.totals.formatting,
        report.totals.missing,
        report.totals.extra,
        report.totals.wording,
    ) == (1, 1, 1, 1, 1)
    assert [difference.position for difference in report.differences] == [
        VersePosition(1, 2),
        VersePosition(1, 3),
        VersePosition(1, 4),
        VersePosition(1, 5),
    ]
    assert [difference.classification for difference in report.differences] == [
        DifferenceClassification.FORMATTING,
        DifferenceClassification.EXTRA,
        DifferenceClassification.MISSING,
        DifferenceClassification.WORDING,
    ]
    assert report.differences[1].source_text is None
    assert report.differences[2].current_text is None
    assert report.is_verified_candidate is False


def test_verified_candidate_allows_only_exact_and_formatting_results():
    report = compare(
        [verse(1, 1, 'cafe\u0301'), verse(1, 2, 'The  earth')],
        [verse(1, 1, 'caf\u00e9'), verse(1, 2, 'The earth')],
    )

    assert report.totals.exact == 1
    assert report.totals.formatting == 1
    assert report.is_verified_candidate is True


@pytest.mark.parametrize('side', ['current', 'source'])
def test_rejects_duplicate_positions_on_each_side(side):
    rows = [verse(1, 1, 'First'), verse(1, 1, 'Second')]
    inputs = {'current': [verse(1, 1, 'First')], 'source': [verse(1, 1, 'First')]}
    inputs[side] = rows

    with pytest.raises(ValueError, match=rf'duplicate.*{side}|{side}.*duplicate'):
        compare(**inputs)


@pytest.mark.parametrize('side', ['current', 'source'])
def test_rejects_rows_for_a_different_work(side):
    inputs = {'current': [verse(1, 1, 'First')], 'source': [verse(1, 1, 'First')]}
    inputs[side] = [verse(1, 1, 'First', work_id='exodus')]

    with pytest.raises(ValueError, match=rf'{side}.*work_id'):
        compare(**inputs)


@pytest.mark.parametrize('work_id', ['', ' genesis ', 'gene\u0301sis', 1])
def test_source_verse_rejects_blank_or_non_normalized_work_ids(work_id):
    with pytest.raises(ValueError, match='work_id'):
        SourceVerse(work_id=work_id, chapter=1, verse=1, text='Text')


@pytest.mark.parametrize('chapter, number', [
    (True, 1), (1, False), (0, 1), (1, 0), (-1, 1), (1, -1), (1.0, 1), (1, '1'),
])
def test_source_verse_rejects_bool_noninteger_and_nonpositive_positions(chapter, number):
    with pytest.raises(ValueError, match='positive integers'):
        verse(chapter, number, 'Text')


@pytest.mark.parametrize('text', [None, 1, b'Text'])
def test_source_verse_requires_string_text_but_preserves_any_supplied_string(text):
    with pytest.raises(ValueError, match='text must be a string'):
        verse(1, 1, text)

    evidence = '  Preserved\r\nexactly  '
    assert verse(1, 1, evidence).text == evidence


def test_source_verse_and_rules_are_immutable_slots_values():
    row = verse(1, 1, 'Text')
    rules = ComparisonRules()

    with pytest.raises(FrozenInstanceError):
        row.text = 'Changed'
    with pytest.raises(FrozenInstanceError):
        rules.unicode_form = 'NFD'
    assert not hasattr(row, '__dict__')


@pytest.mark.parametrize(('classification', 'current_text', 'source_text'), [
    (DifferenceClassification.FORMATTING, None, 'Source'),
    (DifferenceClassification.FORMATTING, 'Current', None),
    (DifferenceClassification.WORDING, None, 'Source'),
    (DifferenceClassification.WORDING, 'Current', None),
    (DifferenceClassification.MISSING, 'Current', 'Source'),
    (DifferenceClassification.MISSING, None, None),
    (DifferenceClassification.EXTRA, 'Current', 'Source'),
    (DifferenceClassification.EXTRA, None, None),
])
def test_difference_rejects_text_shapes_that_contradict_classification(
    classification, current_text, source_text,
):
    with pytest.raises(ValueError, match='classification|text'):
        VerseDifference(
            VersePosition(1, 1), classification, current_text, source_text,
        )


def test_difference_rejects_exact_classification_entries():
    with pytest.raises(ValueError, match='classification'):
        VerseDifference(VersePosition(1, 1), 'exact', 'Same', 'Same')


def test_direct_report_rejects_counts_that_contradict_differences():
    difference = VerseDifference(
        VersePosition(1, 1), DifferenceClassification.WORDING, 'Current', 'Source',
    )

    with pytest.raises(ValueError, match='totals.*differences'):
        direct_report(
            totals=ComparisonCounts(exact=1, wording=0),
            differences=(difference,),
        )


@pytest.mark.parametrize('declared_omissions', [
    (VersePosition(1, 2), VersePosition(1, 2)),
    (VersePosition(2, 1), VersePosition(1, 9)),
])
def test_direct_report_requires_unique_sorted_declared_omissions(declared_omissions):
    with pytest.raises(ValueError, match='declared_omissions.*unique.*sorted'):
        direct_report(declared_omissions=declared_omissions)


@pytest.mark.parametrize('positions', [
    (VersePosition(1, 2), VersePosition(1, 2)),
    (VersePosition(2, 1), VersePosition(1, 9)),
])
def test_direct_report_requires_unique_sorted_difference_positions(positions):
    differences = tuple(
        VerseDifference(
            position, DifferenceClassification.WORDING, 'Current', 'Source',
        )
        for position in positions
    )

    with pytest.raises(ValueError, match='differences.*unique.*sorted'):
        direct_report(
            totals=ComparisonCounts(wording=2),
            differences=differences,
        )


def test_direct_report_rejects_difference_that_overlaps_declared_omission():
    position = VersePosition(1, 2)
    difference = VerseDifference(
        position, DifferenceClassification.EXTRA, 'Current', None,
    )

    with pytest.raises(ValueError, match='overlap'):
        direct_report(
            totals=ComparisonCounts(extra=1),
            declared_omissions=(position,),
            differences=(difference,),
        )


def test_default_rules_are_nfc_line_endings_and_whitespace_collapse():
    rules = ComparisonRules()

    assert rules.unicode_form == 'NFC'
    assert rules.normalize_line_endings is True
    assert rules.collapse_whitespace is True


@pytest.mark.parametrize('unicode_form', ['NFC', 'NFD', 'NFKC', 'NFKD'])
def test_rules_accept_only_supported_unicode_forms(unicode_form):
    assert ComparisonRules(unicode_form=unicode_form).unicode_form == unicode_form


@pytest.mark.parametrize('unicode_form', ['', 'nfc', 'UNKNOWN', None, []])
def test_rules_reject_unsupported_unicode_forms(unicode_form):
    with pytest.raises(ValueError, match='unicode_form'):
        ComparisonRules(unicode_form=unicode_form)


@pytest.mark.parametrize('field', ['normalize_line_endings', 'collapse_whitespace'])
def test_rules_require_real_booleans(field):
    with pytest.raises(ValueError, match=field):
        ComparisonRules(**{field: 1})


def test_crlf_and_lf_are_exact_only_when_line_normalization_enabled():
    enabled = compare([verse(1, 1, 'First\r\nSecond')], [verse(1, 1, 'First\nSecond')])
    disabled = compare(
        [verse(1, 1, 'First\r\nSecond')],
        [verse(1, 1, 'First\nSecond')],
        rules=ComparisonRules(normalize_line_endings=False),
    )

    assert enabled.totals.exact == 1
    assert disabled.totals.formatting == 1


@pytest.mark.parametrize(('current_text', 'source_text'), [
    ('The\tearth', 'The earth'),
    ('The\n earth', 'The earth'),
    ('  The earth  ', 'The earth'),
])
def test_whitespace_only_differences_are_formatting(current_text, source_text):
    report = compare([verse(1, 1, current_text)], [verse(1, 1, source_text)])

    assert report.totals.formatting == 1
    assert report.differences[0].classification is DifferenceClassification.FORMATTING


@pytest.mark.parametrize(('current_text', 'source_text'), [
    ('Word.', 'Word!'), ('Word', 'word'), ('cat', 'cut'), ('one 2', 'one 3'),
])
def test_semantic_character_changes_are_wording(current_text, source_text):
    report = compare([verse(1, 1, current_text)], [verse(1, 1, source_text)])

    assert report.totals.wording == 1
    assert report.differences[0].classification is DifferenceClassification.WORDING


def test_disabling_whitespace_collapse_makes_whitespace_change_wording():
    report = compare(
        [verse(1, 1, 'The  earth')],
        [verse(1, 1, 'The earth')],
        rules=ComparisonRules(collapse_whitespace=False),
    )

    assert report.totals.wording == 1


@pytest.mark.parametrize('field', ['source_artifact_sha256', 'current_publication_sha256'])
@pytest.mark.parametrize('value', ['', 'a' * 63, 'A' * 64, 'g' * 64, 64])
def test_rejects_invalid_checksums(field, value):
    with pytest.raises(ValueError, match=field):
        compare([verse(1, 1, 'Text')], [verse(1, 1, 'Text')], **{field: value})


@pytest.mark.parametrize('parser_version', ['', '  ', 1])
def test_rejects_blank_or_nonstring_parser_version(parser_version):
    with pytest.raises(ValueError, match='parser_version'):
        compare(
            [verse(1, 1, 'Text')], [verse(1, 1, 'Text')],
            parser_version=parser_version,
        )


def test_accepts_sorted_declared_omissions_as_metadata_without_affecting_counts():
    report = compare(
        [verse(1, 1, 'Text')],
        [verse(1, 1, 'Text')],
        declared_omissions=[(2, 3), VersePosition(1, 4)],
    )

    assert report.declared_omissions == (VersePosition(1, 4), VersePosition(2, 3))
    assert report.totals.exact == 1
    assert report.differences == ()


@pytest.mark.parametrize('omissions', [
    [(0, 1)], [(1, False)], [(1, 2), (1, 2)], [(1, 1)],
])
def test_rejects_invalid_duplicate_or_present_declared_omissions(omissions):
    with pytest.raises(ValueError, match='declared omission'):
        compare(
            [verse(1, 1, 'Text')],
            [verse(1, 1, 'Text')],
            declared_omissions=omissions,
        )


@pytest.mark.parametrize('current, source', [([], [verse(1, 1, 'Text')]), ([verse(1, 1, 'Text')], [])])
def test_fails_closed_when_either_dataset_is_empty(current, source):
    with pytest.raises(ValueError, match='must not be empty'):
        compare(current, source)


def test_difference_order_is_numeric_and_independent_of_input_order():
    current = [verse(10, 1, 'A'), verse(2, 10, 'A'), verse(2, 2, 'A')]
    source = [verse(2, 2, 'B'), verse(10, 1, 'B'), verse(2, 10, 'B')]

    first = compare(current, source)
    second = compare(reversed(current), reversed(source))

    expected = [VersePosition(2, 2), VersePosition(2, 10), VersePosition(10, 1)]
    assert [item.position for item in first.differences] == expected
    assert first == second
