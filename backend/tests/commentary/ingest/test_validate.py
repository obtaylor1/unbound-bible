import json
from pathlib import Path

import pytest

from app.commentary.ingest.types import NormalizedCommentaryEntry


ROOT = Path(__file__).parents[3]
REGISTRY = ROOT / 'data' / 'commentaries' / 'sources.json'


def _row(work='genesis', chapter=1, start=1, end=1, entry_type='verse', position=0):
    return NormalizedCommentaryEntry(
        work, chapter, start, end, entry_type, None, 'Commentary text.',
        f'provider:{work}:{position}', position,
    )


def _intro(work='genesis', chapter=None, position=0):
    return NormalizedCommentaryEntry(
        work, chapter, None, None, 'book_intro' if chapter is None else 'chapter_intro',
        None, 'Introduction.', f'provider:{work}:intro:{position}', position,
    )


def test_valid_rows_have_exact_coverage_and_nonblocking_intro_warnings():
    from app.commentary.ingest.validate import validate_commentary

    result = validate_commentary([_row(position=2), _row('exodus', position=1)], {'genesis', 'exodus'})

    assert result.coverage == {
        'books': 2,
        'chapters': 2,
        'entries': 2,
        'by_work': {
            'genesis': {'chapters': 1, 'chapter_numbers': (1,), 'entries': 1},
            'exodus': {'chapters': 1, 'chapter_numbers': (1,), 'entries': 1},
        },
    }
    assert result.error_count == 0
    assert result.warning_count == 4
    assert result.publishable is True
    assert [finding.code for finding in result.findings] == [
        'missing_book_intro', 'missing_chapter_intro',
        'missing_book_intro', 'missing_chapter_intro',
    ]


def test_no_rows_blocks_publication():
    from app.commentary.ingest.validate import validate_commentary

    result = validate_commentary([], {'genesis'})

    assert {finding.code for finding in result.findings if finding.severity == 'error'} == {'no_rows', 'missing_expected_book'}
    assert result.publishable is False


def test_missing_expected_book_is_the_only_blocking_coverage_finding():
    from app.commentary.ingest.validate import validate_commentary

    result = validate_commentary([_row()], {'genesis', 'exodus'})

    assert {finding.code for finding in result.findings if finding.severity == 'error'} == {'missing_expected_book'}
    assert result.publishable is False


def test_unexpected_book_is_the_only_blocking_coverage_finding():
    from app.commentary.ingest.validate import validate_commentary

    result = validate_commentary([_row(), _row('exodus', position=1)], {'genesis'})

    assert {finding.code for finding in result.findings if finding.severity == 'error'} == {'unexpected_book'}
    assert result.publishable is False


def test_duplicate_identity_is_the_only_blocking_identity_finding():
    from app.commentary.ingest.validate import validate_commentary

    result = validate_commentary([_intro(), _intro(position=99)], {'genesis'})

    assert {finding.code for finding in result.findings if finding.severity == 'error'} == {'duplicate_identity'}
    assert result.publishable is False


def test_overlapping_coverage_is_the_only_blocking_range_finding():
    from app.commentary.ingest.validate import validate_commentary

    result = validate_commentary([
        _row(start=1, end=2, entry_type='verse_range'),
        _row(start=2, end=3, entry_type='verse_range', position=2),
    ], {'genesis'})

    assert {finding.code for finding in result.findings if finding.severity == 'error'} == {'overlapping_coverage'}
    assert result.publishable is False


def test_duplicate_ignores_position_and_range_boundaries_are_precise():
    from app.commentary.ingest.validate import validate_commentary

    touching = validate_commentary([
        _row(start=1, end=2, entry_type='verse_range'),
        _row(start=3, end=4, entry_type='verse_range', position=8),
    ], {'genesis'})
    repeated = validate_commentary([_row(), _row(position=900)], {'genesis'})

    assert 'overlapping_coverage' not in {f.code for f in touching.findings}
    assert 'multiple_notes_at_anchor' in {f.code for f in repeated.findings}


def test_distinct_notes_at_same_exact_verse_are_publishable_and_warned():
    from app.commentary.ingest.validate import validate_commentary

    rows = [
        _row(position=0),
        NormalizedCommentaryEntry(
            'genesis', 1, 1, 1, 'verse', None, 'A second provider note.',
            'provider:genesis:second', 1,
        ),
    ]
    result = validate_commentary(rows, {'genesis'})

    assert result.error_count == 0
    assert 'multiple_notes_at_anchor' in {f.code for f in result.findings}
    assert result.coverage['entries'] == 2


