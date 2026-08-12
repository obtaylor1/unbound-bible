"""Durable, owner-scoped history for validated scripture research responses."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database import Base
from app.research.schemas import ResearchDepth, ResearchMode, ResearchQueryRequest
from app.studies.models import StudySession


_RESEARCH_MODES = tuple(mode.value for mode in ResearchMode)
_RESEARCH_DEPTHS = tuple(depth.value for depth in ResearchDepth)


def _sql_values(values: tuple[str, ...]) -> str:
    return ', '.join(repr(value) for value in values)


class ResearchNode(Base):
    """A display/history snapshot; prior response prose is never retrieval evidence."""

    __tablename__ = 'research_nodes'
    __table_args__ = (
        CheckConstraint(
            'length(question) BETWEEN 1 AND 10000',
            name='ck_research_nodes_question_length',
        ),
        CheckConstraint(
            f'mode IN ({_sql_values(_RESEARCH_MODES)})',
            name='ck_research_nodes_mode',
        ),
        CheckConstraint(
            f'depth IN ({_sql_values(_RESEARCH_DEPTHS)})',
            name='ck_research_nodes_depth',
        ),
        Index('ix_research_nodes_owner_updated', 'owner_id', 'updated_at'),
        Index('ix_research_nodes_parent_id', 'parent_id'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    study_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey('study_sessions.id', ondelete='SET NULL'),
        nullable=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey('research_nodes.id', ondelete='CASCADE'),
        nullable=True,
    )
    question: Mapped[str] = mapped_column(String(10_000), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    source_scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    depth: Mapped[str] = mapped_column(String(30), nullable=False)
    response_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def _identifier(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _snapshot_dict(response_snapshot: Any) -> dict[str, Any]:
    if hasattr(response_snapshot, 'model_dump'):
        value = response_snapshot.model_dump(mode='json')
    else:
        value = deepcopy(response_snapshot)
    if not isinstance(value, dict):
        raise ValueError('response snapshot must be a JSON object')
    return value


def create_research_node(
    session: Session,
    owner_id: uuid.UUID,
    request: ResearchQueryRequest,
    response_snapshot: Any,
    study_id: uuid.UUID | None = None,
    parent: ResearchNode | uuid.UUID | None = None,
) -> ResearchNode:
    """Create a node after enforcing owner and branch boundaries.

    The response snapshot is retained only for display/history. Callers must never
    reuse its prose as evidence for a later research response.
    """

    requested_study_id = _identifier(request.session_id)
    explicit_study_id = _identifier(study_id)
    if (
        requested_study_id is not None
        and explicit_study_id is not None
        and requested_study_id != explicit_study_id
    ):
        raise ValueError('request session and study must match')
    resolved_study_id = explicit_study_id or requested_study_id

    requested_parent_id = _identifier(request.parent_node_id)
    supplied_parent_id = _identifier(
        parent.id if isinstance(parent, ResearchNode) else parent
    )
    if (
        requested_parent_id is not None
        and supplied_parent_id is not None
        and requested_parent_id != supplied_parent_id
    ):
        raise ValueError('request parent and supplied parent must match')
    parent_id = supplied_parent_id or requested_parent_id
    resolved_parent: ResearchNode | None = None
    if isinstance(parent, ResearchNode):
        resolved_parent = parent
        if resolved_parent.owner_id != owner_id:
            raise ValueError('parent must belong to the research owner')
    elif parent_id is not None:
        resolved_parent = get_owned_research_node(session, parent_id, owner_id)
        if resolved_parent is None:
            raise ValueError('parent must belong to the research owner')

    if resolved_parent is not None:
        if resolved_study_id is None:
            resolved_study_id = resolved_parent.study_id
        elif resolved_parent.study_id != resolved_study_id:
            raise ValueError('parent and child must belong to the same study')

    if resolved_study_id is not None:
        study = session.scalar(
            select(StudySession).where(
                StudySession.id == resolved_study_id,
                StudySession.owner_id == owner_id,
            )
        )
        if study is None:
            raise ValueError('study must belong to the research owner')

    node = ResearchNode(
        owner_id=owner_id,
        study_id=resolved_study_id,
        parent_id=parent_id,
        question=request.question,
        mode=request.mode.value,
        source_scopes=[scope.value for scope in request.source_scopes],
        depth=request.depth.value,
        response_snapshot=_snapshot_dict(response_snapshot),
    )
    session.add(node)
    session.flush()
    return node


def get_owned_research_node(
    session: Session,
    node_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> ResearchNode | None:
    """Resolve a research node without revealing another owner's records."""

    return session.scalar(
        select(ResearchNode).where(
            ResearchNode.id == node_id,
            ResearchNode.owner_id == owner_id,
        )
    )


def _trail_node(node: ResearchNode) -> dict[str, Any]:
    return {
        'id': str(node.id),
        'parent_node_id': str(node.parent_id) if node.parent_id else None,
        'question': node.question,
        'mode': node.mode,
        'created_at': node.created_at.isoformat() if node.created_at else None,
        'updated_at': node.updated_at.isoformat() if node.updated_at else None,
    }


def build_trail_snapshot(
    session: Session,
    node_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> dict[str, list[dict[str, Any]]] | None:
    """Return the active ancestry and direct children in deterministic order."""

    current = get_owned_research_node(session, node_id, owner_id)
    if current is None:
        return None

    reverse_ancestry: list[dict[str, Any]] = []
    visited: set[uuid.UUID] = set()
    cursor: ResearchNode | None = current
    while cursor is not None and cursor.id not in visited:
        visited.add(cursor.id)
        reverse_ancestry.append(_trail_node(cursor))
        cursor = (
            get_owned_research_node(session, cursor.parent_id, owner_id)
            if cursor.parent_id is not None
            else None
        )

    children = session.scalars(
        select(ResearchNode)
        .where(
            ResearchNode.parent_id == node_id,
            ResearchNode.owner_id == owner_id,
        )
        .order_by(ResearchNode.updated_at.desc(), ResearchNode.id.asc())
    ).all()
    return {
        'ancestry': list(reversed(reverse_ancestry)),
        'children': [_trail_node(child) for child in children],
    }
