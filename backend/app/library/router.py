"""Read-only canon and installed-edition library endpoints."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import get_session
from app.library.canon import (
    CATHOLIC_WORK_IDS,
    ETHIOPIAN_CANON,
    PROTESTANT_WORK_IDS,
    SUPPLEMENTAL_LIBRARY_WORKS,
    WORKS,
    alias_target,
)
from app.library.models import (
    CanonEntry,
    CanonEntryWork,
    EditionCoverage,
    EditionWorkSource,
    LibraryWork,
    LibraryWorkAlias,
    TextEdition,
)
from app.library.seed import CANON_CODE


router = APIRouter(tags=['library'])
compatibility_router = APIRouter(tags=['scripture reader compatibility'])

_TESTAMENT_NAMES = {'OT': 'Old Testament', 'NT': 'New Testament'}
_ETHIOPIAN_ENTRIES_BY_KEY = {
    (entry.testament, entry.order): entry
    for entry in ETHIOPIAN_CANON
}
_ETHIOPIAN_WORK_ORDER_BY_ENTRY_KEY = {
    (entry.testament, entry.order): {work_id: index for index, work_id in enumerate(entry.work_ids)}
    for entry in ETHIOPIAN_CANON
}
_WORKS_BY_ID = {
    work.id: work for work in (*WORKS, *SUPPLEMENTAL_LIBRARY_WORKS)
}


def _testament_name(value: str) -> str:
    return _TESTAMENT_NAMES.get(value, value)


def _legacy_table_available(session: Session) -> bool:
    return inspect(session.bind).has_table('biblical_texts')


def _edition_payload(edition: TextEdition | None) -> dict | None:
    if edition is None:
        return None
    return {
        'code': edition.edition_code,
        'name': edition.name,
        'language': edition.reading_language,
        'source_language': edition.source_language,
        'script': edition.script,
        'publisher': edition.publisher,
        'license': edition.license_spdx,
        'attribution': edition.attribution,
        'provenance_url': edition.provenance_url,
        'source_tradition': edition.source_tradition,
        'relationship': edition.relationship,
        'versification': edition.versification,
        'verification_status': edition.verification_status,
    }


def _work_source_payload(source: EditionWorkSource | None) -> dict | None:
    if source is None:
        return None
    return {
        'source_key': source.source_key,
        'source_label': source.source_label,
        'source_language': source.source_language,
        'source_tradition': source.source_tradition,
        'published_year': source.published_year,
        'license': source.license_spdx,
        'attribution': source.attribution,
        'provenance_url': source.provenance_url,
        'fallback': source.fallback,
        'modified': source.modified,
        'modification_note': source.modification_note,
        'verification_status': source.verification_status,
        'canon_scope': source.canon_scope,
    }


def _reader_rows(session: Session, where_clause: str, params: dict) -> list[dict]:
    if not _legacy_table_available(session):
        return []
    rows = session.execute(text(f'''
        SELECT id, book, chapter, verse, text, translation
        FROM biblical_texts
        WHERE {where_clause}
        ORDER BY chapter, verse, translation
    '''), params).mappings().all()
    codes = {row['translation'] for row in rows if row['translation']}
    editions = {
        edition.edition_code: edition
        for edition in session.scalars(
            select(TextEdition).where(TextEdition.edition_code.in_(codes))
        ).all()
    } if codes else {}
    work_ids = {
        work_id
        for row in rows
        if (work_id := alias_target(row['book'])) is not None
    }
    sources = {
        (source.edition_code, source.work_id): source
        for source in session.scalars(
            select(EditionWorkSource).where(
                EditionWorkSource.edition_code.in_(codes),
                EditionWorkSource.work_id.in_(work_ids),
            )
        ).all()
    } if codes and work_ids else {}
    return [
        {
            **dict(row),
            'edition': _edition_payload(editions.get(row['translation'])),
            'work_source': _work_source_payload(sources.get((
                row['translation'], alias_target(row['book']),
            ))),
        }
        for row in rows
    ]


@compatibility_router.get('/api/biblical-texts/available-books')
def available_reader_books(session: Session = Depends(get_session)) -> dict:
    if not _legacy_table_available(session):
        return {'books': []}
    books = session.scalars(text(
        'SELECT DISTINCT book FROM biblical_texts ORDER BY book'
    )).all()
    return {'books': list(books)}


@compatibility_router.get('/api/biblical-texts/chapter-content')
def reader_chapter_content(
    book: str = Query(min_length=1, max_length=200),
    chapter: int = Query(ge=1),
    session: Session = Depends(get_session),
) -> dict:
    return {'content': _reader_rows(
        session,
        'lower(book) = lower(:book) AND chapter = :chapter',
        {'book': book, 'chapter': chapter},
    )}


@compatibility_router.get('/api/biblical-texts/book-content')
def reader_book_content(
    book: str = Query(min_length=1, max_length=200),
    session: Session = Depends(get_session),
) -> dict:
    return {'content': _reader_rows(
        session,
        'lower(book) = lower(:book)',
        {'book': book},
    )}


@compatibility_router.get('/api/v1/texts/{book}/{chapter}/{verse}/details')
def reader_verse_details(
    book: str,
    chapter: int,
    verse: int,
    session: Session = Depends(get_session),
) -> dict:
    rows = _reader_rows(
        session,
        'lower(book) = lower(:book) AND chapter = :chapter AND verse = :verse',
        {'book': book, 'chapter': chapter, 'verse': verse},
    )
    if not rows:
        raise HTTPException(status_code=404, detail='Verse not found')
    return {
        'book': book,
        'chapter': chapter,
        'verse': verse,
        'translations': {
            (row['translation'] or 'unknown').lower(): row['text']
            for row in rows
        },
        'historical_context': [],
        'geographical_context': [],
        'original_words': [],
        'original_language_insights': [],
        'cross_references': [],
        'translation_biases': [],
        'race_misuse_records': [],
        'verse_meaning': '',
        'translation_comparison': '',
        'critical_analysis': '',
    }


def _coverage_and_recommendations_by_work(
    session: Session,
    work_ids: Iterable[str],
) -> tuple[dict[str, list[dict]], dict[str, str]]:
    ids = tuple(work_ids)
    if not ids:
        return {}, {}
    rows = session.execute(
        select(EditionCoverage, TextEdition, EditionWorkSource)
        .join(TextEdition, TextEdition.edition_code == EditionCoverage.edition_code)
        .outerjoin(
            EditionWorkSource,
            (EditionWorkSource.edition_code == EditionCoverage.edition_code)
            & (EditionWorkSource.work_id == EditionCoverage.work_id),
        )
        .where(EditionCoverage.work_id.in_(ids))
        .order_by(EditionCoverage.work_id, TextEdition.edition_code)
    ).all()
    coverage: dict[str, list[dict]] = {}
    candidates: dict[str, list[tuple[int, str]]] = {}
    for edition_coverage, edition, source in rows:
        coverage.setdefault(edition_coverage.work_id, []).append({
            'edition_code': edition.edition_code,
            'edition_name': edition.name,
            'reading_language': edition.reading_language,
            'relationship': edition.relationship,
            'verification_status': edition.verification_status,
            'status': edition_coverage.status,
            'chapter_count': edition_coverage.chapter_count,
            'verse_count': edition_coverage.verse_count,
            'note': edition_coverage.note,
        })
        is_english = edition.reading_language.casefold() == 'english'
        eligible = (
            is_english
            and edition_coverage.status == 'verified_english'
            and edition.verification_status in {'verified', 'provisional'}
        )
        if edition.edition_code == 'EOTC-COMPOSITE-EN':
            eligible = eligible and source is not None and source.canon_scope == 'ethio81'
        if eligible:
            priority = (
                0 if edition.edition_code == 'EOTC-COMPOSITE-EN'
                else 1 if edition.verification_status == 'verified'
                else 2
            )
            candidates.setdefault(edition_coverage.work_id, []).append((
                priority, edition.edition_code,
            ))
    recommendations = {
        work_id: min(options)[1]
        for work_id, options in candidates.items()
    }
    return coverage, recommendations


def _coverage_by_work(session: Session, work_ids: Iterable[str]) -> dict[str, list[dict]]:
    return _coverage_and_recommendations_by_work(session, work_ids)[0]


def _normalize_canon(canon: str) -> str:
    normalized = canon.strip().upper()
    if normalized == 'ETH81':
        return CANON_CODE
    if normalized in {CANON_CODE, 'PROT66', 'CATH73'}:
        return normalized
    raise HTTPException(status_code=422, detail=f'Unknown canon: {canon}')


def _ethiopian_books(session: Session) -> tuple[list[dict], int]:
    rows = session.execute(
        select(CanonEntry, CanonEntryWork, LibraryWork)
        .join(CanonEntryWork, CanonEntryWork.canon_entry_id == CanonEntry.id)
        .join(LibraryWork, LibraryWork.id == CanonEntryWork.work_id)
        .where(CanonEntry.canon_code == CANON_CODE)
    ).all()
    canon_count = session.scalar(
        select(func.count()).select_from(CanonEntry).where(CanonEntry.canon_code == CANON_CODE)
    )
    # Only actual normalized membership rows are rendered.  The immutable map
    # supplies the otherwise unavailable work order within a composite entry.
    ordered_rows = sorted(
        (
            (entry, entry_work, work)
            for entry, entry_work, work in rows
            if entry_work.work_id in _ETHIOPIAN_WORK_ORDER_BY_ENTRY_KEY.get(
                (entry.testament, entry.canonical_order), {}
            )
        ),
        key=lambda row: (
            0 if row[0].testament == 'OT' else 1,
            row[0].canonical_order,
            _ETHIOPIAN_WORK_ORDER_BY_ENTRY_KEY[
                (row[0].testament, row[0].canonical_order)
            ][row[1].work_id],
        ),
    )
    coverage, recommendations = _coverage_and_recommendations_by_work(
        session, (entry_work.work_id for _, entry_work, _ in ordered_rows)
    )
    books = []
    for entry, entry_work, work in ordered_rows:
        canonical_entry = _ETHIOPIAN_ENTRIES_BY_KEY[(entry.testament, entry.canonical_order)]
        books.append({
            'id': work.id,
            'name': work.title,
            'testament': _testament_name(entry.testament),
            'collection': canonical_entry.section,
            'entry_name': entry.title,
            'entry_order': entry.canonical_order,
            'canon_included': True,
            'coverage': coverage.get(work.id, []),
            'recommended_edition': recommendations.get(work.id),
            'unavailable_reason': (
                None if work.id in recommendations else 'English text not yet available'
            ),
        })
    return books, int(canon_count or 0)


def _standard_metadata(work_id: str) -> tuple[str, str, str]:
    work = _WORKS_BY_ID[work_id]
    return work.name, work.testament, work.collection


def _standard_books(session: Session, canon_code: str) -> tuple[list[dict], int]:
    work_ids = PROTESTANT_WORK_IDS if canon_code == 'PROT66' else CATHOLIC_WORK_IDS
    stored_titles = dict(session.execute(
        select(LibraryWork.id, LibraryWork.title).where(LibraryWork.id.in_(work_ids))
    ).all())
    coverage = _coverage_by_work(session, work_ids)
    books = []
    for order, work_id in enumerate(work_ids, 1):
        fallback_name, testament, collection = _standard_metadata(work_id)
        name = stored_titles.get(work_id, fallback_name)
        books.append({
            'id': work_id,
            'name': name,
            'testament': _testament_name(testament),
            'collection': collection,
            'entry_name': name,
            'entry_order': order,
            'canon_included': True,
            'coverage': coverage.get(work_id, []),
        })
    return books, len(work_ids)


@router.get('/books')
def books(
    canon: str = Query(default='PROT66'),
    session: Session = Depends(get_session),
) -> dict:
    canon_code = _normalize_canon(canon)
    if canon_code == CANON_CODE:
        catalog, canon_count = _ethiopian_books(session)
    else:
        catalog, canon_count = _standard_books(session, canon_code)
    return {
        'canon_filter': canon_code,
        'canon_count': canon_count,
        'navigation_count': len(catalog),
        'books': catalog,
    }


@router.get('/library/works/{work_id}')
def library_work(work_id: str, session: Session = Depends(get_session)) -> dict:
    work = session.get(LibraryWork, work_id)
    if work is None:
        raise HTTPException(status_code=404, detail='Library work not found')
    aliases = session.scalars(
        select(LibraryWorkAlias.alias)
        .where(LibraryWorkAlias.work_id == work_id)
        .order_by(LibraryWorkAlias.alias)
    ).all()
    entries = session.execute(
        select(CanonEntry)
        .join(CanonEntryWork, CanonEntryWork.canon_entry_id == CanonEntry.id)
        .where(CanonEntryWork.work_id == work_id)
        .order_by(CanonEntry.canon_code, CanonEntry.testament, CanonEntry.canonical_order)
    ).scalars().all()
    coverage = _coverage_by_work(session, (work_id,)).get(work_id, [])
    return {
        'id': work.id,
        'name': work.title,
        'aliases': aliases,
        'canon_entries': [{
            'canon_code': entry.canon_code,
            'testament': _testament_name(entry.testament),
            'collection': _ETHIOPIAN_ENTRIES_BY_KEY.get(
                (entry.testament, entry.canonical_order), None
            ).section if entry.canon_code == CANON_CODE else None,
            'entry_name': entry.title,
            'entry_order': entry.canonical_order,
        } for entry in entries],
        'coverage': coverage,
    }
