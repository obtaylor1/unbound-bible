import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.studies.models import StudySession, UserNote


class StudyRepository:
    def __init__(self, session: Session, owner_id: uuid.UUID):
        self.session, self.owner_id = session, owner_id

    def note(self, note_id: uuid.UUID) -> UserNote | None:
        return self.session.scalar(select(UserNote).where(UserNote.id == note_id, UserNote.owner_id == self.owner_id))

    def study(self, study_id: uuid.UUID) -> StudySession | None:
        return self.session.scalar(select(StudySession).options(selectinload(StudySession.messages)).where(StudySession.id == study_id, StudySession.owner_id == self.owner_id))
