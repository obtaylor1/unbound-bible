from dataclasses import FrozenInstanceError

import pytest

from app.library.ingest.normalize import normalize_verse


def test_normalizes_song_of_songs_without_rewriting_scripture_punctuation():
    verse = normalize_verse(
        '  Song of Songs  ', 2, 1, "  Let him kiss me—with the kisses of his mouth;  ",
    )

    assert verse.work_id == 'song-of-solomon'
    assert verse.source_book == 'Song of Songs'
    assert verse.chapter == 2
    assert verse.verse == 1
    assert verse.text == 'Let him kiss me—with the kisses of his mouth;'
    assert verse.source_locator is None


@pytest.mark.parametrize('chapter, verse', [
    (0, 1), (1, 0), (True, 1), (1, False), (1.0, 1), (1, 1.0), ('1', 1), (1, '1'),
])
def test_rejects_non_positive_or_non_integer_positions(chapter, verse):
    with pytest.raises(ValueError, match='positive integers'):
        normalize_verse('Genesis', chapter, verse, 'In the beginning')


@pytest.mark.parametrize('source_book, expected_work_id', [
    ('Genesis', 'genesis'),
    ('genesis', 'genesis'),
    ('song-of-solomon', 'song-of-solomon'),
    ('Song of Songs', 'song-of-solomon'),
    ('Meqabyan 1', '1-meqabyan'),
    ('I Meqabyan', '1-meqabyan'),
    ('1 Maccabees', '1-maccabees'),
    ('I Maccabees', '1-maccabees'),
])
def test_resolves_canonical_ids_names_and_aliases_without_conflating_books(source_book, expected_work_id):
    assert normalize_verse(source_book, 1, 1, 'A verse').work_id == expected_work_id


def test_rejects_unknown_or_blank_source_book():
    for source_book in ('', '   ', 'Unknown Canonical Work'):
        with pytest.raises(ValueError, match='Unknown source book'):
            normalize_verse(source_book, 1, 1, 'A verse')


@pytest.mark.parametrize('field', ['source_book', 'text'])
@pytest.mark.parametrize('value', [None, 1, b'Genesis'])
def test_rejects_non_string_book_and_text(field, value):
    args = {'source_book': 'Genesis', 'chapter': 1, 'verse': 1, 'text': 'A verse'}
    args[field] = value

    with pytest.raises(ValueError, match=f'{field} must be a string'):
        normalize_verse(**args)


def test_normalizes_combining_characters_and_unicode_whitespace():
    verse = normalize_verse(
        ' Song\u00a0of\u2002Songs ', 1, 1,
        '  cafe\u0301\n\u2009and\u202fgrace\u00a0 ',
    )

    assert verse.source_book == 'Song of Songs'
    assert verse.text == 'caf\u00e9 and grace'


def test_preserves_legitimate_comparison_and_ampersand_text():
    verse = normalize_verse('Genesis', 1, 1, 'For 2 < 3, and A & B remain.')

    assert verse.text == 'For 2 < 3, and A & B remain.'


@pytest.mark.parametrize('markup', [
    '<em>word</em>',
    '<SCRIPT\n type="text/javascript">word</SCRIPT>',
    '<style>body { color: red; }</style>',
    '<!DOCTYPE scripture>',
    '<!-- a multiline\ncomment -->',
    '<?xml version="1.0"?>word',
])
def test_rejects_html_and_xml_markup_instead_of_stripping_it(markup):
    with pytest.raises(ValueError, match='markup'):
        normalize_verse('Genesis', 1, 1, markup)


@pytest.mark.parametrize('text', ['', '  \u00a0\n\u2009  '])
def test_rejects_empty_normalized_text(text):
    with pytest.raises(ValueError, match='text must not be empty'):
        normalize_verse('Genesis', 1, 1, text)


def test_normalizes_explicit_source_locator_and_retains_none_when_omitted():
    with_locator = normalize_verse(
        'Genesis', 1, 1, 'In the beginning', ' source\u00a0file\n: 1 '
    )
    without_locator = normalize_verse('Genesis', 1, 1, 'In the beginning')

    assert with_locator.source_locator == 'source file : 1'
    assert without_locator.source_locator is None


@pytest.mark.parametrize('locator', ['', ' \u00a0 ', 1, 'source\x00file', '<ref>1</ref>'])
def test_rejects_invalid_source_locator(locator):
    with pytest.raises(ValueError, match='source_locator'):
        normalize_verse('Genesis', 1, 1, 'In the beginning', locator)


def test_checksums_are_deterministic_and_sensitive_to_staged_values():
    original = normalize_verse('Genesis', 1, 1, 'In the beginning', 'gen.usfm:1:1')
    same = normalize_verse('Genesis', 1, 1, 'In the beginning', 'gen.usfm:1:1')
    changed_text = normalize_verse('Genesis', 1, 1, 'In the end', 'gen.usfm:1:1')
    changed_locator = normalize_verse('Genesis', 1, 1, 'In the beginning', 'gen.usfm:1:2')
    changed_position = normalize_verse('Genesis', 1, 2, 'In the beginning', 'gen.usfm:1:1')

    assert original.text_checksum == same.text_checksum
    assert original.row_checksum == same.row_checksum
    assert original.text_checksum != changed_text.text_checksum
    assert original.row_checksum != changed_text.row_checksum
    assert original.row_checksum != changed_locator.row_checksum
    assert original.row_checksum != changed_position.row_checksum
    assert len(original.row_checksum) == len(original.text_checksum) == 64


def test_row_checksum_uses_unambiguous_field_serialization():
    first = normalize_verse('Genesis', 1, 1, 'alpha:beta', 'gamma')
    second = normalize_verse('Genesis', 1, 1, 'alpha', 'beta:gamma')
    third = normalize_verse('Genesis', 1, 1, 'alpha:beta:gamma', None)

    assert first.row_checksum != second.row_checksum
    assert first.row_checksum != third.row_checksum


def test_normalized_verse_is_frozen():
    verse = normalize_verse('Genesis', 1, 1, 'In the beginning')

    with pytest.raises(FrozenInstanceError):
        verse.text = 'Changed'
