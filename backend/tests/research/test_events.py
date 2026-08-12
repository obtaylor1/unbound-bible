from dataclasses import FrozenInstanceError, replace

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
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
        connection.execute(text('''
            INSERT INTO biblical_texts
                (id, book, chapter, verse, text, translation)
            VALUES
                (151, 'Genesis', 2, 8, 'Duplicate KJV row', 'KJV')
        '''))
    with Session(engine) as session:
        yield session


def test_release_one_definitions_are_reviewed_and_immutable():
    assert EVENT_DEFINITIONS == (
        event_catalog.EventDefinition(
            'eden', 'Life in the Garden of Eden',
            'The LORD God places the man in the garden, gives the command '
            'concerning the tree, and brings the woman to him.',
            ('Eden', 'Garden life', 'Garden of Eden'),
            'Genesis', 2, 8, 25, ('adam', 'eve'), ('garden-of-eden',),
            'eden-sequence', 1,
        ),
        event_catalog.EventDefinition(
            'eden-expulsion', 'Expulsion from Eden',
            'The man and woman are sent out from the garden, and cherubim '
            'guard the way to the tree of life.',
            ('Eden expulsion', 'Expelled from Eden', 'Garden expulsion'),
            'Genesis', 3, 22, 24, ('adam', 'eve'), ('garden-of-eden',),
            'eden-sequence', 2,
        ),
        event_catalog.EventDefinition(
            'cain-born', 'Cain is born', 'Eve bears Cain.',
            ("Cain's birth", 'Birth of Cain'), 'Genesis', 4, 1, 1,
            ('adam', 'eve', 'cain'), (), 'eden-sequence', 3,
        ),
        event_catalog.EventDefinition(
            'abel-born', 'Abel is born',
            "Eve also bears Cain's brother Abel, who keeps sheep.",
            ("Abel's birth", 'Birth of Abel'), 'Genesis', 4, 2, 2,
            ('eve', 'cain', 'abel'), (), 'eden-sequence', 4,
        ),
        event_catalog.EventDefinition(
            'offerings', "Cain and Abel's offerings",
            'Cain and Abel bring offerings; the LORD regards Abel and his '
            'offering, but not Cain and his offering.',
            ('Offerings', 'Cain and Abel bring offerings'),
            'Genesis', 4, 3, 5, ('cain', 'abel'), (), 'eden-sequence', 5,
        ),
        event_catalog.EventDefinition(
            'abel-killed', 'Cain kills Abel',
            'Cain rises against Abel in the field and kills him.',
            ("Abel's death", 'Abel killed', 'Cain murders Abel'),
            'Genesis', 4, 8, 8, ('cain', 'abel'), ('field',),
            'eden-sequence', 6,
        ),
    )
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
    assert [(event.reference, event.source_ids) for event in events] == [
        ('Genesis 2:8-25', tuple(f'scripture:{row_id}' for row_id in range(83, 101))),
        ('Genesis 3:22-24', ('scripture:122', 'scripture:123', 'scripture:124')),
        ('Genesis 4:1', ('scripture:125',)),
        ('Genesis 4:2', ('scripture:126',)),
        ('Genesis 4:3-5', ('scripture:127', 'scripture:128', 'scripture:129')),
        ('Genesis 4:8', ('scripture:132',)),
    ]


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
    attack = "x' OR 1=1 --"
    assert list_events(event_session, attack) == []
    assert event_session.scalar(text('SELECT COUNT(*) FROM biblical_texts')) == 151


def test_search_strips_before_bounding_and_whitespace_only_is_empty(event_session):
    assert [event.id for event in list_events(event_session, (' ' * 500) + 'Eden')] == [
        'eden', 'eden-expulsion'
    ]
    assert len(list_events(event_session, '\u3000\t\n ')) == 6


@pytest.mark.parametrize('query', [
    'x' * 257,
    '\ufb03' * 256,
])
def test_search_rejects_overlong_normalized_queries_safely(event_session, query):
    with pytest.raises(EventCatalogError) as raised:
        list_events(event_session, query)

    assert raised.value.code == 'invalid_query'
    assert str(raised.value) == 'Event search query is too long.'


@pytest.mark.parametrize('query', [5000 * ' ', object()])
def test_search_rejects_invalid_raw_queries_before_normalizing(
    event_session, query, monkeypatch,
):
    def normalization_must_not_run(_value):
        raise AssertionError('normalization should not run')

    monkeypatch.setattr(event_catalog, '_normalized', normalization_must_not_run)
    with pytest.raises(EventCatalogError) as raised:
        list_events(event_session, query)

    assert raised.value.code == 'invalid_query'
    assert str(raised.value) == 'Event search query is too long.'


def test_missing_table_is_catalog_unavailable_and_does_not_rollback_caller():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE caller_work (value TEXT)'))
    with Session(engine) as session:
        session.execute(
            text('INSERT INTO caller_work (value) VALUES (:value)'),
            {'value': 'still pending'},
        )

        with pytest.raises(EventCatalogError) as raised:
            resolve_between_events(session, 'eden', 'abel-killed')

        assert raised.value.code == 'catalog_unavailable'
        assert str(raised.value) == 'The verified event catalog is unavailable.'
        assert isinstance(raised.value.__cause__, OperationalError)
        assert session.scalar(text('SELECT COUNT(*) FROM caller_work')) == 1
        assert session.in_transaction()


def test_forced_sql_error_is_catalog_unavailable(event_session, monkeypatch):
    failure = OperationalError('SELECT', {}, RuntimeError('database offline'))

    def fail_execute(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(event_session, 'execute', fail_execute)
    with pytest.raises(EventCatalogError) as raised:
        list_events(event_session)

    assert raised.value.code == 'catalog_unavailable'
    assert raised.value.__cause__ is failure


@pytest.mark.parametrize(('operation', 'expected_ids'), [
    (
        lambda session: list_events(session),
        ['eden', 'eden-expulsion', 'cain-born', 'abel-born', 'offerings',
         'abel-killed'],
    ),
    (
        lambda session: resolve_between_events(
            session, 'eden-expulsion', 'abel-killed'
        ),
        ['eden-expulsion', 'cain-born', 'abel-born', 'offerings',
         'abel-killed'],
    ),
])
def test_event_resolution_uses_one_bounded_biblical_query(
    event_session, operation, expected_ids,
):
    statements = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
        if 'biblical_texts' in statement:
            statements.append(statement)

    event.listen(
        event_session.get_bind(), 'before_cursor_execute', record_statement
    )
    try:
        assert [item.id for item in operation(event_session)] == expected_ids
    finally:
        event.remove(
            event_session.get_bind(), 'before_cursor_execute', record_statement
        )

    assert len(statements) == 1
    normalized_sql = statements[0].lower()
    assert 'lower(' not in normalized_sql
    assert 'upper(' not in normalized_sql
    assert 'book in' in normalized_sql
    assert 'chapter =' in normalized_sql
    assert 'verse between' in normalized_sql


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
