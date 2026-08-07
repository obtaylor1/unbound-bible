import uuid
from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User
from app.auth.security import decode_token


bearer = HTTPBearer(auto_error=False)


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_token(credentials.credentials, request.app.state.settings, "access")
        user = session.get(User, uuid.UUID(claims["sub"]))
        auth_session = session.get(AuthSession, uuid.UUID(claims["sid"]))
    except (ValueError, TypeError):
        raise unauthorized from None
    if user is None or not user.is_active or auth_session is None or auth_session.revoked_at is not None:
        raise unauthorized
    return user


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
) -> User | None:
    if credentials is None: return None
    try:
        claims = decode_token(credentials.credentials, request.app.state.settings, "access")
        user = session.get(User, uuid.UUID(claims["sub"]))
        auth_session = session.get(AuthSession, uuid.UUID(claims["sid"]))
        return user if user and user.is_active and auth_session and auth_session.revoked_at is None else None
    except (ValueError, TypeError):
        return None


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return user
