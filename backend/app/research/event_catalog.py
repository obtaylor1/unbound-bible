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
_WHITESPACE = re.compile(r'\s+')
_ERRORS = MappingProxyType({
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
    bounded = value[:_MAX_QUERY_LENGTH]
    normalized = unicodedata.normalize('NFKC', bounded)
    return _WHITESPACE.sub(' ', normalized).strip().casefold()


def _matches(definition: EventDefinition, query: str) -> bool:
    needle = _normalized(query)
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
    definition: EventDefinition,
) -> tuple[str, list[dict[str, Any]]] | None:
    translation_names = []
    params: dict[str, Any] = {
        'book': definition.book,
        'chapter': definition.chapter,
        'verse_start': definition.verse_start,
        'verse_end': definition.verse_end,
    }
    for index, translation in enumerate(_TRUSTED_TRANSLATIONS):
        name = f'translation_{index}'
        params[name] = translation
        translation_names.append(f':{name}')
    statement = text(f'''
        SELECT id, verse, upper(translation) AS translation
        FROM biblical_texts
        WHERE lower(trim(book)) = lower(:book)
          AND chapter = :chapter
          AND verse BETWEEN :verse_start AND :verse_end
          AND upper(coalesce(translation, '')) IN ({', '.join(translation_names)})
        ORDER BY verse, id
    ''')
    try:
        rows = [dict(row) for row in session.execute(statement, params).mappings()]
    except SQLAlchemyError:
        session.rollback()
        return None

    expected_verses = set(range(definition.verse_start, definition.verse_end + 1))
    by_translation: dict[str, dict[int, dict[str, Any]]] = {}
    for row in rows:
        translation = str(row['translation'])
        by_translation.setdefault(translation, {}).setdefault(row['verse'], row)
    for translation in _TRUSTED_TRANSLATIONS:
        verse_rows = by_translation.get(translation, {})
        if set(verse_rows) == expected_verses:
            return translation, [verse_rows[verse] for verse in sorted(verse_rows)]
    return None


def _resolve_definition(
    session: Session,
    definition: EventDefinition,
) -> EventRecord | None:
    resolved = _passage_rows(session, definition)
    if resolved is None:
        return None
    translation, rows = resolved
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
        source_ids=tuple(f"scripture:{row['id']}" for row in rows),
        translation=translation,
    )


def list_events(session: Session, query: str | None = None) -> list[EventRecord]:
    """Return reviewed events whose complete passages exist in trusted scripture."""

    definitions = sorted(
        (item for item in EVENT_DEFINITIONS if _matches(item, query or '')),
        key=lambda item: (item.ordering_group, item.ordinal, item.id),
    )
    return [
        event
        for definition in definitions
        if (event := _resolve_definition(session, definition)) is not None
    ]


def get_event(session: Session, event_id: str) -> EventRecord | None:
    """Return one source-backed event, or ``None`` when unknown or incomplete."""

    definition = _DEFINITIONS_BY_ID.get(event_id)
    return _resolve_definition(session, definition) if definition is not None else None


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
    resolved = [_resolve_definition(session, item) for item in definitions]
    if any(item is None for item in resolved):
        raise _error('missing_passage')
    return [item for item in resolved if item is not None]
