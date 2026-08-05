"""Queries over immutable, actively published commentary editions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, select
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
        'coverage': edition.coverage,
    }


def _coverage_availability(coverage: dict, work_id: str, chapter: int) -> str:
    work_coverage = (coverage.get('by_work') or {}).get(work_id)
    if not isinstance(work_coverage, dict):
        return 'coverage_incomplete'
    chapter_numbers = work_coverage.get('chapter_numbers')
    if isinstance(chapter_numbers, list) and chapter not in chapter_numbers:
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


def passage_document(
    session: Session,
    *,
    source_id: str,
    book: str,
    chapter: int,
    verse: int | None,
) -> tuple[dict, datetime]:
    published = get_published_source(session, source_id)
    work = resolve_work(session, book)
    statement = select(CommentaryEntry).where(
        CommentaryEntry.edition_id == published.edition.id,
        CommentaryEntry.work_id == work.id,
        CommentaryEntry.chapter == chapter,
    )
    if verse is not None:
        statement = statement.where(
            CommentaryEntry.verse_start.is_not(None),
            CommentaryEntry.verse_end.is_not(None),
            CommentaryEntry.verse_start <= verse,
            CommentaryEntry.verse_end >= verse,
        )
    statement = statement.order_by(
        CommentaryEntry.chapter,
        CommentaryEntry.verse_start,
        CommentaryEntry.verse_end,
        CommentaryEntry.entry_type,
        CommentaryEntry.position,
        CommentaryEntry.id,
    )
    rows = session.scalars(statement.limit(MAX_ENTRIES + 1)).all()
    count_truncated = len(rows) > MAX_ENTRIES
    rows = rows[:MAX_ENTRIES]

    source = source_document(published)
    remaining = MAX_BODY_CHARACTERS
    entries: list[dict] = []
    body_truncated = False
    for row in rows:
        body = row.body
        if len(body) > remaining:
            body = body[:remaining]
            body_truncated = True
        remaining -= len(body)
        entries.append({
            'scope': {
                'chapter': row.chapter,
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

    if entries:
        availability = 'available' if verse is not None else (
            'available'
            if any(entry['entry_type'] in {'book_intro', 'chapter_intro'} for entry in entries)
            else 'wider_range'
        )
    else:
        availability = _coverage_availability(published.edition.coverage, work.id, chapter)
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
        'coverage': published.edition.coverage,
        'entries': entries,
        'truncated': count_truncated or body_truncated,
    }
    return document, published.publication.published_at
