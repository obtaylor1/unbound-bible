from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_session
from app.auth.models import User
from app.auth.schemas import LoginRequest, ProfileUpdate, RefreshRequest, TokenPair, UserCreate, UserRead
from app.auth.service import AuthService, AuthenticationError, ConflictError
from app.security.rate_limits import enforce_rate_limit


router = APIRouter(prefix="/auth", tags=["authentication"])


def service(request: Request, session: Session = Depends(get_session)) -> AuthService:
    return AuthService(session, request.app.state.settings)


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED, dependencies=[Depends(enforce_rate_limit('register', 'auth_rate_limit', 3600))])
def register(payload: UserCreate, auth: AuthService = Depends(service)) -> TokenPair:
    try:
        _, access, refresh = auth.register(payload.email, payload.username, payload.password)
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenPair, dependencies=[Depends(enforce_rate_limit('login', 'auth_rate_limit', 900))])
def login(payload: LoginRequest, auth: AuthService = Depends(service)) -> TokenPair:
    try:
        _, access, refresh = auth.login(payload.email, payload.password)
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, auth: AuthService = Depends(service)) -> TokenPair:
    try:
        access, refresh_token = auth.refresh(payload.refresh_token)
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return TokenPair(access_token=access, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, auth: AuthService = Depends(service)) -> Response:
    try:
        auth.logout(payload.refresh_token)
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/profile", response_model=UserRead)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> User:
    duplicate = session.scalar(select(User).where(User.username == payload.username, User.id != user.id))
    if duplicate:
        raise HTTPException(status_code=409, detail="Username is already registered")
    user.username = payload.username
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
