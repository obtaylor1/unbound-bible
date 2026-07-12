import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().casefold()
        return self.session.scalar(select(User).where(User.email_normalized == normalized))
