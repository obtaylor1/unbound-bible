import json
import os
from pathlib import Path
import threading

import pytest


FIXTURE = Path(__file__).parents[1] / 'fixtures' / 'helloao-genesis-1.json'


def _bundle():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def _write_bundle(path, bundle=None):
    path.write_text(json.dumps(bundle if bundle is not None else _bundle(), ensure_ascii=False), encoding='utf-8')
    return path


def _write_raw_bundle(path, text):
    path.write_text(text, encoding='utf-8')
    return path


def _load(path, book_map=None):
    from app.commentary.ingest.adapter import load_helloao_bundle

    return list(load_helloao_bundle(path, {'GEN': 'genesis'} if book_map is None else book_map))


def test_loads_all_commentary_scopes_in_source_order_with_stable_checksums():
    rows = _load(FIXTURE)

    assert [(row.entry_type, row.chapter, row.verse_start, row.verse_end) for row in rows] == [
        ('book_intro', None, None, None),
        ('chapter_intro', 1, None, None),
        ('verse', 1, 1, 1),
        ('verse_range', 1, 2, 3),
    ]
    assert [row.position for row in rows] == [0, 1, 2, 3]
    assert [row.source_locator for row in rows] == [
        'helloao:matthew-henry:GEN:book-intro',
        'helloao:matthew-henry:GEN:chapter:1:intro',
        'helloao:matthew-henry:GEN:chapter:1:verse:1',
        'helloao:matthew-henry:GEN:chapter:1:verse:2-3',
    ]
    assert rows[3].body == 'First paragraph.\n\nSecond paragraph.'
    assert [row.row_checksum for row in rows] == [
        '1b1f5a1b21304184941c67fda31c67f6743bda9c6dd3e43da7baebd279a858e2',
        '02814837f7227d2688479a5edc56746e757fde116041716c228984f95bf096b5',
        '122d9256c07cb817afa3d8a03c88818d15bf349af04eb4ec503d51fb3a2beeae',
        '0aa9975b176510fa49eca4b51a25d20fde09bedd91f1134d78869f2b22b7b09e',
    ]


def test_repeat_loads_are_identical():
    first = _load(FIXTURE)
    second = _load(FIXTURE)

    assert first == second
    assert [row.row_checksum for row in first] == [row.row_checksum for row in second]


@pytest.mark.parametrize('number', [True, 1.0, '1', '01', '1-01', '0-1', '1-0', '3-2', '1 - 2', '1–2'])
def test_rejects_malformed_or_noncanonical_verse_numbers(tmp_path, number):
    bundle = _bundle()
    bundle['books'][0]['chapters'][0]['content'][0]['number'] = number

    with pytest.raises(ValueError, match='number'):
        _load(_write_bundle(tmp_path / 'bundle.json', bundle))


def test_normalizes_oversized_range_integer_errors(tmp_path):
    bundle = _bundle()
    bundle['books'][0]['chapters'][0]['content'][0]['number'] = f"1-{'9' * 10_000}"

    with pytest.raises(ValueError, match='content number'):
        _load(_write_bundle(tmp_path / 'bundle.json', bundle))


def test_single_value_range_is_normalized_to_a_verse(tmp_path):
    bundle = _bundle()
    bundle['books'][0]['chapters'][0]['content'][0]['number'] = '1-1'

    rows = _load(_write_bundle(tmp_path / 'bundle.json', bundle))

    assert rows[2].entry_type == 'verse'
    assert (rows[2].verse_start, rows[2].verse_end) == (1, 1)


@pytest.mark.parametrize('replacement', [
    {},
    {'commentary': {'id': 'x'}},
    {'commentary': {'id': 'x'}, 'books': [], 'extra': []},
])
def test_rejects_nonexact_top_level_keys(tmp_path, replacement):
    with pytest.raises(ValueError, match='top-level'):
        _load(_write_bundle(tmp_path / 'bundle.json', replacement))


@pytest.mark.parametrize(
    'mutate',
    [
        lambda text: text.replace(
            '"commentary": {"id": "matthew-henry"}',
            '"commentary": {"id": "matthew-henry"}, "commentary": {"id": "duplicate"}',
            1,
        ),
        lambda text: text.replace('"id": "GEN",', '"id": "GEN", "id": "GEN",', 1),
        lambda text: text.replace(
            '"number": 1,\n          "introduction"',
            '"number": 1, "number": 1,\n          "introduction"',
            1,
        ),
        lambda text: text.replace('"type": "verse", "number": 1,', '"type": "verse", "type": "verse", "number": 1,', 1),
    ],
    ids=['top-level', 'book', 'chapter', 'content'],
)
def test_rejects_duplicate_json_object_members_at_every_nesting_level(tmp_path, mutate):
    text = FIXTURE.read_text(encoding='utf-8')

    with pytest.raises(ValueError, match='duplicate JSON key'):
        _load(_write_raw_bundle(tmp_path / 'duplicate.json', mutate(text)))