def test_exact_duplicate_row_or_reused_locator_remains_blocking():
    from app.commentary.ingest.validate import validate_commentary

    exact = validate_commentary([_row(), _row()], {'genesis'})
    reused_locator = validate_commentary([
        _row(),
        NormalizedCommentaryEntry(
            'genesis', 1, 1, 1, 'verse', None, 'Different body.',
            'provider:genesis:0', 1,
        ),
    ], {'genesis'})

    assert 'duplicate_normalized_row' in {f.code for f in exact.findings}
    assert 'duplicate_source_locator' in {f.code for f in reused_locator.findings}


def test_exact_duplicate_range_notes_are_allowed_but_partial_overlap_is_blocked():
    from app.commentary.ingest.validate import validate_commentary

    exact_anchor = validate_commentary([
        _row(start=1, end=3, entry_type='verse_range'),
        NormalizedCommentaryEntry(
            'genesis', 1, 1, 3, 'verse_range', None, 'Another range note.',
            'provider:genesis:range:2', 1,
        ),
    ], {'genesis'})
    partial = validate_commentary([
        _row(start=1, end=3, entry_type='verse_range'),
        NormalizedCommentaryEntry(
            'genesis', 1, 3, 4, 'verse_range', None, 'Partial overlap.',
            'provider:genesis:range:3', 1,
        ),
    ], {'genesis'})

    assert exact_anchor.error_count == 0
    assert 'multiple_notes_at_anchor' in {f.code for f in exact_anchor.findings}
    assert 'overlapping_coverage' in {f.code for f in partial.findings}


def test_non_normalized_row_has_only_its_intended_blocker():
    from app.commentary.ingest.validate import validate_commentary

    result = validate_commentary([_row(), object()], {'genesis'})

    assert {finding.code for finding in result.findings if finding.severity == 'error'} == {'invalid_row_type'}


def test_bypassed_normalized_row_has_only_its_intended_blocker():
    from app.commentary.ingest.validate import validate_commentary

    unsafe = _row(start=2, end=2, position=2)
    object.__setattr__(unsafe, 'body', '   ')
    result = validate_commentary([_intro(), unsafe], {'genesis'})

    assert {finding.code for finding in result.findings if finding.severity == 'error'} == {'unsafe_normalized_row'}


@pytest.mark.parametrize('expected', [set(), ['genesis'], {'Genesis'}, {True}, {'unknown'}])
def test_expected_books_must_be_nonempty_exact_canonical_set(expected):
    from app.commentary.ingest.validate import validate_commentary

    with pytest.raises(ValueError, match='expected_books'):
        validate_commentary([_row()], expected)


@pytest.mark.parametrize('previous', [None, {}, {'entries': 0}, {'entries': True}, {'entries': '20'}, {'other': 20}])
def test_malformed_previous_coverage_is_rejected(previous):
    from app.commentary.ingest.validate import validate_commentary

    if previous is None:
        assert validate_commentary([_row()], {'genesis'}, previous).publishable
    else:
        with pytest.raises(ValueError, match='previous_coverage'):
            validate_commentary([_row()], {'genesis'}, previous)


def test_regression_allows_exactly_five_percent_and_blocks_more_without_floats():
    from app.commentary.ingest.validate import validate_commentary

    rows_95 = [_row(start=index, end=index, position=index) for index in range(1, 96)]
    rows_94 = [_row(start=index, end=index, position=index) for index in range(1, 95)]

    assert validate_commentary(rows_95, {'genesis'}, {'entries': 100}).publishable
    blocked = validate_commentary(rows_94, {'genesis'}, {'entries': 100})
    assert 'record_count_regression' in {finding.code for finding in blocked.findings}


def test_prior_full_coverage_mapping_is_accepted_for_regression_checks():
    from app.commentary.ingest.validate import validate_commentary

    prior = {
        'books': 1, 'chapters': 1, 'entries': 1,
        'by_work': {'genesis': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1}},
    }

    assert validate_commentary([_row()], {'genesis'}, prior).publishable


