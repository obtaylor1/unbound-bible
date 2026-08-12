from dataclasses import FrozenInstanceError, replace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.research import event_catalog
from app.research.event_catalog import (
    EVENT_DEFINITIONS,
    EventCatalogError,
    list_events,
    resolve_between_events,
)


@pytest.fixture
def event_session():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text('''
            CREATE TABLE biblical_texts (
                id INTEGER PRIMARY KEY,
                book TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER NOT NULL,
                text TEXT NOT NULL,
                translation TEXT
            )
        '''))
        row_id = 1
        for translation in ('ASV', 'KJV'):
            rows = []
            for chapter, final_verse in ((2, 25), (3, 24), (4, 26)):
                for verse in range(1, final_verse + 1):
                    rows.append({
                        'id': row_id,
                        'book': 'Genesis',
                        'chapter': chapter,
                        'verse': verse,
                        'text': f'Genesis {chapter}:{verse} {translation}',
                        'translation': translation,
                    })
                    row_id += 1
            connection.execute(text('''
                INSERT INTO biblical_texts
                    (id, book, chapter, verse, text, translation)
                VALUES
                    (:id, :book, :chapter, :verse, :text, :translation)
            '''), rows)
    with Session(engine) as session:
        yield session


def test_release_one_definitions_are_reviewed_and_immutable():
    assert [
        (item.id, item.book, item.chapter, item.verse_start, item.verse_end)
        for item in EVENT_DEFINITIONS
    ] == [
        ('eden', 'Genesis', 2, 8, 25),
        ('eden-expulsion', 'Genesis', 3, 22, 24),
        ('cain-born', 'Genesis', 4, 1, 1),
        ('abel-born', 'Genesis', 4, 2, 2),
        ('offerings', 'Genesis', 4, 3, 5),
        ('abel-killed', 'Genesis', 4, 8, 8),
    ]
    assert all(item.aliases and item.people is not None and item.places is not None
               for item in EVENT_DEFINITIONS)
    with pytest.raises(FrozenInstanceError):
        EVENT_DEFINITIONS[0].title = 'Changed'


def test_list_events_is_source_backed_ordered_and_prefers_one_kjv_translation(
    event_session,
):
    events = list_events(event_session)

    assert [event.id for event in events] == [
        'eden', 'eden-expulsion', 'cain-born', 'abel-born', 'offerings',
        'abel-killed',
    ]
    assert {event.translation for event in events} == {'KJV'}
    assert events[0].reference == 'Genesis 2:8-25'
    assert events[2].reference == 'Genesis 4:1'
    assert all(event.source_ids for event in events)
    assert all(source_id.startswith('scripture:')
               for event in events for source_id in event.source_ids)
    assert len(events[0].source_ids) == 18


@pytest.mark.parametrize('query', [None, '', '   '])
def test_empty_search_returns_all_resolved_events(event_session, query):
    assert len(list_events(event_session, query)) == 6


@pytest.mark.parametrize(('query', 'expected'), [
    ('EDEN', ['eden', 'eden-expulsion']),
    ('garden of eden', ['eden']),
    ('Garden Life', ['eden']),
])
def test_search_normalizes_case_and_matches_titles_or_aliases(
    event_session, query, expected,
):
    assert [event.id for event in list_events(event_session, query)] == expected


def test_search_handles_apostrophes_bounds_input_and_does_not_change_data(
    event_session,
):
    assert [event.id for event in list_events(event_session, "Cain's birth")] == [
        'cain-born'
    ]
    attack = "x' OR 1=1 --" + ('z' * 10_000)
    assert list_events(event_session, attack) == []
    assert event_session.scalar(text('SELECT COUNT(*) FROM biblical_texts')) == 150


def test_between_is_inclusive_and_same_event_is_a_singleton(event_session):
    assert [event.id for event in resolve_between_events(
        event_session, 'eden-expulsion', 'abel-killed'
    )] == [
        'eden-expulsion', 'cain-born', 'abel-born', 'offerings', 'abel-killed'
    ]
    assert [event.id for event in resolve_between_events(
        event_session, 'eden', 'eden'
    )] == ['eden']


def test_between_includes_garden_event_when_requested(event_session):
    assert [event.id for event in resolve_between_events(
        event_session, 'eden', 'offerings'
    )] == ['eden', 'eden-expulsion', 'cain-born', 'abel-born', 'offerings']


@pytest.mark.parametrize(('from_id', 'to_id', 'code'), [
    ('unknown', 'eden', 'unknown_event'),
    ('eden', 'unknown', 'unknown_event'),
    ('abel-killed', 'eden', 'invalid_event_order'),
])
def test_between_rejects_unknown_ids_and_reverse_order_safely(
    event_session, from_id, to_id, code,
):
    with pytest.raises(EventCatalogError) as raised:
        resolve_between_events(event_session, from_id, to_id)

    assert raised.value.code == code
    assert from_id not in str(raised.value)
    assert to_id not in str(raised.value)


def test_between_rejects_different_ordering_groups(event_session, monkeypatch):
    other = replace(
        EVENT_DEFINITIONS[-1], id='other-group-event', ordering_group='other'
    )
    monkeypatch.setattr(
        event_catalog,
        '_DEFINITIONS_BY_ID',
        {**event_catalog._DEFINITIONS_BY_ID, other.id: other},
    )

    with pytest.raises(EventCatalogError) as raised:
        resolve_between_events(event_session, 'eden', other.id)

    assert raised.value.code == 'different_ordering_group'
    assert str(raised.value) == 'Events must belong to the same ordering group.'


def test_incomplete_declared_range_is_omitted_and_cannot_resolve(event_session):
    event_session.execute(text('''
        DELETE FROM biblical_texts
        WHERE chapter = :chapter AND verse = :verse
    '''), {'chapter': 2, 'verse': 12})

    assert 'eden' not in {event.id for event in list_events(event_session)}
    with pytest.raises(EventCatalogError) as raised:
        resolve_between_events(event_session, 'eden', 'abel-killed')
    assert raised.value.code == 'missing_passage'
    assert str(raised.value) == (
        'The requested event range is not fully available from verified scripture.'
    )


def test_untrusted_translation_cannot_back_an_event():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text('''
            CREATE TABLE biblical_texts (
                id INTEGER PRIMARY KEY, book TEXT, chapter INTEGER,
                verse INTEGER, text TEXT, translation TEXT
            )
        '''))
        connection.execute(text('''
            INSERT INTO biblical_texts VALUES
                (1, 'Genesis', 4, 1, 'Unreviewed rendering', 'UNKNOWN')
        '''))
    with Session(engine) as session:
        assert list_events(session, 'Cain') == []
