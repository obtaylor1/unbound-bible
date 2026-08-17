"""Idempotent importer for the retired standalone forum SQLite database."""
import argparse
import json
from datetime import datetime
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session
from app.auth.models import User
from app.community.models import CommunityComment, CommunityPost
from app.config import Settings
from app.database import create_database_engine, create_session_factory


def canonical_legacy_role(value) -> str:
    role = str(value or '').split('.')[-1].strip().casefold()
    return 'administrator' if role in {'admin', 'administrator'} else 'reader'


def as_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def import_legacy_forum(source_url: str, session: Session) -> dict:
    source = create_engine(source_url)
    report = {'users_imported': 0, 'users_existing': 0, 'posts_imported': 0, 'comments_imported': 0, 'unmapped_posts': [], 'unmapped_comments': []}
    if not inspect(source).has_table('auth_users'): return report
    with source.connect() as connection:
        users = list(connection.execute(text('SELECT id, email, username, hashed_password, role, is_active, created_at FROM auth_users ORDER BY id')).mappings())
        posts = list(connection.execute(text('SELECT id, title, content, author_id, created_at, updated_at FROM forum_posts ORDER BY id')).mappings()) if inspect(source).has_table('forum_posts') else []
        comments = list(connection.execute(text('SELECT id, content, post_id, author_id, created_at, updated_at FROM forum_comments ORDER BY id')).mappings()) if inspect(source).has_table('forum_comments') else []
    user_map = {}
    for row in users:
        user = session.scalar(select(User).where((User.legacy_forum_user_id == row['id']) | (User.email_normalized == row['email'].strip().casefold())))
        if user: report['users_existing'] += 1
        else:
            user = User(email=row['email'].strip(), email_normalized=row['email'].strip().casefold(), username=row['username'], password_hash=row['hashed_password'], role=canonical_legacy_role(row['role']), is_active=bool(row['is_active']), legacy_forum_user_id=row['id'])
            session.add(user); session.flush(); report['users_imported'] += 1
        if user.legacy_forum_user_id is None: user.legacy_forum_user_id = row['id']
        user_map[row['id']] = user.id
    post_map = {}
    for row in posts:
        existing = session.scalar(select(CommunityPost).where(CommunityPost.legacy_id == row['id']))
        if existing: post_map[row['id']] = existing.id; continue
        author_id = user_map.get(row['author_id'])
        if not author_id: report['unmapped_posts'].append(row['id']); continue
        item = CommunityPost(legacy_id=row['id'], title=row['title'], content=row['content'], author_id=author_id, created_at=as_datetime(row['created_at']), updated_at=as_datetime(row['updated_at'] or row['created_at']))
        session.add(item); session.flush(); post_map[row['id']] = item.id; report['posts_imported'] += 1
    for row in comments:
        if session.scalar(select(CommunityComment).where(CommunityComment.legacy_id == row['id'])): continue
        author_id, post_id = user_map.get(row['author_id']), post_map.get(row['post_id'])
        if not author_id or not post_id: report['unmapped_comments'].append(row['id']); continue
        session.add(CommunityComment(legacy_id=row['id'], content=row['content'], post_id=post_id, author_id=author_id, created_at=as_datetime(row['created_at']), updated_at=as_datetime(row['updated_at'] or row['created_at']))); report['comments_imported'] += 1
    session.commit(); source.dispose(); return report


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument('--source', required=True, help='Legacy SQLAlchemy database URL'); parser.add_argument('--report', default='community-migration-report.json'); args = parser.parse_args()
    settings = Settings(); engine = create_database_engine(settings)
    with create_session_factory(engine)() as session: report = import_legacy_forum(args.source, session)
    with open(args.report, 'w', encoding='utf-8') as output: json.dump(report, output, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