def test_legacy_prior_coverage_without_chapter_numbers_remains_accepted():
    from app.commentary.ingest.validate import validate_commentary

    legacy = {
        'books': 1, 'chapters': 1, 'entries': 1,
        'by_work': {'genesis': {'chapters': 1, 'entries': 1}},
    }

    result = validate_commentary([_row()], {'genesis'}, legacy)

    assert result.publishable is True
    assert result.coverage['by_work']['genesis']['chapter_numbers'] == (1,)


def test_prior_full_coverage_rejects_zero_total_entries():
    from app.commentary.ingest.validate import validate_commentary

    with pytest.raises(ValueError, match='previous_coverage'):
        validate_commentary(
            [_row()], {'genesis'},
            {'books': 0, 'chapters': 0, 'entries': 0, 'by_work': {}},
        )


def test_prior_full_coverage_rejects_zero_entry_work():
    from app.commentary.ingest.validate import validate_commentary

    previous = {
        'books': 2, 'chapters': 1, 'entries': 2,
        'by_work': {
            'genesis': {'chapters': 0, 'chapter_numbers': [], 'entries': 0},
            'exodus': {'chapters': 1, 'chapter_numbers': [1], 'entries': 2},
        },
    }
    with pytest.raises(ValueError, match='previous_coverage'):
        validate_commentary([_row()], {'genesis'}, previous)


@pytest.mark.parametrize('previous', [
    {'entries': 1, 'books': 1},
    {'entries': 1, 'other': 1},
    {'books': 1, 'chapters': 1, 'entries': 1, 'by_work': {'': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1}}},
    {'books': 1, 'chapters': 1, 'entries': 1, 'by_work': {'unknown': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1}}},
    {'books': 1, 'chapters': 1, 'entries': 1, 'by_work': {'genesis': {'chapters': 1, 'chapter_numbers': [1]}}},
    {'books': 1, 'chapters': 1, 'entries': 1, 'by_work': {'genesis': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1, 'extra': 1}}},
    {'books': True, 'chapters': 1, 'entries': 1, 'by_work': {'genesis': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1}}},
    {'books': 1, 'chapters': -1, 'entries': 1, 'by_work': {'genesis': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1}}},
    {'books': 1, 'chapters': 2, 'entries': 1, 'by_work': {'genesis': {'chapters': 2, 'chapter_numbers': [1, 2], 'entries': 1}}},
    {'books': 0, 'chapters': 0, 'entries': 1, 'by_work': {'genesis': {'chapters': 0, 'chapter_numbers': [], 'entries': 1}}},
    {'books': 1, 'chapters': 0, 'entries': 0, 'by_work': {'genesis': {'chapters': 0, 'chapter_numbers': [], 'entries': 0}}},
    {'books': 2, 'chapters': 1, 'entries': 1, 'by_work': {'genesis': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1}}},
    {'books': 1, 'chapters': 1, 'entries': 2, 'by_work': {'genesis': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1}}},
])
def test_previous_coverage_requires_consistent_canonical_full_shape(previous):
    from app.commentary.ingest.validate import validate_commentary

    with pytest.raises(ValueError, match='previous_coverage'):
        validate_commentary([_row()], {'genesis'}, previous)


def test_result_is_deterministic_independent_of_input_order():
    from app.commentary.ingest.validate import validate_commentary

    rows = [_row('exodus', position=8), _row('genesis', position=3), _row('genesis', position=4)]
    assert validate_commentary(rows, {'genesis', 'exodus'}) == validate_commentary(reversed(rows), {'genesis', 'exodus'})


def test_findings_and_result_are_immutable_and_constrained():
    from app.commentary.ingest.validate import ValidationFinding, CommentaryValidationResult

    with pytest.raises(ValueError):
        ValidationFinding('info', 'bad-code', 'x')
    with pytest.raises(ValueError):
        ValidationFinding('error', 'bad-code', 'x')
    with pytest.raises(ValueError):
        ValidationFinding('error', 'safe_code', ' ', 'genesis')
    with pytest.raises(ValueError):
        CommentaryValidationResult((), {})


