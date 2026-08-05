"""Bounded public commentary reads and administrator publication controls."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import format_datetime, parsedate_to_datetime
from hashlib import sha256
import json
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_session, require_admin
from app.auth.models import User
from app.commentary.ingest.publish import (
    CommentaryPublicationConflict,
    is_commentary_publication_conflict,
    publish_run,
    rollback_publication,
)
from app.commentary.models import CommentaryImportRun, CommentaryValidationFinding
from app.commentary.schemas import (
    CommentaryCompareResponse,
    CommentaryImportStatusResponse,
    CommentaryPassageResponse,
    CommentaryPublicationActionResponse,
    CommentarySourcesResponse,
    ConfirmationRequest,
)
from app.commentary.service import (
    CommentaryLookupError,
    MAX_BODY_CHARACTERS,
    MAX_CHAPTER,
    MAX_ENTRIES,
    MAX_VERSE,
    list_published_sources,
    passage_document,
    source_document,
)


router = APIRouter(prefix='/commentaries', tags=['commentaries'])
PUBLIC_CACHE_CONTROL = 'public, max-age=60, must-revalidate'


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, detail={'code': code, 'message': message})


def _http_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _cached_response(
    request: Request,
    document: dict,
    modified: datetime,
    response_model: type[BaseModel],
) -> Response:
    validated = response_model.model_validate(document).model_dump(mode='json')
    serialized = json.dumps(
        validated, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
    )
    etag = f'"{sha256(serialized.encode("utf-8")).hexdigest()}"'
    modified_utc = _http_datetime(modified).replace(microsecond=0)
    headers = {
        'ETag': etag,
        'Last-Modified': format_datetime(modified_utc, usegmt=True),
        'Cache-Control': PUBLIC_CACHE_CONTROL,
    }
    if_none_match = request.headers.get('if-none-match')
    if if_none_match is not None:
        validators = {
            token.strip().removeprefix('W/') for token in if_none_match.split(',')
        }
        if '*' in validators or etag in validators:
            return Response(status_code=304, headers=headers)
    if_modified_since = request.headers.get('if-modified-since')
    if if_none_match is None and if_modified_since:
        try:
            if parsedate_to_datetime(if_modified_since) >= modified_utc:
                return Response(status_code=304, headers=headers)
        except (TypeError, ValueError, OverflowError):
            pass
    return Response(serialized, media_type='application/json', headers=headers)


@router.get('/sources', response_model=CommentarySourcesResponse)
def sources(request: Request, session: Session = Depends(get_session)) -> Response:
    published = list_published_sources(session)
    document = {'sources': [source_document(item) for item in published]}
    modified = max(
        (item.publication.published_at for item in published),
        default=datetime(1970, 1, 1, tzinfo=UTC),
    )
    return _cached_response(request, document, modified, CommentarySourcesResponse)


@router.get('/entries', response_model=CommentaryPassageResponse)
def entries(
    request: Request,
    source: str = Query(min_length=1, max_length=64),
    book: str = Query(min_length=1, max_length=200),
    chapter: int = Query(gt=0, le=MAX_CHAPTER),
    verse: int | None = Query(default=None, gt=0, le=MAX_VERSE),
    session: Session = Depends(get_session),
) -> Response:
    try:
        document, modified = passage_document(
            session, source_id=source, book=book, chapter=chapter, verse=verse,
        )
    except CommentaryLookupError as exc:
        raise _error(404, exc.code, exc.message) from exc
    return _cached_response(request, document, modified, CommentaryPassageResponse)


@router.get('/compare', response_model=CommentaryCompareResponse)
def compare(
    request: Request,
    sources: list[str] = Query(),
    book: str = Query(min_length=1, max_length=200),
    chapter: int = Query(gt=0, le=MAX_CHAPTER),
    verse: int = Query(gt=0, le=MAX_VERSE),
    session: Session = Depends(get_session),
) -> Response:
    if not 1 <= len(sources) <= 2 or len(set(sources)) != len(sources):
        raise _error(422, 'invalid_sources', 'Choose one or two distinct commentary sources.')
    results, modified_values = [], []
    remaining_entries = MAX_ENTRIES
    remaining_body_characters = MAX_BODY_CHARACTERS
    try:
        for source_id in sources:
            document, modified = passage_document(
                session,
                source_id=source_id,
                book=book,
                chapter=chapter,
                verse=verse,
                max_entries=remaining_entries,
                max_body_characters=remaining_body_characters,
            )
            results.append(document)
            modified_values.append(modified)
            remaining_entries -= len(document['entries'])
            remaining_body_characters -= sum(
                len(entry['body']) for entry in document['entries']
            )
    except CommentaryLookupError as exc:
        raise _error(404, exc.code, exc.message) from exc
    document = {
        'reference': results[0]['reference'],
        'results': results,
    }
    return _cached_response(
        request, document, max(modified_values), CommentaryCompareResponse,
    )


@router.get('/admin/imports/{run_id}', response_model=CommentaryImportStatusResponse)
def import_status(
    run_id: UUID,
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    run = session.get(CommentaryImportRun, run_id)
    if run is None:
        raise _error(404, 'import_not_found', 'Commentary import run was not found.')
    findings = session.scalars(
        select(CommentaryValidationFinding)
        .where(CommentaryValidationFinding.run_id == run.id)
        .order_by(CommentaryValidationFinding.id)
    ).all()
    return {
        'id': str(run.id), 'source_id': run.source_id, 'status': run.status,
        'staged_count': run.staged_count, 'error_count': run.error_count,
        'warning_count': run.warning_count, 'metadata': run.metadata_snapshot,
        'findings': [{
            'severity': item.severity, 'code': item.code, 'work_id': item.work_id,
            'chapter': item.chapter, 'verse': item.verse, 'message': item.message,
        } for item in findings],
    }


def _require_confirmation(body: ConfirmationRequest | None) -> None:
    if body is None or not body.confirm:
        raise _error(400, 'confirmation_required', 'Set confirm to true to continue.')


def _publication_conflict() -> HTTPException:
    return _error(
        409,
        'publication_conflict',
        'Another publication operation won the race. Refresh and try again.',
    )


@router.post(
    '/admin/imports/{run_id}/publish',
    response_model=CommentaryPublicationActionResponse,
)
def publish_import(
    run_id: UUID,
    body: ConfirmationRequest | None = Body(default=None),
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    _require_confirmation(body)
    if session.get(CommentaryImportRun, run_id) is None:
        raise _error(404, 'import_not_found', 'Commentary import run was not found.')
    try:
        publication = publish_run(session, run_id)
        session.commit()
    except CommentaryPublicationConflict as exc:
        session.rollback()
        raise _publication_conflict() from exc
    except ValueError as exc:
        session.rollback()
        raise _error(409, 'publication_blocked', str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        if is_commentary_publication_conflict(exc):
            raise _publication_conflict() from exc
        raise
    except Exception:
        session.rollback()
        raise
    return {
        'publication_id': publication.id, 'source_id': publication.source_id,
        'edition_id': str(publication.edition_id), 'version': publication.version,
        'active': publication.active,
    }


@router.post(
    '/admin/publications/{publication_id}/rollback',
    response_model=CommentaryPublicationActionResponse,
)
def rollback(
    publication_id: int,
    body: ConfirmationRequest | None = Body(default=None),
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    _require_confirmation(body)
    try:
        publication = rollback_publication(session, publication_id)
        session.commit()
    except CommentaryPublicationConflict as exc:
        session.rollback()
        raise _publication_conflict() from exc
    except ValueError as exc:
        session.rollback()
        message = str(exc)
        if message == 'Commentary publication was not found.':
            raise _error(404, 'publication_not_found', message) from exc
        raise _error(409, 'rollback_blocked', message) from exc
    except IntegrityError as exc:
        session.rollback()
        if is_commentary_publication_conflict(exc):
            raise _publication_conflict() from exc
        raise
    except Exception:
        session.rollback()
        raise
    return {
        'publication_id': publication.id, 'source_id': publication.source_id,
        'edition_id': str(publication.edition_id), 'version': publication.version,
        'active': publication.active,
    }
