import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User
from app.auth.security import create_token, decode_token, hash_password, hash_token, verify_password
from app.config import Settings


class AuthenticationError(Exception):
    pass


class ConflictError(Exception):
    pass


class AuthService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings

    def register(self, email: str, username: str, password: str) -> tuple[User, str, str]:
        normalized = email.strip().casefold()
        duplicate = self.session.scalar(
            select(User).where((User.email_normalized == normalized) | (User.username == username))
        )
        if duplicate:
            raise ConflictError("Email or username is already registered")
        user = User(email=email.strip(), email_normalized=normalized, username=username, password_hash=hash_password(password))
        self.session.add(user)
        self.session.flush()
        access, refresh = self._new_session(user)
        self.session.commit()
        return user, access, refresh

    def login(self, email: str, password: str) -> tuple[User, str, str]:
        user = self.session.scalar(select(User).where(User.email_normalized == email.strip().casefold()))
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
        access, refresh = self._new_session(user)
        self.session.commit()
        return user, access, refresh

    def refresh(self, token: str) -> tuple[str, str]:
        try:
            claims = decode_token(token, self.settings, "refresh")
            auth_session = self.session.get(AuthSession, uuid.UUID(claims["sid"]))
        except (ValueError, TypeError):
            raise AuthenticationError("Invalid refresh token") from None
        if auth_session is None or auth_session.revoked_at is not None or not hmac_equal(auth_session.refresh_token_hash, hash_token(token)):
            raise AuthenticationError("Invalid refresh token")
        auth_session.revoked_at = datetime.now(UTC)
        user = self.session.get(User, auth_session.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Account is inactive")
        access, refresh = self._new_session(user)
        self.session.commit()
        return access, refresh

    def logout(self, token: str) -> None:
        try:
            claims = decode_token(token, self.settings, "refresh")
            auth_session = self.session.get(AuthSession, uuid.UUID(claims["sid"]))
        except (ValueError, TypeError):
            raise AuthenticationError("Invalid refresh token") from None
        if auth_session is None or not hmac_equal(auth_session.refresh_token_hash, hash_token(token)):
            raise AuthenticationError("Invalid refresh token")
        auth_session.revoked_at = datetime.now(UTC)
        self.session.commit()

    def _new_session(self, user: User) -> tuple[str, str]:
        auth_session = AuthSession(
            user_id=user.id,
            refresh_token_hash="pending",
            expires_at=datetime.now(UTC) + timedelta(days=self.settings.refresh_token_days),
        )
        self.session.add(auth_session)
        self.session.flush()
        refresh = create_token(user_id=user.id, session_id=auth_session.id, token_type="refresh", settings=self.settings)
        auth_session.refresh_token_hash = hash_token(refresh)
        access = create_token(user_id=user.id, session_id=auth_session.id, token_type="access", settings=self.settings)
        return access, refresh


def hmac_equal(left: str, right: str) -> bool:
    import hmac
    return hmac.compare_digest(left, right)