def test_result_coverage_is_deeply_copied_and_immutable():
    from app.commentary.ingest.validate import CommentaryValidationResult, ValidationFinding, validate_commentary

    source_coverage = {
        'books': 1, 'chapters': 1, 'entries': 1,
        'by_work': {'genesis': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1}},
    }
    findings = (ValidationFinding('warning', 'safe_warning', 'Safe warning.'),)
    result = CommentaryValidationResult(findings, source_coverage)
    source_coverage['entries'] = 99
    source_coverage['by_work']['genesis']['entries'] = 99
    source_coverage['by_work']['genesis']['chapter_numbers'].append(2)

    assert result.coverage['entries'] == 1
    assert result.coverage['by_work']['genesis']['entries'] == 1
    assert result.coverage['by_work']['genesis']['chapter_numbers'] == (1,)
    with pytest.raises(TypeError):
        result.coverage['entries'] = 2
    with pytest.raises(TypeError):
        result.coverage['by_work']['genesis']['entries'] = 2
    with pytest.raises(AttributeError):
        result.coverage['by_work']['genesis']['chapter_numbers'].append(2)
    with pytest.raises(AttributeError):
        result.findings.append(findings[0])
    assert validate_commentary([_row()], {'genesis'}).coverage['entries'] == 1


@pytest.mark.parametrize('coverage', [
    {'books': 1, 'chapters': 1, 'entries': 1, 'by_work': {'unknown': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1}}},
    {'books': 1, 'chapters': 1, 'entries': 1, 'by_work': {'genesis': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1, 'extra': 1}}},
    {'books': 2, 'chapters': 1, 'entries': 1, 'by_work': {'genesis': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1}}},
    {'books': 1, 'chapters': 2, 'entries': 1, 'by_work': {'genesis': {'chapters': 2, 'chapter_numbers': [1, 2], 'entries': 1}}},
    {'books': 1, 'chapters': 1, 'entries': 1, 'by_work': {'genesis': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1}}, 'extra': 1},
])
def test_public_validation_result_rejects_nonsensical_coverage(coverage):
    from app.commentary.ingest.validate import CommentaryValidationResult

    with pytest.raises(ValueError, match='coverage'):
        CommentaryValidationResult((), coverage)


@pytest.mark.parametrize('chapter_numbers', [
    [2, 1], [1, 1], [0], [True], ['1'], [1], '1', None,
])
def test_coverage_rejects_noncanonical_chapter_number_snapshots(chapter_numbers):
    from app.commentary.ingest.validate import CommentaryValidationResult

    coverage = {
        'books': 1, 'chapters': 2, 'entries': 2,
        'by_work': {
            'genesis': {
                'chapters': 2, 'chapter_numbers': chapter_numbers, 'entries': 2,
            },
        },
    }
    with pytest.raises(ValueError, match='coverage'):
        CommentaryValidationResult((), coverage)


