"""HTTP boundary for grounded scripture research."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.factory import create_chat_provider
from app.auth.dependencies import get_current_user, get_optional_user, get_session
from app.auth.models import User
from app.research.event_catalog import EventCatalogError, EventRecord, list_events
from app.research.models import (
    MAX_TRAIL_DEPTH,
    ResearchNode,
    ResearchTrailError,
    build_trail_snapshot,
    create_research_node,
    get_owned_research_node,
)
from app.research.retrieval import retrieve_research_evidence
from app.research.schemas import ResearchQueryRequest, ResearchResponse, TrailNode
from app.research.service import ResearchService, ResearchServiceError
from app.security.rate_limits import enforce_rate_limit


router = APIRouter(prefix='/research', tags=['Scripture research'])


def _problem(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={'code': code, 'message': message},
    )


def _rollback(session: Session) -> None:
    """Restore the request transaction before returning a safe HTTP error."""

    try:
        session.rollback()
    except Exception:
        # The mapped HTTP error remains authoritative even when the failed
        # transaction can no longer be rolled back. The request-scoped session
        # is discarded by its dependency context and must not be reused.
        pass


def _trail_error(error: ResearchTrailError) -> HTTPException:
    if error.code == 'parent_not_found':
        return _problem(404, 'not_found', 'Research trail node not found.')
    return _problem(422, error.code, 'The research trail request is invalid.')


def _node_summary(node: ResearchNode) -> dict[str, Any]:
    return {
        'id': str(node.id),
        'parent_node_id': str(node.parent_id) if node.parent_id else None,
        'question': node.question,
        'mode': node.mode,
        'created_at': node.created_at.isoformat() if node.created_at else None,
        'updated_at': node.updated_at.isoformat() if node.updated_at else None,
    }


@router.post(
    '/query',
    response_model=ResearchResponse,
    dependencies=[Depends(enforce_rate_limit('ai', 'ai_rate_limit', 60))],
)
async def query(
    payload: ResearchQueryRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User | None = Depends(get_optional_user),
) -> ResearchResponse:
    """Retrieve, validate, audit, and optionally persist one research response."""

    if user is None and payload.parent_node_id is not None:
        raise _problem(
            422,
            'guest_parent_not_allowed',
            'Sign in to continue a saved research trail.',
        )

    parent: ResearchNode | None = None
    if user is not None and payload.parent_node_id is not None:
        try:
            parent = get_owned_research_node(
                session, payload.parent_node_id, user.id
            )
        except SQLAlchemyError as error:
            _rollback(session)
            raise _problem(
                503, 'research_unavailable', 'Research is temporarily unavailable.'
            ) from error
        if parent is None:
            _rollback(session)
            raise _problem(404, 'not_found', 'Research trail node not found.')

    try:
        settings = request.app.state.settings
        provider = create_chat_provider(
            settings.ai_chat_provider,
            settings,
            request.app.state.http_client,
        )
        response = await ResearchService(
            retrieve_research_evidence,
            provider,
            session,
            user,
        ).query(payload)

        if user is not None:
            node = create_research_node(
                session,
                user.id,
                payload,
                response,
                parent=parent,
            )
            response.trail_node = TrailNode(
                id=node.id,
                parent_node_id=node.parent_id,
                question=node.question,
            )
        session.commit()
        return response
    except ResearchTrailError as error:
        _rollback(session)
        raise _trail_error(error) from error
    except ValueError as error:
        _rollback(session)
        message = str(error)
        if 'study must belong' in message:
            raise _problem(404, 'not_found', 'Study not found.') from error
        if message in {
            'request session and study must match',
            'parent and child must belong to the same study',
        }:
            raise _problem(
                422, 'invalid_trail', 'The research trail request is invalid.'
            ) from error
        raise _problem(
            503, 'research_unavailable', 'Research is temporarily unavailable.'
        ) from error
    except (ResearchServiceError, SQLAlchemyError) as error:
        _rollback(session)
        raise _problem(
            503, 'research_unavailable', 'Research is temporarily unavailable.'
        ) from error


def _event_payload(event: EventRecord) -> dict[str, Any]:
    return {
        'id': event.id,
        'title': event.title,
        'description': event.description,
        'reference': event.reference,
        'source_ids': list(event.source_ids),
        'people': list(event.people),
        'places': list(event.places),
    }


@router.get('/events')
def events(
    q: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, list[dict[str, Any]]]:
    """List only reviewed events backed by complete local passages."""

    try:
        return {'events': [_event_payload(event) for event in list_events(session, q)]}
    except EventCatalogError as error:
        if error.code == 'invalid_query':
            raise _problem(422, error.code, str(error)) from error
        if error.code == 'catalog_unavailable':
            _rollback(session)
            raise _problem(503, error.code, str(error)) from error
        raise _problem(422, error.code, 'The event request is invalid.') from error
    except SQLAlchemyError as error:
        _rollback(session)
        raise _problem(
            503, 'catalog_unavailable', 'The verified event catalog is unavailable.'
        ) from error


@router.get('/trail/{node_id}')
def trail(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return an owner-scoped, bounded branch without stored response prose."""

    try:
        node = get_owned_research_node(session, node_id, user.id)
        if node is None:
            raise _problem(404, 'not_found', 'Research trail node not found.')
        snapshot = build_trail_snapshot(session, node_id, user.id)
        if snapshot is None:
            raise _problem(404, 'not_found', 'Research trail node not found.')
        ancestry = snapshot['ancestry']
        # The persistence helper returns an inclusive path. The API names the
        # selected node separately so clients cannot accidentally duplicate it.
        return {
            'ancestry': ancestry[:-1],
            'active': _node_summary(node),
            'children': snapshot['children'][:MAX_TRAIL_DEPTH],
            'children_truncated': snapshot['children_truncated'],
        }
    except HTTPException:
        raise
    except ResearchTrailError as error:
        _rollback(session)
        raise _trail_error(error) from error
    except SQLAlchemyError as error:
        _rollback(session)
        raise _problem(
            503, 'research_unavailable', 'Research is temporarily unavailable.'
        ) from error
