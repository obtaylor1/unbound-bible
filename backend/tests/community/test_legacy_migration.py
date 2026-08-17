from sqlalchemy import create_engine, text, select
from app.application import create_application
from app.auth.models import User
from app.auth.security import hash_password, verify_password
from app.community.migration import canonical_legacy_role, import_legacy_forum
from app.community.models import CommunityComment, CommunityPost


def test_legacy_roles_are_mapped_without_email_inference():
    assert {
        role: canonical_legacy_role(role)
        for role in ('member', 'user', 'reader', 'moderator', 'unknown', None)
    } == {
        'member': 'reader', 'user': 'reader', 'reader': 'reader',
        'moderator': 'reader', 'unknown': 'reader', None: 'reader',
    }
    assert canonical_legacy_role('admin') == 'administrator'
    assert canonical_legacy_role('Role.ADMINISTRATOR') == 'administrator'


def test_legacy_forum_import_is_idempotent_and_preserves_ownership(test_settings, tmp_path):
    source_url = f"sqlite:///{tmp_path / 'legacy.db'}"; source = create_engine(source_url)
    with source.begin() as connection:
        connection.execute(text('CREATE TABLE auth_users (id INTEGER PRIMARY KEY, email TEXT, username TEXT, hashed_password TEXT, role TEXT, is_active BOOLEAN, created_at DATETIME)'))
        connection.execute(text('CREATE TABLE forum_posts (id INTEGER PRIMARY KEY, title TEXT, content TEXT, author_id INTEGER, created_at DATETIME, updated_at DATETIME)'))
        connection.execute(text('CREATE TABLE forum_comments (id INTEGER PRIMARY KEY, content TEXT, post_id INTEGER, author_id INTEGER, created_at DATETIME, updated_at DATETIME)'))
        connection.execute(text("INSERT INTO auth_users VALUES (7,'legacy@example.com','legacy',:password,'member',1,CURRENT_TIMESTAMP)"), {'password': hash_password('legacy-password')})
        connection.execute(text("INSERT INTO forum_posts VALUES (11,'Legacy post','Preserved content',7,CURRENT_TIMESTAMP,NULL)"))
        connection.execute(text("INSERT INTO forum_comments VALUES (13,'Preserved reply',11,7,CURRENT_TIMESTAMP,NULL)"))
    app = create_application(test_settings)
    with app.state.session_factory() as session:
        first = import_legacy_forum(source_url, session); second = import_legacy_forum(source_url, session)
        user = session.scalar(select(User).where(User.legacy_forum_user_id == 7))
        post = session.scalar(select(CommunityPost).where(CommunityPost.legacy_id == 11))
        comment = session.scalar(select(CommunityComment).where(CommunityComment.legacy_id == 13))
        assert first['users_imported'] == first['posts_imported'] == first['comments_imported'] == 1
        assert second['posts_imported'] == second['comments_imported'] == 0
        assert post.author_id == user.id and comment.author_id == user.id
        assert user.role == 'reader'
        assert verify_password('legacy-password', user.password_hash)