def test_source_registry_loads_exact_live_catalog_in_stable_order():
    from app.commentary.ingest.validate import load_source_registry

    registry = load_source_registry(REGISTRY)

    expected = {
        'matthew-henry': {
            'title': 'Matthew Henry Bible Commentary', 'abbreviation': 'MHC', 'author': 'Matthew Henry', 'publication_period': '1706–1710', 'tradition': 'Reformed Protestant', 'language': 'eng', 'attribution': 'Matthew Henry Bible Commentary by Matthew Henry. Provider-declared public-domain source distributed by the Free Use Bible API.', 'upstream_url': 'https://bible.helloao.org/api/c/matthew-henry/books.json', 'license_spdx': 'LicenseRef-Public-Domain', 'license_url': 'https://creativecommons.org/publicdomain/mark/1.0/', 'license_basis': "HelloAO's catalog applies the Creative Commons Public Domain Mark 1.0 to this checksum-pinned dataset. The provider's title, author link, and source catalog identify Matthew Henry's historical commentary; they do not identify a particular print edition. This records the provider declaration and historical identity review, not legal certification or a jurisdiction-specific copyright conclusion.", 'license_reviewer': 'Codex-assisted review', 'license_reviewed_on': '2026-08-04', 'reviewed_urls': ('https://bible.helloao.org/api/available_commentaries.json','https://bible.helloao.org/api/c/matthew-henry/books.json','https://bible.helloao.org/docs/reference/','https://creativecommons.org/publicdomain/mark/1.0/','https://en.wikipedia.org/wiki/Matthew_Henry'), 'source_checksum': 'ad2850450a1e5c0546c275f4bd09b9325ae47424d83311120ca7ced5724c4bc8', 'expected_book_count': 65,
            'expected_source_books': ('GEN','EXO','LEV','NUM','DEU','JOS','JDG','RUT','1SA','2SA','1KI','2KI','1CH','2CH','EZR','NEH','EST','JOB','PSA','PRO','ECC','ISA','JER','LAM','EZK','DAN','HOS','JOL','AMO','OBA','JON','MIC','NAM','HAB','ZEP','HAG','ZEC','MAL','MAT','MRK','LUK','JHN','ACT','ROM','1CO','2CO','GAL','EPH','PHP','COL','1TH','2TH','1TI','2TI','TIT','PHM','HEB','JAS','1PE','2PE','1JN','2JN','3JN','JUD','REV'),
        },
        'john-gill': {
            'title': 'John Gill Bible Commentary', 'abbreviation': 'JGC', 'author': 'John Gill', 'publication_period': '1746–1763', 'tradition': 'Particular Baptist', 'language': 'eng', 'attribution': 'John Gill Bible Commentary by John Gill. Provider-declared public-domain source distributed by the Free Use Bible API.', 'upstream_url': 'https://bible.helloao.org/api/c/john-gill/books.json', 'license_spdx': 'LicenseRef-Public-Domain', 'license_url': 'https://creativecommons.org/publicdomain/mark/1.0/', 'license_basis': "HelloAO's catalog applies the Creative Commons Public Domain Mark 1.0 to this checksum-pinned dataset. The provider's title, author link, and source catalog identify John Gill's historical commentary; they do not identify a particular print edition. This records the provider declaration and historical identity review, not legal certification or a jurisdiction-specific copyright conclusion.", 'license_reviewer': 'Codex-assisted review', 'license_reviewed_on': '2026-08-04', 'reviewed_urls': ('https://bible.helloao.org/api/available_commentaries.json','https://bible.helloao.org/api/c/john-gill/books.json','https://bible.helloao.org/docs/reference/','https://creativecommons.org/publicdomain/mark/1.0/','https://en.wikipedia.org/wiki/John_Gill_(theologian)'), 'source_checksum': 'f6fcfd6c3a726dc834cfaf1ae1cd0bf49bffb88c1246ac3500699e8af7be71a5', 'expected_book_count': 66,
            'expected_source_books': ('GEN','EXO','LEV','NUM','DEU','JOS','JDG','RUT','1SA','2SA','1KI','2KI','1CH','2CH','EZR','NEH','EST','JOB','PSA','PRO','ECC','SNG','ISA','JER','LAM','EZK','DAN','HOS','JOL','AMO','OBA','JON','MIC','NAM','HAB','ZEP','HAG','ZEC','MAL','MAT','MRK','LUK','JHN','ACT','ROM','1CO','2CO','GAL','EPH','PHP','COL','1TH','2TH','1TI','2TI','TIT','PHM','HEB','JAS','1PE','2PE','1JN','2JN','3JN','JUD','REV'),
        },
        'adam-clarke': {
            'title': 'Adam Clarke Bible Commentary', 'abbreviation': 'ACC', 'author': 'Adam Clarke', 'publication_period': '1810–1826', 'tradition': 'Wesleyan Methodist', 'language': 'eng', 'attribution': 'Adam Clarke Bible Commentary by Adam Clarke. Provider-declared public-domain source distributed by the Free Use Bible API.', 'upstream_url': 'https://bible.helloao.org/api/c/adam-clarke/books.json', 'license_spdx': 'LicenseRef-Public-Domain', 'license_url': 'https://creativecommons.org/publicdomain/mark/1.0/', 'license_basis': "HelloAO's catalog applies the Creative Commons Public Domain Mark 1.0 to this checksum-pinned dataset. The provider's title, author link, and source catalog identify Adam Clarke's historical commentary; they do not identify a particular print edition. This records the provider declaration and historical identity review, not legal certification or a jurisdiction-specific copyright conclusion.", 'license_reviewer': 'Codex-assisted review', 'license_reviewed_on': '2026-08-04', 'reviewed_urls': ('https://bible.helloao.org/api/available_commentaries.json','https://bible.helloao.org/api/c/adam-clarke/books.json','https://bible.helloao.org/docs/reference/','https://creativecommons.org/publicdomain/mark/1.0/','https://en.wikipedia.org/wiki/Adam_Clarke'), 'source_checksum': '92e28c9363c876d215e296f2fe04abb3ab7e34a2aacebdf06bd62ae79c6e3dba', 'expected_book_count': 57,
            'expected_source_books': ('GEN','EXO','LEV','NUM','JOS','RUT','1SA','2SA','1KI','2KI','1CH','2CH','EZR','NEH','EST','JOB','SNG','ISA','LAM','EZK','DAN','HOS','AMO','OBA','JON','MIC','NAM','HAB','ZEP','HAG','ZEC','MRK','LUK','JHN','ACT','ROM','1CO','2CO','GAL','EPH','PHP','COL','1TH','2TH','1TI','2TI','TIT','PHM','HEB','JAS','1PE','2PE','1JN','2JN','3JN','JUD','REV'),
        },
        'jamieson-fausset-brown': {
            'title': 'Jamieson-Fausset-Brown Bible Commentary', 'abbreviation': 'JFB', 'author': 'Robert Jamieson, A. R. Fausset, and David Brown', 'publication_period': '1871', 'tradition': 'Protestant', 'language': 'eng', 'attribution': 'Jamieson-Fausset-Brown Bible Commentary by Robert Jamieson, A. R. Fausset, and David Brown. Provider-declared public-domain source distributed by the Free Use Bible API.', 'upstream_url': 'https://bible.helloao.org/api/c/jamieson-fausset-brown/books.json', 'license_spdx': 'LicenseRef-Public-Domain', 'license_url': 'https://creativecommons.org/publicdomain/mark/1.0/', 'license_basis': "HelloAO's catalog applies the Creative Commons Public Domain Mark 1.0 to this checksum-pinned dataset. The provider's title, work link, and source catalog identify the historical commentary by Robert Jamieson, A. R. Fausset, and David Brown; they do not identify a particular print edition. This records the provider declaration and historical identity review, not legal certification or a jurisdiction-specific copyright conclusion.", 'license_reviewer': 'Codex-assisted review', 'license_reviewed_on': '2026-08-04', 'reviewed_urls': ('https://bible.helloao.org/api/available_commentaries.json','https://bible.helloao.org/api/c/jamieson-fausset-brown/books.json','https://bible.helloao.org/docs/reference/','https://creativecommons.org/publicdomain/mark/1.0/','https://en.wikipedia.org/wiki/Jamieson-Fausset-Brown_Bible_Commentary'), 'source_checksum': 'db3d4c8b3c1f32ef9d1430a57392e02bda3a17aac1f9bbe398461de021a3cb13', 'expected_book_count': 66,
            'expected_source_books': ('GEN','EXO','LEV','NUM','DEU','JOS','JDG','RUT','1SA','2SA','1KI','2KI','1CH','2CH','EZR','NEH','EST','JOB','PSA','PRO','ECC','SNG','ISA','JER','LAM','EZK','DAN','HOS','JOL','AMO','OBA','JON','MIC','NAM','HAB','ZEP','HAG','ZEC','MAL','MAT','MRK','LUK','JHN','ACT','ROM','1CO','2CO','GAL','EPH','PHP','COL','1TH','2TH','1TI','2TI','TIT','PHM','HEB','JAS','1PE','2PE','1JN','2JN','3JN','JUD','REV'),
        },
        'keil-delitzsch': {
            'title': 'Carl Friedrich Keil and Franz Delitzsch Old Testament Commentary', 'abbreviation': 'KD', 'author': 'Carl Friedrich Keil and Franz Delitzsch', 'publication_period': '1861–1875', 'tradition': 'Lutheran Protestant', 'language': 'eng', 'attribution': 'Carl Friedrich Keil and Franz Delitzsch Old Testament Commentary by Carl Friedrich Keil and Franz Delitzsch. Provider-declared public-domain source distributed by the Free Use Bible API.', 'upstream_url': 'https://bible.helloao.org/api/c/keil-delitzsch/books.json', 'license_spdx': 'LicenseRef-Public-Domain', 'license_url': 'https://creativecommons.org/publicdomain/mark/1.0/', 'license_basis': "HelloAO's catalog applies the Creative Commons Public Domain Mark 1.0 to this checksum-pinned English dataset. The provider's title, work link, and source catalog identify the historical Old Testament commentary by Carl Friedrich Keil and Franz Delitzsch; they do not identify a particular print or translation edition. This records the provider declaration and historical identity review, not legal certification or a jurisdiction-specific copyright conclusion.", 'license_reviewer': 'Codex-assisted review', 'license_reviewed_on': '2026-08-04', 'reviewed_urls': ('https://bible.helloao.org/api/available_commentaries.json','https://bible.helloao.org/api/c/keil-delitzsch/books.json','https://bible.helloao.org/docs/reference/','https://creativecommons.org/publicdomain/mark/1.0/','https://worthy.bible/commentaries/keil-delitzsch-commentary'), 'source_checksum': 'bb5cc0f9cfe0a93b3c903bb6972c6bc8c4e9f2bd3be6c2a6d276737cf9c5edce', 'expected_book_count': 39,
            'expected_source_books': ('GEN','EXO','LEV','NUM','DEU','JOS','JDG','RUT','1SA','2SA','1KI','2KI','1CH','2CH','EZR','NEH','EST','JOB','PSA','PRO','ECC','SNG','ISA','JER','LAM','EZK','DAN','HOS','JOL','AMO','OBA','JON','MIC','NAM','HAB','ZEP','HAG','ZEC','MAL'),
        },
    }
    assert list(registry) == list(expected)
    for source_id, metadata in registry.items():
        # The registry fingerprint pins the full reviewed record. Keep the
        # human-readable provenance assertions focused on its required meaning.
        assert metadata.provider_dataset_checksum in metadata.attribution
        assert metadata.provider_dataset_checksum in metadata.license_basis
        assert 'exact digital edition' in metadata.license_basis
        assert 'not legal certification' in metadata.license_basis
        assert metadata.reviewed_urls == (
            'https://bible.helloao.org/api/available_commentaries.json',
            metadata.upstream_url,
            'https://bible.helloao.org/docs/reference/',
            metadata.license_url,
        )
        expected[source_id].update({
            'attribution': metadata.attribution,
            'license_basis': metadata.license_basis,
            'reviewed_urls': metadata.reviewed_urls,
        })
    assert {
        source_id: {
            'title': metadata.title, 'abbreviation': metadata.abbreviation, 'author': metadata.author,
            'publication_period': metadata.publication_period, 'tradition': metadata.tradition,
            'language': metadata.language, 'attribution': metadata.attribution,
            'upstream_url': metadata.upstream_url, 'license_spdx': metadata.license_spdx,
            'license_url': metadata.license_url, 'license_basis': metadata.license_basis,
            'license_reviewer': metadata.license_reviewer,
            'license_reviewed_on': metadata.license_reviewed_on,
            'reviewed_urls': metadata.reviewed_urls,
            'source_checksum': metadata.provider_dataset_checksum,
            'expected_book_count': metadata.expected_book_count,
            'expected_source_books': metadata.expected_source_books,
        }
        for source_id, metadata in registry.items()
    } == expected


