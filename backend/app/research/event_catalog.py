"""Reviewed, source-backed event definitions for scripture research."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class EventDefinition:
    id: str
    title: str
    description: str
    aliases: tuple[str, ...]
    book: str
    chapter: int
    verse_start: int
    verse_end: int
    people: tuple[str, ...]
    places: tuple[str, ...]
    ordering_group: str
    ordinal: int


@dataclass(frozen=True)
class EventRecord:
    id: str
    title: str
    description: str
    aliases: tuple[str, ...]
    book: str
    chapter: int
    verse_start: int
    verse_end: int
    reference: str
    people: tuple[str, ...]
    places: tuple[str, ...]
    ordering_group: str
    ordinal: int
    source_ids: tuple[str, ...]
    translation: str


class EventCatalogError(ValueError):
    """A safe, focused event-catalog validation error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


EVENT_DEFINITIONS = (
    EventDefinition(
        id='eden',
        title='Life in the Garden of Eden',
        description=(
            'The LORD God places the man in the garden, gives the command '
            'concerning the tree, and brings the woman to him.'
        ),
        aliases=('Eden', 'Garden life', 'Garden of Eden'),
        book='Genesis',
        chapter=2,
        verse_start=8,
        verse_end=25,
        people=('adam', 'eve'),
        places=('garden-of-eden',),
        ordering_group='eden-sequence',
        ordinal=1,
    ),
    EventDefinition(
        id='eden-expulsion',
        title='Expulsion from Eden',
        description=(
            'The man and woman are sent out from the garden, and cherubim '
            'guard the way to the tree of life.'
        ),
        aliases=('Eden expulsion', 'Expelled from Eden', 'Garden expulsion'),
        book='Genesis',
        chapter=3,
        verse_start=22,
        verse_end=24,
        people=('adam', 'eve'),
        places=('garden-of-eden',),
        ordering_group='eden-sequence',
        ordinal=2,
    ),
    EventDefinition(
        id='cain-born',
        title='Cain is born',
        description='Eve bears Cain.',
        aliases=("Cain's birth", 'Birth of Cain'),
        book='Genesis',
        chapter=4,
        verse_start=1,
        verse_end=1,
        people=('adam', 'eve', 'cain'),
        places=(),
        ordering_group='eden-sequence',
        ordinal=3,
    ),
    EventDefinition(
        id='abel-born',
        title='Abel is born',
        description="Eve also bears Cain's brother Abel, who keeps sheep.",
        aliases=("Abel's birth", 'Birth of Abel'),
        book='Genesis',
        chapter=4,
        verse_start=2,
        verse_end=2,
        people=('eve', 'cain', 'abel'),
        places=(),
        ordering_group='eden-sequence',
        ordinal=4,
    ),
    EventDefinition(
        id='offerings',
        title="Cain and Abel's offerings",
        description=(
            'Cain and Abel bring offerings; the LORD regards Abel and his '
            'offering, but not Cain and his offering.'
        ),
        aliases=('Offerings', 'Cain and Abel bring offerings'),
        book='Genesis',
        chapter=4,
        verse_start=3,
        verse_end=5,
        people=('cain', 'abel'),
        places=(),
        ordering_group='eden-sequence',
        ordinal=5,
    ),
    EventDefinition(
        id='abel-killed',
        title='Cain kills Abel',
        description='Cain rises against Abel in the field and kills him.',
        aliases=("Abel's death", 'Abel killed', 'Cain murders Abel'),
        book='Genesis',
        chapter=4,
        verse_start=8,
        verse_end=8,
        people=('cain', 'abel'),
        places=('field',),
        ordering_group='eden-sequence',
        ordinal=6,
    ),
)

_DEFINITIONS_BY_ID = MappingProxyType({item.id: item for item in EVENT_DEFINITIONS})
_TRUSTED_TRANSLATIONS = (
    'KJV', 'ASV', 'BBE', 'DARBY', 'DRA', 'ERV', 'ESV', 'NASB', 'NIV',
    'NLT', 'NRSV', 'WEB', 'WEBBE',
)
_MAX_QUERY_LENGTH = 256
_RAW_QUERY_MAX = 4096
_WHITESPACE = re.compile(r'\s+')
_ERRORS = MappingProxyType({
    'invalid_query': 'Event search query is too long.',
    'catalog_unavailable': 'The verified event catalog is unavailable.',
    'unknown_event': 'Unknown event ID.',
    'different_ordering_group': (
        'Events must belong to the same ordering group.'
    ),
    'invalid_event_order': 'The start event must not follow the end event.',
    'missing_passage': (
        'The requested event range is not fully available from verified scripture.'
    ),
})


def _normalized(value: str) -> str:
    normalized = unicodedata.normalize('NFKC', value)
    return _WHITESPACE.sub(' ', normalized).strip().casefold()


def _normalized_query(query: object) -> str:
    if not isinstance(query, str) or len(query) > _RAW_QUERY_MAX:
        raise _error('invalid_query')
    normalized = _normalized(query)
    if len(normalized) > _MAX_QUERY_LENGTH:
        raise _error('invalid_query')
    return normalized


def _matches(definition: EventDefinition, needle: str) -> bool:
    if not needle:
        return True
    return any(
        needle in _normalized(candidate)
        for candidate in (definition.title, *definition.aliases)
    )


