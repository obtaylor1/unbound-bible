import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user, get_session
from app.auth.models import User
from app.studies.models import StudyMessage, StudySession, StudySource, UserNote
from app.studies.repository import StudyRepository
from app.studies.schemas import MessageCreate, MessageRead, NoteCreate, NoteRead, NoteUpdate, SourceCreate, SourceRead, StudyCreate, StudyRead, StudyUpdate


router = APIRouter(tags=["studies"])


@router.get("/notes", response_model=list[NoteRead])
def list_notes(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.scalars(select(UserNote).where(UserNote.owner_id == user.id).order_by(UserNote.updated_at.desc())).all()


@router.post("/notes", response_model=NoteRead, status_code=201)
def create_note(payload: NoteCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    note = UserNote(owner_id=user.id, **payload.model_dump())
    session.add(note); session.commit(); session.refresh(note)
    return note


def owned_note(note_id: uuid.UUID, user: User, session: Session) -> UserNote:
    note = StudyRepository(session, user.id).note(note_id)
    if not note: raise HTTPException(404, "Note not found")
    return note


@router.get("/notes/{note_id}", response_model=NoteRead)
def get_note(note_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return owned_note(note_id, user, session)


@router.put("/notes/{note_id}", response_model=NoteRead)
def update_note(note_id: uuid.UUID, payload: NoteUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    note = owned_note(note_id, user, session)
    for key, value in payload.model_dump().items(): setattr(note, key, value)
    session.commit(); session.refresh(note)
    return note


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    session.delete(owned_note(note_id, user, session)); session.commit()
    return Response(status_code=204)


@router.get("/studies", response_model=list[StudyRead])
def list_studies(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.scalars(select(StudySession).options(selectinload(StudySession.messages)).where(StudySession.owner_id == user.id).order_by(StudySession.updated_at.desc())).all()


@router.post("/studies", response_model=StudyRead, status_code=201)
def create_study(payload: StudyCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    study = StudySession(owner_id=user.id, title=payload.title)
    session.add(study); session.commit(); session.refresh(study)
    return study


def owned_study(study_id: uuid.UUID, user: User, session: Session) -> StudySession:
    study = StudyRepository(session, user.id).study(study_id)
    if not study: raise HTTPException(404, "Study not found")
    return study


@router.get("/studies/{study_id}", response_model=StudyRead)
def get_study(study_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return owned_study(study_id, user, session)


@router.put("/studies/{study_id}", response_model=StudyRead)
def update_study(study_id: uuid.UUID, payload: StudyUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    study = owned_study(study_id, user, session); study.title = payload.title
    session.commit(); session.refresh(study)
    return study


@router.delete("/studies/{study_id}", status_code=204)
def delete_study(study_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    session.delete(owned_study(study_id, user, session)); session.commit()
    return Response(status_code=204)


@router.post("/studies/{study_id}/messages", response_model=MessageRead, status_code=201)
def add_message(study_id: uuid.UUID, payload: MessageCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    study = owned_study(study_id, user, session)
    message = StudyMessage(study_id=study.id, **payload.model_dump())
    session.add(message); session.commit(); session.refresh(message)
    return message


@router.post("/studies/{study_id}/sources", response_model=SourceRead, status_code=201)
def add_source(study_id: uuid.UUID, payload: SourceCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    study = owned_study(study_id, user, session)
    source = StudySource(study_id=study.id, **payload.model_dump())
    session.add(source); session.commit(); session.refresh(source)
    return source