def _raw_registry(tmp_path, text):
    path = tmp_path / 'sources.json'
    path.write_text(text, encoding='utf-8')
    return path


@pytest.mark.parametrize('mutator', [
    lambda text: text.replace('"title":', '"title":"duplicate", "title":', 1),
    lambda text: text.replace('"matthew-henry":', '"tyndale":', 1),
    lambda text: text.replace('"license_spdx": "LicenseRef-Public-Domain"', '"license_spdx": "MIT"', 1),
    lambda text: text.replace('https://creativecommons.org/publicdomain/mark/1.0/', 'http://example.test/', 1),
    lambda text: text.replace('2026-08-04', '2999-01-01', 1),
    lambda text: text.replace('Codex-assisted review', '', 1),
    lambda text: text.replace('"https://bible.helloao.org/api/available_commentaries.json",', '', 1),
    lambda text: text.replace('https://bible.helloao.org/', 'https://user:pass@bible.helloao.org/', 1),
    lambda text: text.replace(
        '"provider_dataset_checksum": "', '"provider_dataset_checksum": "UPPER', 1,
    ),
    lambda text: text.replace('"expected_book_count": 65', '"expected_book_count": 64', 1),
    lambda text: text.replace('"GEN",', '"GEN","GEN",', 1),
    lambda text: text.replace('"GEN",', '"gen",', 1),
])
def test_source_registry_rejects_hostile_metadata(tmp_path, mutator):
    from app.commentary.ingest.validate import load_source_registry

    with pytest.raises(ValueError):
        load_source_registry(_raw_registry(tmp_path, mutator(REGISTRY.read_text(encoding='utf-8'))))


