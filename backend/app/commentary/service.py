"""Queries over immutable, actively published commentary editions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.commentary.models import (
    CommentaryEdition,
    CommentaryEntry,
    CommentaryPublication,
    CommentarySource,
)
from app.library.canon import alias_target
from app.library.models import LibraryWork


MAX_ENTRIES = 50
MAX_BODY_CHARACTERS = 100_000
MAX_CHAPTER = 500
MAX_VERSE = 1_000


class CommentaryLookupError(LookupError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PublishedSource:
    source: CommentarySource
    edition: CommentaryEdition
    publication: CommentaryPublication


def _active_publication_statement():
    return (
        select(CommentarySource, CommentaryEdition, CommentaryPublication)
        .join(CommentaryPublication, CommentaryPublication.source_id == CommentarySource.id)
        .join(
            CommentaryEdition,
            and_(
                CommentaryEdition.id == CommentaryPublication.edition_id,
                CommentaryEdition.source_id == CommentaryPublication.source_id,
            ),
        )
        .where(
            CommentaryPublication.active.is_(True),
            CommentaryEdition.status == 'published',
        )
    )


def list_published_sources(session: Session) -> list[PublishedSource]:
    rows = session.execute(
        _active_publication_statement().order_by(CommentarySource.title, CommentarySource.id)
    ).all()
    return [PublishedSource(*row) for row in rows]


def get_published_source(session: Session, source_id: str) -> PublishedSource:
    source_exists = session.get(CommentarySource, source_id)
    if source_exists is None:
        raise CommentaryLookupError('source_not_found', 'Commentary source was not found.')
    row = session.execute(
        _active_publication_statement().where(CommentarySource.id == source_id)
    ).one_or_none()
    if row is None:
        raise CommentaryLookupError(
            'source_not_published', 'Commentary source has no active published edition.',
        )
    return PublishedSource(*row)


def resolve_work(session: Session, book: str) -> LibraryWork:
    work_id = alias_target(book)
    if work_id is None:
        candidate = book.strip().casefold().replace(' ', '-')
        if session.get(LibraryWork, candidate) is not None:
            work_id = candidate
    work = session.get(LibraryWork, work_id) if work_id else None
    if work is None:
        raise CommentaryLookupError('work_not_found', 'Bible work was not found.')
    return work


def source_document(item: PublishedSource) -> dict:
    source, edition, publication = item.source, item.edition, item.publication
    return {
        'id': source.id,
        'title': source.title,
        'abbreviation': source.abbreviation,
        'author': source.author,
        'publication_period': source.publication_period,
        'tradition': source.tradition,
        'language': source.language,
        'license_spdx': source.license_spdx,
        'license_url': source.license_url,
        'attribution': source.attribution,
        'provenance_url': source.provenance_url,
        'edition_version': publication.version,
        'dataset_version': edition.dataset_version,
        'coverage': normalize_public_coverage(edition.coverage),
    }


def normalize_public_coverage(coverage: object) -> dict:
    """Expose exact coverage when present and label legacy counts conservatively."""
    document = coverage if isinstance(coverage, dict) else {}
    raw_by_work = document.get('by_work')
    by_work: dict[str, dict] = {}
    if isinstance(raw_by_work, dict):
        for work_id, raw in raw_by_work.items():
            if not isinstance(work_id, str) or not isinstance(raw, dict):
                continue
            chapters = raw.get('chapters') if type(raw.get('chapters')) is int else 0
            entries = raw.get('entries') if type(raw.get('entries')) is int else 0
            raw_numbers = raw.get('chapter_numbers')
            exact = (
                isinstance(raw_numbers, list)
                and all(type(number) is int and number > 0 for number in raw_numbers)
                and raw_numbers == sorted(set(raw_numbers))
                and len(raw_numbers) == chapters
            )
            by_work[work_id] = {
                'chapters': max(chapters, 0),
                'chapter_numbers': list(raw_numbers) if exact else [],
                'chapter_numbers_complete': exact,
                'entries': max(entries, 0),
            }
    return {
        'books': document.get('books') if type(document.get('books')) is int else len(by_work),
        'chapters': document.get('chapters') if type(document.get('chapters')) is int else 0,
        'entries': document.get('entries') if type(document.get('entries')) is int else 0,
        'by_work': by_work,
    }


def _coverage_availability(coverage: dict, work_id: str, chapter: int) -> str:
    work_coverage = (coverage.get('by_work') or {}).get(work_id)
    if not isinstance(work_coverage, dict):
        return 'coverage_incomplete'
    chapter_numbers = work_coverage.get('chapter_numbers')
    if (
        work_coverage.get('chapter_numbers_complete') is not True
        or not isinstance(chapter_numbers, list)
        or chapter not in chapter_numbers
    ):
        return 'coverage_incomplete'
    return 'no_entry'


def _citation(work: LibraryWork, row: CommentaryEntry, source: CommentarySource) -> str:
    reference = work.title
    if row.chapter is not None:
        reference += f' {row.chapter}'
    if row.verse_start is not None:
        reference += f':{row.verse_start}'
        if row.verse_end != row.verse_start:
            reference += f'-{row.verse_end}'
    return f'{reference} — {source.title}'


def entry_statement(
    *,
    edition_id: UUID,
    work_id: str,
    chapter: int,
    verse: int | None,
    limit: int,
):
    """Build the portable semantic entry order used by every public read."""
    statement = select(CommentaryEntry).where(
        CommentaryEntry.edition_id == edition_id,
        CommentaryEntry.work_id == work_id,
    )
    if verse is not None:
        statement = statement.where(
            CommentaryEntry.chapter == chapter,
            CommentaryEntry.verse_start.is_not(None),
            CommentaryEntry.verse_end.is_not(None),
            CommentaryEntry.verse_start <= verse,
            CommentaryEntry.verse_end >= verse,
        )
    else:
        statement = statement.where(or_(
            CommentaryEntry.chapter == chapter,
            CommentaryEntry.chapter.is_(None),
        ))
    return statement.order_by(
        CommentaryEntry.chapter.asc().nulls_first(),
        CommentaryEntry.verse_start.asc().nulls_first(),
        CommentaryEntry.verse_end.asc().nulls_first(),
        CommentaryEntry.entry_type,
        CommentaryEntry.position,
        CommentaryEntry.id,
    ).limit(limit)


def passage_document(
    session: Session,
    *,
    source_id: str,
    book: str,
    chapter: int,
    verse: int | None,
    max_entries: int = MAX_ENTRIES,
    max_body_characters: int = MAX_BODY_CHARACTERS,
) -> tuple[dict, datetime]:
    published = get_published_source(session, source_id)
    work = resolve_work(session, book)
    if max_entries < 0 or max_body_characters < 0:
        raise ValueError('Commentary response budgets must be nonnegative.')
    statement = entry_statement(
        edition_id=published.edition.id,
        work_id=work.id,
        chapter=chapter,
        verse=verse,
        limit=max_entries + 1,
    )
    matching_rows = session.scalars(statement).all()
    count_truncated = len(matching_rows) > max_entries
    rows = matching_rows[:max_entries]

    source = source_document(published)
    coverage = source['coverage']
    remaining = max_body_characters
    entries: list[dict] = []
    body_truncated = False
    for row in rows:
        if remaining == 0:
            body_truncated = True
            break
        body = row.body
        if len(body) > remaining:
            body = body[:remaining]
            body_truncated = True
        remaining -= len(body)
        entries.append({
            'scope': {
                'verse_start': row.verse_start,
                'verse_end': row.verse_end,
            },
            'entry_type': row.entry_type,
            'heading': row.heading,
            'body': body,
            'source_locator': row.source_locator,
            'citation': _citation(work, row, published.source),
            'source': source,
        })
        if remaining == 0:
            body_truncated = body_truncated or row is not rows[-1]
            break

    coverage_availability = _coverage_availability(
        coverage, work.id, chapter,
    )
    if verse is None and coverage_availability == 'coverage_incomplete':
        availability = coverage_availability
    elif matching_rows:
        availability = 'available' if verse is not None else (
            'available'
            if any(row.entry_type in {'book_intro', 'chapter_intro'} for row in matching_rows)
            else 'wider_range'
        )
    else:
        availability = coverage_availability
    reference = {'book': work.title, 'chapter': chapter}
    if verse is not None:
        reference['verse'] = verse
    document = {
        'reference': reference,
        'availability': availability,
        'source': source,
        'edition': {
            'id': str(published.edition.id),
            'version': published.publication.version,
            'dataset_version': published.edition.dataset_version,
        },
        'coverage': coverage,
        'entries': entries,
        'truncated': count_truncated or body_truncated,
    }
    return document, published.publication.published_at