@pytest.mark.parametrize('field, value', [
    ('introduction', []), ('numberOfChapters', True), ('chapters', {}),
])
def test_rejects_wrong_book_child_types(tmp_path, field, value):
    bundle = _bundle()
    bundle['books'][0][field] = value

    with pytest.raises(ValueError):
        _load(_write_bundle(tmp_path / 'bundle.json', bundle))


def test_rejects_unknown_book_keys_and_chapter_key_shapes(tmp_path):
    bundle = _bundle()
    bundle['books'][0]['unexpected'] = 'value'
    with pytest.raises(ValueError, match='keys'):
        _load(_write_bundle(tmp_path / 'book.json', bundle))

    bundle = _bundle()
    del bundle['books'][0]['chapters'][0]['introduction']
    with pytest.raises(ValueError, match='keys'):
        _load(_write_bundle(tmp_path / 'chapter.json', bundle))


@pytest.mark.parametrize('book_map', [{}, {'GEN': 'not-a-work'}, {'GEN ': 'genesis', 'GEN': 'genesis'}])
def test_rejects_empty_unknown_or_normalization_ambiguous_book_maps(book_map):
    with pytest.raises(ValueError):
        _load(FIXTURE, book_map)


def test_rejects_book_map_source_ids_that_resolve_to_the_same_work():
    with pytest.raises(ValueError, match='canonical work'):
        _load(FIXTURE, {'GEN': 'genesis', 'GenesisAlias': 'genesis'})


def test_rejects_unmapped_and_duplicate_book_ids(tmp_path):
    bundle = _bundle()
    bundle['books'][0]['id'] = 'EXO'
    with pytest.raises(ValueError, match='book_map'):
        _load(_write_bundle(tmp_path / 'unmapped.json', bundle))

    bundle = _bundle()
    bundle['books'].append(bundle['books'][0])
    with pytest.raises(ValueError, match='duplicate'):
        _load(_write_bundle(tmp_path / 'duplicate.json', bundle))


@pytest.mark.parametrize('chapters', [
    [],
    [{"number": 2, "introduction": "", "content": []}],
    [
        {"number": 1, "introduction": "", "content": []},
        {"number": 1, "introduction": "", "content": []},
    ],
])
def test_rejects_inconsistent_or_nonsequential_chapters(tmp_path, chapters):
    bundle = _bundle()
    bundle['books'][0]['chapters'] = chapters
    with pytest.raises(ValueError):
        _load(_write_bundle(tmp_path / 'bundle.json', bundle))


@pytest.mark.parametrize('content', [[], [''], [1], 'text'])
def test_rejects_empty_or_nonstring_content_fragments(tmp_path, content):
    bundle = _bundle()
    bundle['books'][0]['chapters'][0]['content'][0]['content'] = content
    with pytest.raises(ValueError):
        _load(_write_bundle(tmp_path / 'bundle.json', bundle))


@pytest.mark.parametrize('bad_text', [
    '<em>markup</em>', '<!DOCTYPE commentary>', '\x00', '\ud800',
])
def test_rejects_markup_declarations_controls_and_surrogates(tmp_path, bad_text):
    bundle = _bundle()
    bundle['books'][0]['introduction'] = bad_text
    with pytest.raises(ValueError):
        _load(_write_bundle(tmp_path / 'bundle.json', bundle))


def test_rejects_control_characters_in_an_empty_introduction(tmp_path):
    bundle = _bundle()
    bundle['books'][0]['introduction'] = ' \t '

    with pytest.raises(ValueError, match='control'):
        _load(_write_bundle(tmp_path / 'bundle.json', bundle))


def test_allows_plaintext_less_than_comparisons(tmp_path):
    bundle = _bundle()
    bundle['books'][0]['chapters'][0]['content'][0]['content'] = ['age < 10 is young.']

    assert _load(_write_bundle(tmp_path / 'bundle.json', bundle))[2].body == 'age < 10 is young.'


def test_rejects_duplicate_verse_identity_even_when_positions_differ(tmp_path):
    bundle = _bundle()
    bundle['books'][0]['chapters'][0]['content'].append(
        {'type': 'verse', 'number': 1, 'content': ['Repeated.']},
    )

    with pytest.raises(ValueError, match='duplicate'):
        _load(_write_bundle(tmp_path / 'bundle.json', bundle))


def test_rejects_invalid_later_record_before_any_rows_are_observable(tmp_path):
    from app.commentary.ingest.adapter import load_helloao_bundle

    bundle = _bundle()
    bundle['books'][0]['chapters'][0]['content'].append(
        {'type': 'verse', 'number': 4, 'content': ['<em>invalid final row</em>']},
    )
    observed = []

    with pytest.raises(ValueError, match='markup'):
        for row in load_helloao_bundle(_write_bundle(tmp_path / 'invalid-later.json', bundle), {'GEN': 'genesis'}):
            observed.append(row)

    assert observed == []