@pytest.mark.parametrize('mutator', [
    lambda text: text.replace('Matthew Henry Bible Commentary', 'Tampered Commentary', 1),
    lambda text: text.replace('https://bible.helloao.org/api/c/matthew-henry/books.json', 'https://evil.example/api/c/matthew-henry/books.json', 1),
    lambda text: text.replace('https://bible.helloao.org/api/c/matthew-henry/books.json', 'https://bible.helloao.org/api/c/john-gill/books.json', 1),
    lambda text: text.replace('"GEN",', '"ZZZ",', 1),
])
def test_source_registry_rejects_any_reviewed_record_tampering(tmp_path, mutator):
    from app.commentary.ingest.validate import load_source_registry

    with pytest.raises(ValueError, match='reviewed source record'):
        load_source_registry(_raw_registry(tmp_path, mutator(REGISTRY.read_text(encoding='utf-8'))))


def test_source_registry_rejects_symlinks_nonregular_utf8_and_oversize(tmp_path):
    from app.commentary.ingest.validate import load_source_registry

    target = tmp_path / 'target.json'
    target.write_text(REGISTRY.read_text(encoding='utf-8'), encoding='utf-8')
    link = tmp_path / 'link.json'
    link.symlink_to(target)
    with pytest.raises(ValueError):
        load_source_registry(link)
    with pytest.raises(ValueError):
        load_source_registry(tmp_path)
    bad = tmp_path / 'bad.json'
    bad.write_bytes(b'\xff')
    with pytest.raises(ValueError):
        load_source_registry(bad)
    huge = tmp_path / 'huge.json'
    huge.write_bytes(b' ' * (256 * 1024 + 1))
    with pytest.raises(ValueError):
        load_source_registry(huge)


