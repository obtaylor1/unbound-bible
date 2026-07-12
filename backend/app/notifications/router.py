import uuid
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from app.auth.dependencies import get_current_user, get_session
from app.auth.models import User
from app.notifications.models import Notification, NotificationPreference
from app.notifications.service import update_preferences


router = APIRouter(prefix='/notifications', tags=['notifications'])


def serialize(item: Notification) -> dict:
    return {'id': item.id, 'event_type': item.event_type, 'target_type': item.target_type, 'target_id': item.target_id, 'message': item.message, 'created_at': item.created_at, 'read_at': item.read_at}


@router.get('')
def inbox(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return [serialize(item) for item in session.scalars(select(Notification).where(Notification.recipient_id == user.id).order_by(Notification.created_at.desc()).limit(100)).all()]


@router.get('/unread-count')
def unread_count(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return {'count': session.scalar(select(func.count()).select_from(Notification).where(Notification.recipient_id == user.id, Notification.read_at.is_(None))) or 0}


@router.patch('/{notification_id}/read')
def mark_read(notification_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = session.scalar(select(Notification).where(Notification.id == notification_id, Notification.recipient_id == user.id))
    if not item: raise HTTPException(404, 'Notification not found')
    item.read_at = datetime.now(UTC); session.commit(); session.refresh(item); return serialize(item)


@router.post('/read-all')
def read_all(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    session.execute(update(Notification).where(Notification.recipient_id == user.id, Notification.read_at.is_(None)).values(read_at=datetime.now(UTC))); session.commit(); return {'status': 'ok'}


class PreferenceUpdate(BaseModel):
    disabled_event_types: list[str]


@router.get('/preferences')
def preferences(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = session.get(NotificationPreference, user.id); return {'disabled_event_types': item.disabled_event_types if item else []}


@router.put('/preferences')
def set_preferences(payload: PreferenceUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = update_preferences(session, user.id, payload.disabled_event_types); return {'disabled_event_types': item.disabled_event_types}