def _reference(definition: EventDefinition) -> str:
    start = f'{definition.book} {definition.chapter}:{definition.verse_start}'
    if definition.verse_start == definition.verse_end:
        return start
    return f'{start}-{definition.verse_end}'


def _passage_rows(
    session: Session,
    definitions: list[EventDefinition],
) -> list[dict[str, Any]]:
    if not definitions:
        return []

    params: dict[str, Any] = {}
    book_names = []
    for index, book in enumerate(sorted({item.book for item in definitions})):
        name = f'book_{index}'
        params[name] = book
        book_names.append(f':{name}')

    range_clauses = []
    for index, definition in enumerate(definitions):
        chapter_name = f'chapter_{index}'
        start_name = f'verse_start_{index}'
        end_name = f'verse_end_{index}'
        params[chapter_name] = definition.chapter
        params[start_name] = definition.verse_start
        params[end_name] = definition.verse_end
        range_clauses.append(
            f'(chapter = :{chapter_name} '
            f'AND verse BETWEEN :{start_name} AND :{end_name})'
        )

    translation_names = []
    for index, translation in enumerate(_TRUSTED_TRANSLATIONS):
        name = f'translation_{index}'
        params[name] = translation
        translation_names.append(f':{name}')
    statement = text(f'''
        SELECT id, book, chapter, verse, translation
        FROM biblical_texts
        WHERE book IN ({', '.join(book_names)})
          AND ({' OR '.join(range_clauses)})
          AND translation IN ({', '.join(translation_names)})
        ORDER BY book, chapter, verse, id
    ''')
    try:
        return [dict(row) for row in session.execute(statement, params).mappings()]
    except SQLAlchemyError as exc:
        raise _error('catalog_unavailable') from exc


def _resolved_event(
    definition: EventDefinition,
    rows: list[dict[str, Any]],
) -> EventRecord | None:
    expected_verses = set(range(definition.verse_start, definition.verse_end + 1))
    by_translation: dict[str, dict[int, dict[str, Any]]] = {}
    for row in rows:
        if (
            row['book'] != definition.book
            or row['chapter'] != definition.chapter
            or not definition.verse_start <= row['verse'] <= definition.verse_end
        ):
            continue
        translation = str(row['translation'])
        by_translation.setdefault(translation, {}).setdefault(row['verse'], row)
    for translation in _TRUSTED_TRANSLATIONS:
        verse_rows = by_translation.get(translation, {})
        if set(verse_rows) == expected_verses:
            ordered_rows = [verse_rows[verse] for verse in sorted(verse_rows)]
            return EventRecord(
                id=definition.id,
                title=definition.title,
                description=definition.description,
                aliases=definition.aliases,
                book=definition.book,
                chapter=definition.chapter,
                verse_start=definition.verse_start,
                verse_end=definition.verse_end,
                reference=_reference(definition),
                people=definition.people,
                places=definition.places,
                ordering_group=definition.ordering_group,
                ordinal=definition.ordinal,
                source_ids=tuple(
                    f"scripture:{row['id']}" for row in ordered_rows
                ),
                translation=translation,
            )
    return None


def _resolve_definitions(
    session: Session,
    definitions: list[EventDefinition],
) -> list[EventRecord | None]:
    rows = _passage_rows(session, definitions)
    return [_resolved_event(definition, rows) for definition in definitions]


def list_events(session: Session, query: str | None = None) -> list[EventRecord]:
    """Return reviewed events whose complete passages exist in trusted scripture."""

    normalized_query = _normalized_query('' if query is None else query)
    definitions = sorted(
        (item for item in EVENT_DEFINITIONS if _matches(item, normalized_query)),
        key=lambda item: (item.ordering_group, item.ordinal, item.id),
    )
    return [event for event in _resolve_definitions(session, definitions)
            if event is not None]


def get_event(session: Session, event_id: str) -> EventRecord | None:
    """Return one source-backed event, or ``None`` when unknown or incomplete."""

    definition = _DEFINITIONS_BY_ID.get(event_id)
    if definition is None:
        return None
    return _resolve_definitions(session, [definition])[0]


def _error(code: str) -> EventCatalogError:
    return EventCatalogError(code, _ERRORS[code])


def resolve_between_events(
    session: Session,
    from_id: str,
    to_id: str,
) -> list[EventRecord]:
    """Resolve a validated, inclusive event interval in reviewed order."""

    start = _DEFINITIONS_BY_ID.get(from_id)
    end = _DEFINITIONS_BY_ID.get(to_id)
    if start is None or end is None:
        raise _error('unknown_event')
    if start.ordering_group != end.ordering_group:
        raise _error('different_ordering_group')
    if start.ordinal > end.ordinal:
        raise _error('invalid_event_order')

    definitions = sorted(
        (
            item for item in EVENT_DEFINITIONS
            if item.ordering_group == start.ordering_group
            and start.ordinal <= item.ordinal <= end.ordinal
        ),
        key=lambda item: (item.ordinal, item.id),
    )
    resolved = _resolve_definitions(session, definitions)
    if any(item is None for item in resolved):
        raise _error('missing_passage')
    return [item for item in resolved if item is not None]
