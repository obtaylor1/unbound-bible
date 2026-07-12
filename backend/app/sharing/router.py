import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_optional_user, get_session
from app.auth.models import User
from app.sharing.models import SharedStudy
from app.sharing.policies import can_view, is_owner
from app.sharing.schemas import ShareCreate, ShareUpdate
from app.sharing.service import create_snapshot, find_share, revoke
from app.studies.models import StudyMessage, StudySession
from app.notifications.service import create_notification
from app.security.rate_limits import enforce_rate_limit


router = APIRouter(prefix='/shares', tags=['sharing'])


def serialize(share: SharedStudy, identifier: str) -> dict:
    return {'share_id': identifier, 'title': share.title, 'visibility': share.visibility, 'messages': share.messages_snapshot, 'sources': share.sources_snapshot, 'created_at': share.created_at, 'revoked': share.revoked_at is not None}


@router.post('', status_code=201, dependencies=[Depends(enforce_rate_limit('sharing', 'sharing_rate_limit', 3600))])
def create(payload: ShareCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    try: share, identifier = create_snapshot(session, user.id, payload.study_id, payload.visibility, payload.title)
    except LookupError as error: raise HTTPException(404, str(error)) from error
    return serialize(share, identifier)


@router.get('/public')
def public_shares(session: Session = Depends(get_session)):
    shares = session.scalars(select(SharedStudy).where(SharedStudy.visibility == 'public', SharedStudy.revoked_at.is_(None)).order_by(SharedStudy.created_at.desc()).limit(50)).all()
    return [{'share_id': share.public_id, 'title': share.title, 'created_at': share.created_at} for share in shares]


@router.get('/{share_id}')
def get_share(share_id: str, user: User | None = Depends(get_optional_user), session: Session = Depends(get_session)):
    share = find_share(session, share_id)
    if not share or not can_view(share, user): raise HTTPException(404, 'Shared study not found')
    if share.revoked_at is not None: raise HTTPException(410, 'This shared study is no longer available')
    return serialize(share, share_id)


def owner_share(share_id: str, user: User, session: Session) -> SharedStudy:
    share = find_share(session, share_id)
    if not share or not is_owner(share, user): raise HTTPException(404, 'Shared study not found')
    return share


@router.patch('/{share_id}')
def update(share_id: str, payload: ShareUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    share = owner_share(share_id, user, session); share.visibility = payload.visibility; session.commit(); session.refresh(share)
    return serialize(share, share_id)


@router.delete('/{share_id}', status_code=204)
def delete(share_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    session.delete(owner_share(share_id, user, session)); session.commit(); return Response(status_code=204)


@router.post('/{share_id}/revoke')
def revoke_share(share_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    share = owner_share(share_id, user, session); revoke(session, share); return serialize(share, share_id)


@router.post('/{share_id}/duplicate', status_code=201)
def duplicate(share_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    share = find_share(session, share_id)
    if not share or not can_view(share, user) or share.revoked_at is not None: raise HTTPException(404, 'Shared study not found')
    study = StudySession(owner_id=user.id, title=share.title); session.add(study); session.flush()
    for item in share.messages_snapshot: session.add(StudyMessage(study_id=study.id, role=item['role'], content=item['content']))
    session.commit(); session.refresh(study)
    if user.id != share.owner_id:
        create_notification(session, recipient_id=share.owner_id, actor_id=user.id, event_type='shared_study_activity', target_type='share', target_id=share_id, message='Someone saved a copy of your shared study.', deduplication_key=f'share-duplicate:{share.id}:{user.id}')
    return {'id': study.id, 'title': study.title}
