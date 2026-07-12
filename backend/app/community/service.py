import re
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth.models import User
from app.community.models import CommunityComment, CommunityPost
from app.notifications.service import create_notification


def public_user(user: User) -> dict:
    return {'id': user.id, 'username': user.username, 'role': user.role}


def serialize_post(post: CommunityPost) -> dict:
    return {'id': post.id, 'title': post.title, 'content': post.content, 'author': public_user(post.author), 'created_at': post.created_at, 'updated_at': post.updated_at, 'comments_count': len(post.comments)}


def serialize_comment(comment: CommunityComment) -> dict:
    return {'id': comment.id, 'content': comment.content, 'post_id': comment.post_id, 'author': public_user(comment.author), 'created_at': comment.created_at, 'updated_at': comment.updated_at}


def emit_comment_notifications(session: Session, comment: CommunityComment) -> None:
    post = comment.post
    if post.author_id != comment.author_id:
        create_notification(session, recipient_id=post.author_id, actor_id=comment.author_id, event_type='reply', target_type='community_post', target_id=str(post.id), message=f'{comment.author.username} replied to your discussion.', deduplication_key=f'reply:{comment.id}')
    usernames = set(re.findall(r'(?<!\w)@([A-Za-z0-9_-]{3,50})', comment.content))
    for username in usernames:
        mentioned = session.scalar(select(User).where(User.username == username))
        if mentioned and mentioned.id != comment.author_id:
            create_notification(session, recipient_id=mentioned.id, actor_id=comment.author_id, event_type='mention', target_type='community_comment', target_id=str(comment.id), message=f'{comment.author.username} mentioned you in a discussion.', deduplication_key=f'mention:{comment.id}:{mentioned.id}')
