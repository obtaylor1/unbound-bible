import json
import os
from dataclasses import replace
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
            'genesis': {'chapters': 1, 'entries': 1},
            'exodus': {'chapters': 1, 'entries': 1},
        },
    }
    assert result.error_count == 0
    assert result.warning_count == 4
    assert result.publishable is True
    assert [finding.code for finding in result.findings] == [
        'missing_book_intro', 'missing_chapter_intro',
        'missing_book_intro', 'missing_chapter_intro',
    ]


@pytest.mark.parametrize('rows, expected, code', [
    ([], {'genesis'}, 'no_rows'),
    ([_row()], {'exodus'}, 'missing_expected_book'),
    ([_row('exodus')], {'genesis'}, 'unexpected_book'),
    ([_row(), _row(position=99)], {'genesis'}, 'duplicate_identity'),
    ([_row(start=1, end=2, entry_type='verse_range'), _row(start=2, end=3, entry_type='verse_range', position=2)], {'genesis'}, 'overlapping_coverage'),
])
def test_blocking_validation_findings(rows, expected, code):
    from app.commentary.ingest.validate import validate_commentary

    result = validate_commentary(rows, expected)

    assert code in {finding.code for finding in result.findings}
    assert result.publishable is False


def test_duplicate_ignores_position_and_range_boundaries_are_precise():
    from app.commentary.ingest.validate import validate_commentary

    touching = validate_commentary([
        _row(start=1, end=2, entry_type='verse_range'),
        _row(start=3, end=4, entry_type='verse_range', position=8),
    ], {'genesis'})
    repeated = validate_commentary([_row(), _row(position=900)], {'genesis'})

    assert 'overlapping_coverage' not in {f.code for f in touching.findings}
    assert 'duplicate_identity' in {f.code for f in repeated.findings}


def test_adversarial_rows_are_validation_errors_not_crashes():
    from app.commentary.ingest.validate import validate_commentary

    invalid = _row()
    object.__setattr__(invalid, 'body', '   ')
    result = validate_commentary([object(), invalid], {'genesis'})

    assert result.error_count >= 2
    assert 'invalid_row_type' in {finding.code for finding in result.findings}
    assert 'unsafe_normalized_row' in {finding.code for finding in result.findings}


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

    prior = {'books': 1, 'chapters': 1, 'entries': 1, 'by_work': {'genesis': {'chapters': 1, 'entries': 1}}}

    assert validate_commentary([_row()], {'genesis'}, prior).publishable


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


def test_source_registry_loads_exact_live_catalog_in_stable_order():
    from app.commentary.ingest.validate import load_source_registry

    registry = load_source_registry(REGISTRY)

    assert list(registry) == [
        'matthew-henry', 'john-gill', 'adam-clarke', 'jamieson-fausset-brown', 'keil-delitzsch',
    ]
    assert registry['matthew-henry'].source_checksum == 'ad2850450a1e5c0546c275f4bd09b9325ae47424d83311120ca7ced5724c4bc8'
    assert registry['john-gill'].expected_book_count == 66
    assert registry['adam-clarke'].expected_book_count == 57
    assert registry['jamieson-fausset-brown'].abbreviation == 'JFB'
    assert registry['keil-delitzsch'].expected_book_count == 39
    assert registry['keil-delitzsch'].expected_source_books[-1] == 'MAL'


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
    lambda text: text.replace('https://bible.helloao.org/', 'https://user:pass@bible.helloao.org/', 1),
    lambda text: text.replace('"source_checksum": "', '"source_checksum": "UPPER', 1),
    lambda text: text.replace('"expected_book_count": 65', '"expected_book_count": 64', 1),
    lambda text: text.replace('"GEN",', '"GEN","GEN",', 1),
    lambda text: text.replace('"GEN",', '"gen",', 1),
])
def test_source_registry_rejects_hostile_metadata(tmp_path, mutator):
    from app.commentary.ingest.validate import load_source_registry

    with pytest.raises(ValueError):
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


def test_source_registry_rejects_malformed_json_constants_and_overlong_values(tmp_path):
    from app.commentary.ingest.validate import load_source_registry

    for index, text in enumerate(('{', '{"value": NaN}')):
        with pytest.raises(ValueError):
            load_source_registry(_raw_registry(tmp_path, text))
    raw = json.loads(REGISTRY.read_text(encoding='utf-8'))
    raw['john-gill']['title'] = 'x' * 201
    with pytest.raises(ValueError):
        load_source_registry(_raw_registry(tmp_path, json.dumps(raw)))
