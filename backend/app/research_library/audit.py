from copy import deepcopy
from uuid import UUID

from sqlalchemy.orm import Session

from app.research_library.models import SourceAuditEvent


def append_source_audit_event(
    session: Session,
    *,
    actor_id: UUID,
    action: str,
    prior_state: dict | None,
    resulting_state: dict,
    reason: str | None = None,
    source_edition_id: UUID | None = None,
    source_publication_id: UUID | None = None,
    validation_run_id: str | None = None,
    checksum_metadata: dict | None = None,
) -> SourceAuditEvent:
    if not action or not action.strip():
        raise ValueError('action must be nonblank')
    event = SourceAuditEvent(
        actor_id=actor_id,
        action=action.strip(),
        prior_state=deepcopy(prior_state),
        resulting_state=deepcopy(resulting_state),
        reason=reason,
        source_edition_id=source_edition_id,
        source_publication_id=source_publication_id,
        validation_run_id=validation_run_id,
        checksum_metadata=deepcopy(checksum_metadata),
    )
    session.add(event)
    session.flush()
    return event