def test_source_registry_rejects_missing_or_extra_ids_and_fields(tmp_path):
    from app.commentary.ingest.validate import load_source_registry

    base = json.loads(REGISTRY.read_text(encoding='utf-8'))
    cases = []
    missing_id = dict(base)
    missing_id.pop('john-gill')
    cases.append(missing_id)
    extra_id = dict(base)
    extra_id['tyndale'] = base['john-gill']
    cases.append(extra_id)
    missing_field = json.loads(json.dumps(base))
    missing_field['john-gill'].pop('title')
    cases.append(missing_field)
    extra_field = json.loads(json.dumps(base))
    extra_field['john-gill']['extra'] = 'not allowed'
    cases.append(extra_field)
    for index, raw in enumerate(cases):
        path = tmp_path / f'case-{index}.json'
        path.write_text(json.dumps(raw), encoding='utf-8')
        with pytest.raises(ValueError):
            load_source_registry(path)


@pytest.mark.parametrize('replacement', [
    'https://bible.helloao.org/api/c/matthew-henry/books.json?unsafe=yes',
    'https://bible.helloao.org/api/c/matthew-henry/books.json#unsafe',
])
def test_source_registry_rejects_upstream_url_queries_and_fragments(tmp_path, replacement):
    from app.commentary.ingest.validate import load_source_registry

    text = REGISTRY.read_text(encoding='utf-8').replace(
        'https://bible.helloao.org/api/c/matthew-henry/books.json', replacement, 1,
    )
    with pytest.raises(ValueError):
        load_source_registry(_raw_registry(tmp_path, text))


@pytest.mark.parametrize('replacement', [
    ' https://bible.helloao.org/api/c/matthew-henry/books.json',
    'https://bible.helloao.org/api/c/matthew-henry/books.json\t',
    'https://bible.helloao.org/api/c/matthew-henry/books.json\u00a0',
    'https://bible.helloao.org:99999/api/c/matthew-henry/books.json',
    'https://bible.helloao.org:not-a-port/api/c/matthew-henry/books.json',
])
def test_source_registry_rejects_whitespace_and_invalid_url_ports(tmp_path, replacement):
    from app.commentary.ingest.validate import load_source_registry

    text = REGISTRY.read_text(encoding='utf-8').replace(
        'https://bible.helloao.org/api/c/matthew-henry/books.json', replacement, 1,
    )
    with pytest.raises(ValueError):
        load_source_registry(_raw_registry(tmp_path, text))


def test_source_registry_rejects_malformed_json_constants_and_overlong_values(tmp_path):
    from app.commentary.ingest.validate import load_source_registry

    for index, text in enumerate(('{', '{"value": NaN}')):
        with pytest.raises(ValueError):
            load_source_registry(_raw_registry(tmp_path, text))
    raw = json.loads(REGISTRY.read_text(encoding='utf-8'))
    raw['john-gill']['title'] = 'x' * 201
    with pytest.raises(ValueError):
        load_source_registry(_raw_registry(tmp_path, json.dumps(raw)))
