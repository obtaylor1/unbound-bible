import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.notifications.models import Notification, NotificationPreference


def update_preferences(session: Session, user_id: uuid.UUID | str, disabled_event_types: list[str]) -> NotificationPreference:
    user_id = uuid.UUID(str(user_id)); preference = session.get(NotificationPreference, user_id)
    if preference is None: preference = NotificationPreference(user_id=user_id, disabled_event_types=disabled_event_types); session.add(preference)
    else: preference.disabled_event_types = disabled_event_types
    session.commit(); return preference


def create_notification(session: Session, *, recipient_id, event_type: str, target_type: str, target_id: str, message: str, deduplication_key: str, actor_id=None) -> Notification | None:
    recipient_id = uuid.UUID(str(recipient_id)); actor_id = uuid.UUID(str(actor_id)) if actor_id else None
    preference = session.get(NotificationPreference, recipient_id)
    if preference and event_type in (preference.disabled_event_types or []): return None
    existing = session.scalar(select(Notification).where(Notification.recipient_id == recipient_id, Notification.deduplication_key == deduplication_key))
    if existing: return existing
    notification = Notification(recipient_id=recipient_id, actor_id=actor_id, event_type=event_type, target_type=target_type, target_id=str(target_id), message=message, deduplication_key=deduplication_key)
    session.add(notification)
    try: session.commit()
    except IntegrityError:
        session.rollback(); return session.scalar(select(Notification).where(Notification.recipient_id == recipient_id, Notification.deduplication_key == deduplication_key))
    session.refresh(notification); return notification
