from dataclasses import FrozenInstanceError

import pytest

from app.library.ingest import types as ingest_types
from app.library.ingest.normalize import normalize_verse
from app.library.ingest.types import NormalizedVerse


def _direct_verse(**overrides):
    values = {
        'work_id': 'genesis',
        'source_book': 'Genesis',
        'chapter': 1,
        'verse': 1,
        'text': 'In the beginning',
        'source_locator': None,
    }
    values.update(overrides)
    return NormalizedVerse(**values)


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


def test_preserves_legitimate_comparison_ampersand_and_non_tag_angle_text():
    verse = normalize_verse(
        'Genesis', 1, 1,
        'For 2 < 3, 2 < x > 1, <1> is not a tag, <x is unfinished, and A & B remain.',
    )

    assert verse.text == (
        'For 2 < 3, 2 < x > 1, <1> is not a tag, <x is unfinished, and A & B remain.'
    )


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


@pytest.mark.parametrize('markup', [
    '<_verse>word</_verse>',
    '</_verse>',
    '<ns:verse source="import">word</ns:verse>',
    '<π/>',
    '<ሕግ n="1">word</ሕግ>',
])
def test_rejects_xml_tags_with_all_valid_name_start_forms_in_text(markup):
    with pytest.raises(ValueError, match='markup'):
        normalize_verse('Genesis', 1, 1, markup)


@pytest.mark.parametrize('markup', [
    '<_source/>',
    '</_source>',
    '<ns:source path="file"/>',
    '<π source="file"/>',
    '<ምንጭ>file</ምንጭ>',
])
def test_rejects_xml_tags_with_all_valid_name_start_forms_in_locator(markup):
    with pytest.raises(ValueError, match='source_locator.*markup'):
        normalize_verse('Genesis', 1, 1, 'In the beginning', markup)


@pytest.mark.parametrize('markup', [
    '<img/src=x>',
    '<input/disabled>',
    '<br/ >',
    '<π/attribute>',
    '<ns:verse/weird attribute contents>',
])
def test_rejects_tag_starts_with_a_later_closing_angle_regardless_of_contents(markup):
    with pytest.raises(ValueError, match='markup'):
        normalize_verse('Genesis', 1, 1, markup)


@pytest.mark.parametrize('markup', [
    '<!-- unfinished',
    '<!DECLARATION unfinished',
    '<![CDATA[unfinished',
    '<!DOCTYPE scripture',
    '<?xml version="1.0"',
])
def test_rejects_unterminated_markup_declaration_openers(markup):
    with pytest.raises(ValueError, match='markup'):
        normalize_verse('Genesis', 1, 1, markup)


def test_markup_scanner_has_one_bounded_name_start_check_per_candidate(monkeypatch):
    candidate_count = 20_000
    safe_text = '<x' * candidate_count
    calls = 0
    original = ingest_types._is_xml_name_start

    def counting_name_start(character):
        nonlocal calls
        calls += 1
        return original(character)

    monkeypatch.setattr(ingest_types, '_is_xml_name_start', counting_name_start)

    assert ingest_types.contains_markup(safe_text) is False
    assert calls == candidate_count


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


@pytest.mark.parametrize('field', ['source_book', 'text', 'source_locator'])
def test_rejects_lone_unicode_surrogates_before_returning_a_verse(field):
    values = {
        'source_book': 'Genesis',
        'chapter': 1,
        'verse': 1,
        'text': 'In the beginning',
        'source_locator': None,
    }
    values[field] = 'unsafe\ud800value'

    with pytest.raises(ValueError, match=f'{field}.*surrogate'):
        normalize_verse(**values)


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


def test_row_checksum_includes_source_label_while_text_checksum_is_text_only():
    canonical_name = normalize_verse('Genesis', 1, 1, 'In the beginning')
    canonical_id = normalize_verse('genesis', 1, 1, 'In the beginning')

    assert canonical_name.text_checksum == canonical_id.text_checksum
    assert canonical_name.row_checksum != canonical_id.row_checksum


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


@pytest.mark.parametrize(('overrides', 'message'), [
    ({'work_id': 'unknown-work'}, 'known canonical work'),
    ({'source_book': 1}, 'source_book must be a string'),
    ({'source_book': ''}, 'source_book must not be empty'),
    ({'source_book': 'Genesis\ud800'}, 'source_book.*surrogate'),
    ({'chapter': True}, 'positive integers'),
    ({'chapter': 0}, 'positive integers'),
    ({'verse': '1'}, 'positive integers'),
    ({'text': 1}, 'text must be a string'),
    ({'text': ''}, 'text must not be empty'),
    ({'text': '<img/src=x>'}, 'text.*markup'),
    ({'text': 'unsafe\x00text'}, 'text.*control'),
    ({'text': 'unsafe\ud800text'}, 'text.*surrogate'),
    ({'source_locator': 1}, 'source_locator must be a string'),
    ({'source_locator': ''}, 'source_locator must not be empty'),
    ({'source_locator': '<_source>'}, 'source_locator.*markup'),
    ({'source_locator': 'unsafe\x00locator'}, 'source_locator.*control'),
    ({'source_locator': 'unsafe\ud800locator'}, 'source_locator.*surrogate'),
])
def test_direct_construction_rejects_invalid_staging_rows(overrides, message):
    with pytest.raises(ValueError, match=message):
        _direct_verse(**overrides)


@pytest.mark.parametrize(('field', 'value'), [
    ('source_book', ' Genesis '),
    ('text', 'cafe\u0301'),
    ('text', 'two  spaces'),
    ('source_locator', ' source\nline '),
])
def test_direct_construction_requires_already_normalized_strings(field, value):
    with pytest.raises(ValueError, match=f'{field}.*normalized'):
        _direct_verse(**{field: value})


def test_successfully_created_direct_verse_has_total_checksum_properties():
    verse = _direct_verse(
        work_id='1-maccabees',
        source_book='1 Maccabees',
        text='A safe supplementary verse — ሰላም',
        source_locator='source:𐀀',
    )

    assert len(verse.text_checksum) == 64
    assert len(verse.row_checksum) == 64


@pytest.mark.parametrize(('work_id', 'source_book'), [
    ('song-of-solomon', 'song-of-solomon'),
    ('1-meqabyan', '1-meqabyan'),
    ('1-maccabees', '1-maccabees'),
])
def test_direct_construction_accepts_exact_canonical_work_id_labels(work_id, source_book):
    verse = _direct_verse(work_id=work_id, source_book=source_book)

    assert verse.work_id == work_id
    assert verse.source_book == source_book


def test_direct_construction_rejects_source_book_resolving_to_a_different_work():
    with pytest.raises(ValueError, match='source_book.*resolve.*work_id'):
        _direct_verse(work_id='genesis', source_book='Exodus')


@pytest.mark.parametrize('source_book', ['Totally Unknown', 'GEN'])
def test_direct_construction_rejects_unresolved_adapter_book_labels(source_book):
    with pytest.raises(ValueError, match='source_book.*known canonical work'):
        _direct_verse(work_id='genesis', source_book=source_book)
