import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.auth.dependencies import get_current_user, get_session
from app.auth.models import User
from app.community.models import CommunityComment, CommunityPost
from app.community.service import emit_comment_notifications, serialize_comment, serialize_post


router = APIRouter(prefix='/community', tags=['community'])
class PostPayload(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    content: str = Field(min_length=2, max_length=20_000)
class CommentPayload(BaseModel):
    content: str = Field(min_length=1, max_length=5_000)


def post_query(): return select(CommunityPost).options(selectinload(CommunityPost.author), selectinload(CommunityPost.comments))
def comment_query(): return select(CommunityComment).options(selectinload(CommunityComment.author), selectinload(CommunityComment.post).selectinload(CommunityPost.author))


@router.get('/posts')
def list_posts(skip: int = 0, limit: int = 20, session: Session = Depends(get_session)):
    limit = min(max(limit, 1), 100); return [serialize_post(item) for item in session.scalars(post_query().order_by(CommunityPost.created_at.desc()).offset(max(skip, 0)).limit(limit)).all()]


@router.post('/posts', status_code=201)
def create_post(payload: PostPayload, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = CommunityPost(title=payload.title, content=payload.content, author_id=user.id); session.add(item); session.commit()
    item = session.scalar(post_query().where(CommunityPost.id == item.id)); return serialize_post(item)


def find_post(post_id: uuid.UUID, session: Session) -> CommunityPost:
    item = session.scalar(post_query().where(CommunityPost.id == post_id))
    if not item: raise HTTPException(404, 'Post not found')
    return item


@router.get('/posts/{post_id}')
def get_post(post_id: uuid.UUID, session: Session = Depends(get_session)): return serialize_post(find_post(post_id, session))


def can_manage(owner_id, user): return owner_id == user.id or user.role == 'administrator'


@router.put('/posts/{post_id}')
def update_post(post_id: uuid.UUID, payload: PostPayload, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = find_post(post_id, session)
    if not can_manage(item.author_id, user): raise HTTPException(403, 'Not authorized to update this post')
    item.title, item.content = payload.title, payload.content; session.commit()
    return serialize_post(find_post(post_id, session))


@router.delete('/posts/{post_id}', status_code=204)
def delete_post(post_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = find_post(post_id, session)
    if not can_manage(item.author_id, user): raise HTTPException(403, 'Not authorized to delete this post')
    session.delete(item); session.commit(); return Response(status_code=204)


@router.get('/posts/{post_id}/comments')
def comments(post_id: uuid.UUID, session: Session = Depends(get_session)):
    find_post(post_id, session); return [serialize_comment(item) for item in session.scalars(comment_query().where(CommunityComment.post_id == post_id).order_by(CommunityComment.created_at)).all()]


@router.post('/posts/{post_id}/comments', status_code=201)
def create_comment(post_id: uuid.UUID, payload: CommentPayload, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    find_post(post_id, session); item = CommunityComment(post_id=post_id, author_id=user.id, content=payload.content); session.add(item); session.commit()
    item = session.scalar(comment_query().where(CommunityComment.id == item.id)); result = serialize_comment(item); emit_comment_notifications(session, item); return result


def find_comment(comment_id: uuid.UUID, session: Session) -> CommunityComment:
    item = session.scalar(comment_query().where(CommunityComment.id == comment_id))
    if not item: raise HTTPException(404, 'Comment not found')
    return item


@router.put('/comments/{comment_id}')
def update_comment(comment_id: uuid.UUID, payload: CommentPayload, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = find_comment(comment_id, session)
    if not can_manage(item.author_id, user): raise HTTPException(403, 'Not authorized to update this comment')
    item.content = payload.content; session.commit(); return serialize_comment(find_comment(comment_id, session))


@router.delete('/comments/{comment_id}', status_code=204)
def delete_comment(comment_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = find_comment(comment_id, session)
    if not can_manage(item.author_id, user): raise HTTPException(403, 'Not authorized to delete this comment')
    session.delete(item); session.commit(); return Response(status_code=204)
