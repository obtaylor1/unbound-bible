import uuid
from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import User
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
    except (ValueError, TypeError):
        raise unauthorized from None
    if user is None or not user.is_active:
        raise unauthorized
    return user