def test_rejects_book_labels_that_do_not_match_the_mapped_work(tmp_path):
    with pytest.raises(ValueError, match='does not match'):
        _load(_write_bundle(tmp_path / 'bundle.json'), {'GEN': 'exodus'})


def test_normalized_entry_enforces_coordinates_string_limits_and_checksum():
    from app.commentary.ingest.types import NormalizedCommentaryEntry

    entry = NormalizedCommentaryEntry(
        work_id='genesis', chapter=1, verse_start=1, verse_end=1,
        entry_type='verse', heading=' A heading ', body='One.   \n\n\nTwo.',
        source_locator=' helloao:example:GEN ', position=0,
    )

    assert entry.heading == 'A heading'
    assert entry.body == 'One.\n\nTwo.'
    assert entry.source_locator == 'helloao:example:GEN'
    assert entry.row_checksum == '7590cb657483db714b64f90c7cf31927127dd700cc5f5fafdf7ad0ab6fd59ff5'

    with pytest.raises(ValueError):
        NormalizedCommentaryEntry('unknown', None, None, None, 'book_intro', None, 'body', 'source', 0)
    with pytest.raises(ValueError):
        NormalizedCommentaryEntry('genesis', 1, None, None, 'verse', None, 'body', 'source', 0)
    with pytest.raises(ValueError):
        NormalizedCommentaryEntry('genesis', None, None, None, 'book_intro', 'x' * 501, 'body', 'source', 0)
    with pytest.raises(ValueError):
        NormalizedCommentaryEntry('genesis', None, None, None, 'book_intro', None, 'x' * 100001, 'source', 0)
    with pytest.raises(ValueError):
        NormalizedCommentaryEntry('genesis', None, None, None, 'book_intro', None, 'body', 'x' * 2049, 0)
    with pytest.raises(ValueError):
        NormalizedCommentaryEntry('genesis', None, None, None, 'book_intro', None, 'body', 'source', True)
    with pytest.raises(ValueError):
        NormalizedCommentaryEntry('genesis', 1, 1, 1, 'verse_range', None, 'body', 'source', 0)
    with pytest.raises(ValueError):
        NormalizedCommentaryEntry('genesis', None, None, None, [], None, 'body', 'source', 0)


def test_body_allows_comparison_prose_that_is_not_markup():
    from app.commentary.ingest.types import normalize_body

    assert normalize_body('both 1<x and y>0 comparisons hold') == 'both 1<x and y>0 comparisons hold'


@pytest.mark.parametrize('prose', ['x < y > z', 'both 1 < x and y > 0'])
def test_body_allows_spaced_comparison_prose(prose):
    from app.commentary.ingest.types import normalize_body

    assert normalize_body(prose) == prose


@pytest.mark.parametrize('tag', [
    'abbr', 'bdi', 'bdo', 'big', 'blink', 'center', 'dfn', 'dir', 'font', 'kbd', 'marquee',
    'nobr', 'noembed', 'noframes', 'param', 'plaintext', 'portal', 'rp', 'rt', 'ruby', 'samp',
    'search', 'strike', 'tt', 'var', 'xmp', 'image',
])
def test_body_rejects_complete_standard_tag_set_even_when_embedded(tag):
    from app.commentary.ingest.types import normalize_body

    with pytest.raises(ValueError, match='markup'):
        normalize_body(f'a<{tag}>b')


@pytest.mark.parametrize('payload', [
    '<img src=x onerror=alert(1)>', '<svg/>', '<note/>', '<note>', '<hr>', '<h1>heading',
    '<note key="value">', '<unknown>text</unknown>',
])
def test_body_rejects_standard_and_arbitrary_angle_token_markup(payload):
    from app.commentary.ingest.types import normalize_body

    with pytest.raises(ValueError, match='markup'):
        normalize_body(payload)


def test_body_rejects_many_unknown_angle_tokens_without_repeated_suffix_searches():
    from app.commentary.ingest.types import normalize_body

    with pytest.raises(ValueError, match='markup'):
        normalize_body('<note>' * 2_000)


