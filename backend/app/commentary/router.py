"""Bounded public commentary reads and administrator publication controls."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import format_datetime, parsedate_to_datetime
from hashlib import sha256
import json
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_session, require_admin
from app.auth.models import User
from app.commentary.ingest.publish import publish_run, rollback_publication
from app.commentary.models import CommentaryImportRun, CommentaryValidationFinding
from app.commentary.schemas import ConfirmationRequest
from app.commentary.service import (
    CommentaryLookupError,
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


def _cached_response(request: Request, document: dict, modified: datetime) -> Response:
    serialized = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
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
    return JSONResponse(document, headers=headers)


@router.get('/sources')
def sources(request: Request, session: Session = Depends(get_session)) -> Response:
    published = list_published_sources(session)
    document = {'sources': [source_document(item) for item in published]}
    modified = max(
        (item.publication.published_at for item in published),
        default=datetime(1970, 1, 1, tzinfo=UTC),
    )
    return _cached_response(request, document, modified)


@router.get('/entries')
def entries(
    request: Request,
    source: str = Query(min_length=1, max_length=64),
    book: str = Query(min_length=1, max_length=200),
    chapter: int = Query(gt=0),
    verse: int | None = Query(default=None, gt=0),
    session: Session = Depends(get_session),
) -> Response:
    try:
        document, modified = passage_document(
            session, source_id=source, book=book, chapter=chapter, verse=verse,
        )
    except CommentaryLookupError as exc:
        raise _error(404, exc.code, exc.message) from exc
    return _cached_response(request, document, modified)


@router.get('/compare')
def compare(
    request: Request,
    sources: list[str] = Query(),
    book: str = Query(min_length=1, max_length=200),
    chapter: int = Query(gt=0),
    verse: int = Query(gt=0),
    session: Session = Depends(get_session),
) -> Response:
    if not 1 <= len(sources) <= 2 or len(set(sources)) != len(sources):
        raise _error(422, 'invalid_sources', 'Choose one or two distinct commentary sources.')
    results, modified_values = [], []
    try:
        for source_id in sources:
            document, modified = passage_document(
                session, source_id=source_id, book=book, chapter=chapter, verse=verse,
            )
            results.append(document)
            modified_values.append(modified)
    except CommentaryLookupError as exc:
        raise _error(404, exc.code, exc.message) from exc
    document = {
        'reference': results[0]['reference'],
        'results': results,
    }
    return _cached_response(request, document, max(modified_values))


@router.get('/admin/imports/{run_id}')
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


@router.post('/admin/imports/{run_id}/publish')
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
    except ValueError as exc:
        session.rollback()
        raise _error(409, 'publication_blocked', str(exc)) from exc
    except Exception:
        session.rollback()
        raise
    return {
        'publication_id': publication.id, 'source_id': publication.source_id,
        'edition_id': str(publication.edition_id), 'version': publication.version,
        'active': publication.active,
    }


@router.post('/admin/publications/{publication_id}/rollback')
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
    except ValueError as exc:
        session.rollback()
        message = str(exc)
        if message == 'Commentary publication was not found.':
            raise _error(404, 'publication_not_found', message) from exc
        raise _error(409, 'rollback_blocked', message) from exc
    except Exception:
        session.rollback()
        raise
    return {
        'publication_id': publication.id, 'source_id': publication.source_id,
        'edition_id': str(publication.edition_id), 'version': publication.version,
        'active': publication.active,
    }
