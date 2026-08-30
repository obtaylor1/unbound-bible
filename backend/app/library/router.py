"""Read-only canon and installed-edition library endpoints."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
import ipaddress
import re
import unicodedata
from urllib.parse import parse_qsl, unquote, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import get_session, require_admin
from app.auth.models import User
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
from app.library.schemas import (
    AdminVerificationInventoryResponse,
    PublicWorkSourceResponse,
    VERIFICATION_LABELS,
)
from app.library.seed import CANON_CODE
from app.library.verification.registry import validate_https_url


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
_COMPOSITE_EDITION_CODE = 'EOTC-COMPOSITE-EN'
_SHA256 = re.compile(r'[0-9a-f]{64}\Z')
_URL_IN_TEXT = re.compile(r'(?i)\b[a-z][a-z0-9+.-]*://')
_POTENTIAL_ASSIGNMENT = re.compile(
    r'(?<![A-Za-z0-9_-])([A-Za-z][A-Za-z0-9_-]{0,80})\s*(?::|=)\s*\S+'
)
_ACRONYM_CASE_BOUNDARY = re.compile(r'(?<=[A-Z])(?=[A-Z][a-z])')
_CAMEL_CASE_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')
_CREDENTIAL_KEY_WORDS = frozenset({
    'authorization', 'credential', 'credentials', 'passwd', 'password',
    'secret', 'token',
})
_CREDENTIAL_KEY_SUFFIXES = (
    'credential', 'credentials', 'passwd', 'password', 'secret', 'token',
)
_CREDENTIAL_KEY_COMPOUNDS = frozenset({
    'accesskey', 'apikey', 'clientkey', 'consumerkey', 'encryptionkey',
    'privatekey', 'publickey', 'secretkey', 'signingkey',
})
_BEARER_SECRET = re.compile(r'(?i)\bbearer\s+[A-Za-z0-9._~+/-]{6,}')
_STANDALONE_SECRET = re.compile(
    r'(?<![A-Za-z0-9_])(?:'
    r'ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,255}|'
    r'(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,255}|'
    r'(?:AKIA|ASIA)[A-Z0-9]{16}|'
    r'sk-[A-Za-z0-9_-]{20,255}|AIza[A-Za-z0-9_-]{35}|'
    r'xox[baprs]-[A-Za-z0-9-]{20,255}'
    r')(?![A-Za-z0-9_])'
)
_JWT_SECRET = re.compile(
    r'(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{5,}\.'
    r'[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])'
)
_WINDOWS_DRIVE_PATH = re.compile(r'(?i)(?<![A-Za-z0-9])[A-Z]:[\\/]')
_UNC_PATH = re.compile(r'(?:^|[\s="\'(?&])\\\\[^\\/\s]+[\\/]')
_KNOWN_POSIX_PATH = re.compile(
    r'(?i)(?<![A-Za-z0-9])/(?:users|home|private|var|tmp|etc|opt|root|volumes|'
    r'srv|data|mnt|app|workspace)'
    r'(?:/|\b)'
)
_GENERIC_ABSOLUTE_PATH = re.compile(
    r'(?<![A-Za-z0-9:/])/(?!/|\s|[?#])[^/\s?#]+'
    r'(?:/[^\s?#]*)?'
)
_HOME_PATH = re.compile(
    r'(?i)(?:^|[\s="\'(?&])(?:~|\$HOME|\$\{HOME\}|%USERPROFILE%|%HOMEPATH%)'
    r'[\\/]'
)
_TRAVERSAL_PATH = re.compile(r'(?<![A-Za-z0-9])\.\.[\\/]')
_NUMERIC_HOST_COMPONENT = re.compile(r'(?:0[xX][0-9A-Fa-f]+|[0-9]+)\Z')
_VERIFIED_STATUSES = frozenset({
    'verified_exact', 'verified_formatting', 'verified_rebuilt',
})


def _testament_name(value: str) -> str:
    return _TESTAMENT_NAMES.get(value, value)


def _legacy_table_available(session: Session) -> bool:
    return inspect(session.bind).has_table('biblical_texts')


def _edition_payload(edition: TextEdition | None) -> dict | None:
    if edition is None:
        return None
    return {
        'code': edition.edition_code,
        'name': _bounded_text(edition.name, 200, required=True),
        'language': _bounded_text(edition.reading_language, 64, required=True),
        'source_language': _bounded_text(edition.source_language, 64, required=True),
        'script': _bounded_text(edition.script, 64, required=True),
        'publisher': _bounded_text(edition.publisher, 200),
        'license': _bounded_text(edition.license_spdx, 100),
        'attribution': _bounded_text(edition.attribution, 2000),
        'provenance_url': _safe_public_url(edition.provenance_url),
        'source_tradition': _bounded_text(edition.source_tradition, 200),
        'relationship': edition.relationship,
        'versification': _bounded_text(edition.versification, 100),
        'verification_status': edition.verification_status,
    }


def _decoded_variants(value: str) -> tuple[str, ...]:
    variants = [unicodedata.normalize('NFC', value)]
    for _ in range(len(value) + 1):
        decoded = unquote(variants[-1])
        if decoded == variants[-1]:
            break
        variants.append(decoded)
    return tuple(variants)


def _looks_like_local_path(value: str, *, generic_absolute: bool) -> bool:
    lowered = value.casefold()
    if (
        'file://' in lowered
        or _WINDOWS_DRIVE_PATH.search(value)
        or _UNC_PATH.search(value)
        or _KNOWN_POSIX_PATH.search(value)
        or _HOME_PATH.search(value)
        or _TRAVERSAL_PATH.search(value)
    ):
        return True
    return generic_absolute and _GENERIC_ABSOLUTE_PATH.search(value) is not None


def _contains_credential_assignment(value: str) -> bool:
    for match in _POTENTIAL_ASSIGNMENT.finditer(value):
        separated = _ACRONYM_CASE_BOUNDARY.sub('_', match.group(1))
        separated = _CAMEL_CASE_BOUNDARY.sub('_', separated)
        words = tuple(
            word for word in re.split(r'[_-]+', separated.casefold()) if word
        )
        collapsed = ''.join(words)
        if (
            any(word in _CREDENTIAL_KEY_WORDS for word in words)
            or collapsed.endswith(_CREDENTIAL_KEY_SUFFIXES)
            or any(
                collapsed.endswith(compound)
                for compound in _CREDENTIAL_KEY_COMPOUNDS
            )
            or any(
                ''.join(words[index:index + 2]) in _CREDENTIAL_KEY_COMPOUNDS
                for index in range(len(words) - 1)
            )
        ):
            return True
    return False


def _unsafe_text_disclosure(value: str) -> bool:
    for variant in _decoded_variants(value):
        if (
            any(unicodedata.category(character).startswith('C') for character in variant)
            or _URL_IN_TEXT.search(variant)
            or _contains_credential_assignment(variant)
            or _BEARER_SECRET.search(variant)
            or _STANDALONE_SECRET.search(variant)
            or _JWT_SECRET.search(variant)
            or _looks_like_local_path(variant, generic_absolute=True)
        ):
            return True
    return False


def _bounded_text(
    value: str | None,
    maximum: int,
    *,
    required: bool = False,
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return 'Not disclosed' if required else None
    value = value.strip()
    if _unsafe_text_disclosure(value):
        return 'Not disclosed' if required else None
    if len(value) <= maximum:
        return value
    return f'{value[:maximum - 1]}…'


def _unsafe_url_disclosure(value: str) -> bool:
    for variant in _decoded_variants(value):
        if (
            any(unicodedata.category(character).startswith('C') for character in variant)
            or _contains_credential_assignment(variant)
            or _BEARER_SECRET.search(variant)
            or _STANDALONE_SECRET.search(variant)
            or _JWT_SECRET.search(variant)
            or _looks_like_local_path(variant, generic_absolute=False)
        ):
            return True
        try:
            parsed = urlsplit(variant)
            query_values = (
                item for _key, item in parse_qsl(parsed.query, keep_blank_values=True)
            )
            if any(
                _looks_like_local_path(item, generic_absolute=True)
                for item in query_values
            ):
                return True
        except ValueError:
            return True
    return False


def _is_noncanonical_numeric_host(host: str) -> bool:
    components = host.split('.')
    if not components or not all(
        _NUMERIC_HOST_COMPONENT.fullmatch(component) for component in components
    ):
        return False
    return (
        len(components) != 4
        or any(component.casefold().startswith('0x') for component in components)
        or any(len(component) > 1 and component.startswith('0') for component in components)
        or any(int(component) > 255 for component in components)
    )


def _safe_public_url(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        if _unsafe_url_disclosure(value):
            return None
        result = validate_https_url(value)
        host = urlsplit(result).hostname
        if host is None or host in {'localhost', 'localhost.localdomain'} or host.endswith('.local'):
            return None
        if _is_noncanonical_numeric_host(host):
            return None
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return result
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
        ):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _utc_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace('+00:00', 'Z')


def _verification_payload(source: EditionWorkSource) -> dict:
    status = source.verification_status
    return {
        'status': status,
        'label': VERIFICATION_LABELS[status],
        'verified_at': (
            _utc_timestamp(source.reviewed_at) if status in _VERIFIED_STATUSES else None
        ),
    }


def _safe_sha256(value: str | None) -> str | None:
    return value if isinstance(value, str) and _SHA256.fullmatch(value) else None


def _transformation_descriptions(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    descriptions: list[str] = []
    for item in value[:32]:
        candidate: object = item
        if isinstance(item, dict):
            candidate = item.get('description')
        if not isinstance(candidate, str):
            continue
        description = _bounded_text(candidate, 300)
        if description is None:
            continue
        descriptions.append(description)
        if len(descriptions) == 8:
            break
    return descriptions


def _work_source_payload(source: EditionWorkSource | None) -> dict | None:
    if source is None:
        return None
    return {
        'source_key': source.source_key,
        'source_label': _bounded_text(source.source_label, 200, required=True),
        'translator': _bounded_text(source.translator, 200),
        'source_language': _bounded_text(source.source_language, 100, required=True),
        'source_tradition': _bounded_text(source.source_tradition, 200, required=True),
        'published_year': source.published_year,
        'license': _bounded_text(source.license_spdx, 100, required=True),
        'attribution': _bounded_text(source.attribution, 2000, required=True),
        'provenance_url': _safe_public_url(source.provenance_url),
        'rights_url': _safe_public_url(source.rights_url),
        'rights_jurisdiction': _bounded_text(source.rights_jurisdiction, 500),
        'source_edition': _bounded_text(source.source_edition, 200),
        'source_revision': _bounded_text(source.source_revision, 200),
        'fallback': source.fallback,
        'modified': source.modified,
        'modification_note': _bounded_text(source.modification_note, 2000),
        'transformations': _transformation_descriptions(source.transformations),
        'verification_status': source.verification_status,
        'verification': _verification_payload(source),
        'canon_scope': source.canon_scope,
    }


def _source_detail_payload(source: EditionWorkSource) -> dict:
    payload = _work_source_payload(source)
    assert payload is not None
    payload.pop('verification_status')
    return {
        'edition_code': source.edition_code,
        'work_id': source.work_id,
        **payload,
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


@router.get(
    '/library/editions/{edition_code}/works/{work_id}/source',
    response_model=PublicWorkSourceResponse,
)
def edition_work_source(
    edition_code: str = Path(min_length=1, max_length=100),
    work_id: str = Path(min_length=1, max_length=100),
    session: Session = Depends(get_session),
) -> dict:
    source = session.scalar(select(EditionWorkSource).where(
        EditionWorkSource.edition_code == edition_code,
        EditionWorkSource.work_id == work_id,
    ))
    if source is None:
        raise HTTPException(status_code=404, detail='Edition work source not found')
    return _source_detail_payload(source)


@router.get(
    '/library/admin/scripture-verification',
    response_model=AdminVerificationInventoryResponse,
)
def scripture_verification_inventory(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> dict:
    sources = session.execute(
        select(EditionWorkSource, LibraryWork)
        .join(LibraryWork, LibraryWork.id == EditionWorkSource.work_id)
        .where(EditionWorkSource.edition_code == _COMPOSITE_EDITION_CODE)
        .order_by(EditionWorkSource.work_id)
    ).all()
    family_counts = Counter(source.source_key for source, _work in sources)
    status_counts = Counter(source.verification_status for source, _work in sources)
    return {
        'edition_code': _COMPOSITE_EDITION_CODE,
        'total_works': len(sources),
        'family_totals': [
            {'source_key': source_key, 'count': count}
            for source_key, count in sorted(family_counts.items())
        ],
        'status_totals': [
            {
                'status': status,
                'label': label,
                'count': status_counts[status],
            }
            for status, label in VERIFICATION_LABELS.items()
        ],
        'works': [
            {
                'work_id': source.work_id,
                'work_name': _bounded_text(work.title, 200, required=True),
                'source_key': source.source_key,
                'source_label': _bounded_text(
                    source.source_label, 200, required=True
                ),
                'source_edition': _bounded_text(source.source_edition, 200),
                'source_revision': _bounded_text(source.source_revision, 200),
                'provenance_url': _safe_public_url(source.provenance_url),
                'rights_url': _safe_public_url(source.rights_url),
                'license': _bounded_text(
                    source.license_spdx, 100, required=True
                ),
                'fallback': source.fallback,
                'canon_scope': source.canon_scope,
                'artifact_sha256': _safe_sha256(source.artifact_sha256),
                'comparison_report_sha256': _safe_sha256(
                    source.comparison_report_sha256
                ),
                'comparison': {
                    'exact': source.comparison_exact,
                    'formatting': source.comparison_formatting,
                    'missing': source.comparison_missing,
                    'extra': source.comparison_extra,
                    'wording': source.comparison_wording,
                },
                'reviewer': _bounded_text(source.reviewer, 200),
                'reviewed_at': _utc_timestamp(source.reviewed_at),
                'verification': _verification_payload(source),
            }
            for source, work in sources
        ],
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