def test_body_applies_raw_safety_ceiling_before_markup_scanning():
    from app.commentary.ingest.types import _MAX_RAW_BODY_CHARS, normalize_body

    with pytest.raises(ValueError, match='raw input safety'):
        normalize_body('<note>' * (_MAX_RAW_BODY_CHARS // 2))


def test_body_preserves_unicode_line_and_paragraph_separators():
    from app.commentary.ingest.types import normalize_body

    assert normalize_body('One\u2028Two\u2029Three') == 'One\nTwo\n\nThree'


def test_rejects_invalid_files_json_and_utf8(tmp_path):
    missing = tmp_path / 'missing.json'
    with pytest.raises(ValueError, match='regular file'):
        _load(missing)

    malformed = tmp_path / 'malformed.json'
    malformed.write_text('{', encoding='utf-8')
    with pytest.raises(ValueError, match='JSON'):
        _load(malformed)

    invalid_utf8 = tmp_path / 'invalid.json'
    invalid_utf8.write_bytes(b'\x80')
    with pytest.raises(ValueError, match='UTF-8'):
        _load(invalid_utf8)


def test_rejects_symlink_and_nonregular_bundle_paths(tmp_path):
    source = _write_bundle(tmp_path / 'source.json')
    link = tmp_path / 'bundle-link.json'
    link.symlink_to(source)

    with pytest.raises(ValueError, match='regular file'):
        _load(link)
    with pytest.raises(ValueError, match='regular file'):
        _load(tmp_path)


def test_rejects_fifo_without_waiting_for_a_writer(tmp_path):
    if not hasattr(os, 'mkfifo'):
        pytest.skip('mkfifo is unavailable on this platform')
    fifo = tmp_path / 'bundle.fifo'
    os.mkfifo(fifo)
    result = []

    def load_fifo():
        try:
            _load(fifo)
        except ValueError:
            result.append('rejected')

    worker = threading.Thread(target=load_fifo, daemon=True)
    worker.start()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert result == ['rejected']


def test_rejects_path_replaced_between_lstat_and_open(tmp_path, monkeypatch):
    from app.commentary.ingest import adapter

    path = _write_bundle(tmp_path / 'bundle.json')
    replacement = _write_bundle(tmp_path / 'replacement.json')
    original_open = os.open

    def replace_then_open(target, flags):
        os.replace(replacement, path)
        return original_open(target, flags)

    monkeypatch.setattr(adapter.os, 'open', replace_then_open)

    with pytest.raises(ValueError, match='regular file'):
        _load(path)


def test_accepts_a_bundle_exactly_at_the_size_limit(tmp_path):
    from app.commentary.ingest.adapter import _MAX_BUNDLE_BYTES

    payload = json.dumps(_bundle()).encode('utf-8')
    path = tmp_path / 'exact.json'
    path.write_bytes(payload + b' ' * (_MAX_BUNDLE_BYTES - len(payload)))

    assert len(_load(path)) == 4


def test_rejects_growth_observed_while_reading(tmp_path, monkeypatch):
    from app.commentary.ingest import adapter

    path = _write_bundle(tmp_path / 'bundle.json')
    monkeypatch.setattr(adapter.os, 'read', lambda _fd, _size: b'x' * (adapter._MAX_BUNDLE_BYTES + 1))

    with pytest.raises(ValueError, match='5 MiB'):
        _load(path)


@pytest.mark.parametrize('constant', [float('nan'), float('inf')], ids=['NaN', 'Infinity'])
def test_rejects_nonstandard_json_constants_even_in_ignored_metadata(tmp_path, constant):
    bundle = _bundle()
    bundle['commentary']['metadata'] = constant

    with pytest.raises(ValueError, match='JSON constant'):
        _load(_write_bundle(tmp_path / 'constant.json', bundle))


def test_normalizes_deep_json_recursion_errors(tmp_path):
    nested = '[' * 100_000 + ']' * 100_000
    path = _write_raw_bundle(
        tmp_path / 'deep.json', '{"commentary":{"id":"x"},"books":' + nested + '}',
    )

    with pytest.raises(ValueError, match='valid JSON'):
        _load(path)


def test_normalizes_raw_oversized_json_integer_errors(tmp_path):
    path = _write_raw_bundle(
        tmp_path / 'huge-integer.json',
        '{"commentary":{"id":"x"},"books":' + '9' * 10_000 + '}',
    )

    with pytest.raises(ValueError, match='valid JSON'):
        _load(path)


def test_accepts_an_optional_introduction_at_the_exact_body_limit(tmp_path):
    bundle = _bundle()
    bundle['books'][0]['introduction'] = 'x' * 100_000

    rows = _load(_write_bundle(tmp_path / 'maximum.json', bundle))

    assert rows[0].body == 'x' * 100_000


def test_rejects_an_optional_introduction_over_the_body_limit(tmp_path):
    bundle = _bundle()
    bundle['books'][0]['introduction'] = 'x' * 100_001

    with pytest.raises(ValueError, match='100000'):
        _load(_write_bundle(tmp_path / 'over-limit.json', bundle))


def test_rejects_oversized_file_before_reading(tmp_path):
    path = tmp_path / 'large.json'
    path.write_bytes(b' ' * (5 * 1024 * 1024 + 1))

    with pytest.raises(ValueError, match='5 MiB'):
        _load(path)
