import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.sharing.models import SharedStudy
from app.studies.models import StudySession


def identifier_hash(identifier: str) -> str:
    return hashlib.sha256(identifier.encode()).hexdigest()


def find_share(session: Session, identifier: str) -> SharedStudy | None:
    return session.scalar(select(SharedStudy).where(SharedStudy.public_id_hash == identifier_hash(identifier)))


def create_snapshot(session: Session, owner_id: uuid.UUID, study_id: uuid.UUID, visibility: str, title: str | None = None) -> tuple[SharedStudy, str]:
    study = session.scalar(select(StudySession).options(selectinload(StudySession.messages), selectinload(StudySession.sources)).where(StudySession.id == study_id, StudySession.owner_id == owner_id))
    if not study: raise LookupError('Study not found')
    identifier = secrets.token_urlsafe(18)
    share = SharedStudy(owner_id=owner_id, source_study_id=study.id, public_id_hash=identifier_hash(identifier), public_id=identifier, title=title or study.title, visibility=visibility,
        messages_snapshot=[{'role': item.role, 'content': item.content} for item in study.messages],
        sources_snapshot=[{'title': item.title, 'url': item.url, 'citation': item.citation} for item in study.sources])
    session.add(share); session.commit(); session.refresh(share)
    return share, identifier


def revoke(session: Session, share: SharedStudy) -> None:
    share.revoked_at = datetime.now(UTC); session.commit()
