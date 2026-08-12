"""Bounded, fail-closed retrieval for grounded scripture research."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import quote

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.references import parse_reference
from app.ai.retrieval import retrieve_exact_reference
from app.library.canon import ALIASES, alias_target
from app.research.schemas import ResearchDepth, SourceScope


@dataclass(frozen=True)
class ResearchEvidence:
    id: str
    title: str
    reference: str
    text: str
    source_type: str
    tradition: str
    translation: str | None = None
    date_or_era: str | None = None
    original_language: str | None = None
    open_target: str | None = None
    score: float = 0.0


_DEPTH_LIMITS = {
    ResearchDepth.QUICK.value: 6,
    ResearchDepth.STUDY.value: 12,
    ResearchDepth.DEEP.value: 24,
    ResearchDepth.SCHOLAR.value: 32,
}
_MAX_QUERY_TOKENS = 8
_WESTERN_TRANSLATIONS = frozenset({
    'ASV', 'ESV', 'KJV', 'NASB', 'NIV', 'NRSV', 'WEB',
})
_WESTERN_CANON_WORKS = frozenset({
    'genesis', 'exodus', 'leviticus', 'numbers', 'deuteronomy',
    'joshua', 'judges', 'ruth', '1-samuel', '2-samuel', '1-kings',
    '2-kings', '1-chronicles', '2-chronicles', 'ezra', 'nehemiah',
    'esther', 'job', 'psalms', 'proverbs', 'ecclesiastes',
    'song-of-solomon', 'isaiah', 'jeremiah', 'lamentations', 'ezekiel',
    'daniel', 'hosea', 'joel', 'amos', 'obadiah', 'jonah', 'micah',
    'nahum', 'habakkuk', 'zephaniah', 'haggai', 'zechariah', 'malachi',
    'matthew', 'mark', 'luke', 'john', 'acts', 'romans',
    '1-corinthians', '2-corinthians', 'galatians', 'ephesians',
    'philippians', 'colossians', '1-thessalonians', '2-thessalonians',
    '1-timothy', '2-timothy', 'titus', 'philemon', 'hebrews', 'james',
    '1-peter', '2-peter', '1-john', '2-john', '3-john', 'jude',
    'revelation',
})
_STOP_WORDS = frozenset({
    'and', 'are', 'can', 'did', 'does', 'for', 'from', 'has', 'have',
    'how', 'into', 'its', 'say', 'says', 'that', 'the', 'their', 'then',
    'there', 'these', 'this', 'those', 'was', 'were', 'what', 'when',
    'where', 'which', 'who', 'why', 'with', 'would',
})
_TOKEN_PATTERN = re.compile(r"[^\W_]+(?:'[^\W_]+)?", re.UNICODE)
_COMPOSITE_EDITION = 'EOTC-COMPOSITE-EN'
_COMPOSITE_TRADITION = 'Composite English sources associated with ETHIO81 works'
_WESTERN_BOOK_ALIASES = tuple(sorted(
    alias for alias, work_id in ALIASES.items()
    if work_id in _WESTERN_CANON_WORKS
))


@dataclass(frozen=True)
class _Classification:
    source_type: str
    tradition: str
    title: str
    date_or_era: str | None = None
    original_language: str | None = None


def _value(value: Any) -> str:
    return str(getattr(value, 'value', value))


def _depth_limit(depth: ResearchDepth | str) -> int:
    return _DEPTH_LIMITS.get(_value(depth), _DEPTH_LIMITS[ResearchDepth.DEEP.value])


def _enabled_scopes(source_scopes: Iterable[SourceScope | str]) -> frozenset[str]:
    scopes = {_value(scope) for scope in source_scopes}
    if SourceScope.ALL_SOURCES.value in scopes:
        return frozenset({
            SourceScope.BIBLICAL_CANON.value,
            SourceScope.ETHIOPIAN_TRADITION.value,
        })
    return frozenset(scopes)


def _meaningful_tokens(question: str) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()
    for match in _TOKEN_PATTERN.finditer(question.casefold()):
        token = match.group(0)
        if len(token) < 3 or token in _STOP_WORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
        if len(tokens) == _MAX_QUERY_TOKENS:
            break
    return tuple(tokens)


def _escape_like(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _eligible_ethiopian_editions(session: Session) -> dict[str, set[str]]:
    if not _has_ethiopian_metadata(session):
        return {}
    statement = text('''
        SELECT ews.edition_code, ews.work_id
        FROM edition_work_sources AS ews
        JOIN text_editions AS edition
          ON edition.edition_code = ews.edition_code
        WHERE ews.canon_scope = :canon_scope
          AND ews.verification_status IN (:verified, :provisional)
          AND edition.verification_status IN (:verified, :provisional)
          AND (
              (edition.edition_code = :composite_edition
               AND edition.relationship = :general_reading
               AND edition.source_tradition = :composite_tradition)
              OR
              (edition.relationship = :exact_ethiopian
               AND lower(edition.source_tradition) LIKE :eotc_pattern)
          )
        ORDER BY ews.edition_code, ews.work_id
        LIMIT :metadata_limit
    ''')
    params = {
        'canon_scope': 'ethio81',
        'verified': 'verified',
        'provisional': 'provisional',
        'composite_edition': _COMPOSITE_EDITION,
        'general_reading': 'general_reading',
        'composite_tradition': _COMPOSITE_TRADITION,
        'exact_ethiopian': 'exact_ethiopian',
        'eotc_pattern': '%ethiopian orthodox tewahedo%',
        'metadata_limit': 512,
    }
    try:
        rows = session.execute(statement, params).mappings()
    except SQLAlchemyError:
        session.rollback()
        return {}
    editions: dict[str, set[str]] = {}
    for row in rows:
        editions.setdefault(row['edition_code'], set()).add(row['work_id'])
    return editions


def _scope_eligibility_sql(
    session: Session,
    scopes: frozenset[str],
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if SourceScope.BIBLICAL_CANON.value in scopes:
        translation_names = []
        for index, translation in enumerate(sorted(_WESTERN_TRANSLATIONS)):
            name = f'western_translation_{index}'
            params[name] = translation
            translation_names.append(f':{name}')
        book_names = []
        for index, book in enumerate(_WESTERN_BOOK_ALIASES):
            name = f'western_book_{index}'
            params[name] = book
            book_names.append(f':{name}')
        clauses.append(
            f"(upper(coalesce(translation, '')) IN ({', '.join(translation_names)}) "
            f"AND lower(trim(book)) IN ({', '.join(book_names)}))"
        )

    if SourceScope.ETHIOPIAN_TRADITION.value in scopes:
        for edition_index, (edition, work_ids) in enumerate(
            sorted(_eligible_ethiopian_editions(session).items())
        ):
            edition_name = f'ethiopian_edition_{edition_index}'
            params[edition_name] = edition
            book_names = []
            eligible_aliases = sorted(
                alias for alias, work_id in ALIASES.items()
                if work_id in work_ids
            )
            for book_index, book in enumerate(eligible_aliases):
                name = f'ethiopian_book_{edition_index}_{book_index}'
                params[name] = book
                book_names.append(f':{name}')
            if book_names:
                clauses.append(
                    f"(translation = :{edition_name} AND "
                    f"lower(trim(book)) IN ({', '.join(book_names)}))"
                )
    return (' OR '.join(clauses) if clauses else '0 = 1'), params


def _lexical_rows(
    session: Session,
    question: str,
    limit: int,
    scopes: frozenset[str],
) -> list[dict[str, Any]]:
    tokens = _meaningful_tokens(question)
    if not tokens:
        return []

    match_fragments: list[str] = []
    score_fragments: list[str] = []
    eligibility_sql, eligibility_params = _scope_eligibility_sql(session, scopes)
    params: dict[str, Any] = {
        'candidate_limit': min(limit * 8, 256),
        **eligibility_params,
    }
    for index, token in enumerate(tokens):
        token_name = f'token_{index}'
        like_name = f'like_{index}'
        params[token_name] = token
        params[like_name] = f"%{_escape_like(token)}%"
        match_fragments.append(
            f"(lower(book) = :{token_name} OR "
            f"lower(book) LIKE :{like_name} ESCAPE '\\' OR "
            f"lower(text) LIKE :{like_name} ESCAPE '\\')"
        )
        score_fragments.append(
            f"CASE WHEN lower(book) = :{token_name} THEN 100.0 "
            f"WHEN lower(book) LIKE :{like_name} ESCAPE '\\' THEN 50.0 "
            f"WHEN lower(text) LIKE :{like_name} ESCAPE '\\' THEN 1.0 "
            'ELSE 0.0 END'
        )

    statement = text(f'''
        SELECT id, book, chapter, verse, text, translation,
               ({' + '.join(score_fragments)}) AS match_score
        FROM biblical_texts
        WHERE ({' OR '.join(match_fragments)})
          AND ({eligibility_sql})
        ORDER BY match_score DESC, lower(book), chapter, verse,
                 upper(coalesce(translation, '')), id
        LIMIT :candidate_limit
    ''')
    try:
        return [dict(row) for row in session.execute(statement, params).mappings()]
    except SQLAlchemyError:
        session.rollback()
        return []


def _has_ethiopian_metadata(session: Session) -> bool:
    try:
        tables = set(inspect(session.get_bind()).get_table_names())
    except SQLAlchemyError:
        return False
    return {'text_editions', 'edition_work_sources'} <= tables


def _ethiopian_metadata(
    session: Session,
    translation: str,
    work_id: str,
) -> dict[str, Any] | None:
    statement = text('''
        SELECT ews.source_label, ews.source_language, ews.source_tradition,
               ews.published_year
        FROM edition_work_sources AS ews
        JOIN text_editions AS edition
          ON edition.edition_code = ews.edition_code
        WHERE ews.edition_code = :edition_code
          AND ews.work_id = :work_id
          AND ews.canon_scope = :canon_scope
          AND ews.verification_status IN (:verified, :provisional)
          AND edition.verification_status IN (:verified, :provisional)
          AND (
              (edition.edition_code = :composite_edition
               AND edition.relationship = :general_reading
               AND edition.source_tradition = :composite_tradition)
              OR
              (edition.relationship = :exact_ethiopian
               AND lower(edition.source_tradition) LIKE :eotc_pattern)
          )
        ORDER BY ews.id
        LIMIT :row_limit
    ''')
    params = {
        'edition_code': translation,
        'work_id': work_id,
        'canon_scope': 'ethio81',
        'verified': 'verified',
        'provisional': 'provisional',
        'composite_edition': _COMPOSITE_EDITION,
        'general_reading': 'general_reading',
        'composite_tradition': _COMPOSITE_TRADITION,
        'exact_ethiopian': 'exact_ethiopian',
        'eotc_pattern': '%ethiopian orthodox tewahedo%',
        'row_limit': 1,
    }
    try:
        row = session.execute(statement, params).mappings().first()
    except SQLAlchemyError:
        session.rollback()
        return None
    return dict(row) if row is not None else None


def _classify(
    session: Session,
    *,
    book: str,
    translation: str | None,
    scopes: frozenset[str],
    metadata_available: bool,
    metadata_cache: dict[tuple[str, str], dict[str, Any] | None],
) -> _Classification | None:
    work_id = alias_target(book)
    normalized_translation = (translation or '').upper()
    if (
        SourceScope.BIBLICAL_CANON.value in scopes
        and normalized_translation in _WESTERN_TRANSLATIONS
        and work_id in _WESTERN_CANON_WORKS
    ):
        return _Classification(
            source_type='canonical-scripture',
            tradition='Protestant',
            title=normalized_translation,
        )

    if (
        SourceScope.ETHIOPIAN_TRADITION.value not in scopes
        or not metadata_available
        or not translation
        or work_id is None
    ):
        return None
    cache_key = (translation, work_id)
    if cache_key not in metadata_cache:
        metadata_cache[cache_key] = _ethiopian_metadata(session, translation, work_id)
    metadata = metadata_cache[cache_key]
    if metadata is None:
        return None
    return _Classification(
        source_type='ethiopian-canon',
        tradition=metadata['source_tradition'],
        title=metadata['source_label'],
        date_or_era=(
            str(metadata['published_year'])
            if metadata['published_year'] is not None else None
        ),
        original_language=metadata['source_language'],
    )


def _open_target(book: str, chapter: int, verse: int) -> str:
    return f'/api/v1/texts/{quote(book, safe="")}/{chapter}/{verse}/details'


def _to_evidence(
    session: Session,
    rows: Iterable[dict[str, Any]],
    scopes: frozenset[str],
    limit: int,
) -> list[ResearchEvidence]:
    metadata_available = _has_ethiopian_metadata(session)
    metadata_cache: dict[tuple[str, str], dict[str, Any] | None] = {}
    evidence: list[ResearchEvidence] = []
    for row in rows:
        classification = _classify(
            session,
            book=row['book'],
            translation=row.get('translation'),
            scopes=scopes,
            metadata_available=metadata_available,
            metadata_cache=metadata_cache,
        )
        if classification is None:
            continue
        reference = f"{row['book']} {row['chapter']}:{row['verse']}"
        translation = row.get('translation')
        evidence.append(ResearchEvidence(
            id=f"scripture:{row['id']}",
            title=f'{classification.title} — {reference}',
            reference=reference,
            text=row['text'],
            source_type=classification.source_type,
            tradition=classification.tradition,
            translation=translation,
            date_or_era=classification.date_or_era,
            original_language=classification.original_language,
            open_target=_open_target(row['book'], row['chapter'], row['verse']),
            score=float(row.get('match_score', 0.0)),
        ))
        if len(evidence) == limit:
            break
    return evidence


def _exact_rows(session: Session, question: str) -> list[dict[str, Any]] | None:
    reference = parse_reference(question)
    if reference is None:
        return None
    sources = retrieve_exact_reference(session, reference)
    rows: list[dict[str, Any]] = []
    for source in sources:
        verse = int(source.reference.rsplit(':', 1)[1])
        raw_id = source.id.removeprefix('scripture:')
        rows.append({
            'id': raw_id,
            'book': reference.book,
            'chapter': reference.chapter,
            'verse': verse,
            'text': source.text,
            'translation': source.translation,
            'match_score': 1000.0,
        })
    rows.sort(key=lambda row: (
        row['chapter'], row['verse'], str(row['translation']).upper(), str(row['id'])
    ))
    return rows


def retrieve_research_evidence(
    session: Session,
    question: str,
    source_scopes: Iterable[SourceScope | str],
    depth: ResearchDepth | str,
) -> list[ResearchEvidence]:
    """Retrieve only locally indexed evidence allowed by the requested scopes."""
    limit = _depth_limit(depth)
    scopes = _enabled_scopes(source_scopes)
    exact_rows = _exact_rows(session, question)
    rows = (
        exact_rows
        if exact_rows is not None
        else _lexical_rows(session, question, limit, scopes)
    )
    return _to_evidence(session, rows, scopes, limit)
