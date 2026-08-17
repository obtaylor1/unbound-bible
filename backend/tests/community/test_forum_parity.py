from fastapi.testclient import TestClient
from app.application import create_application
from app.auth.models import User
import uuid


def account(client, email, username):
    data = client.post('/api/v1/auth/register', json={'email': email, 'username': username, 'password': 'correct-horse-battery-staple'}).json()
    return {'Authorization': f"Bearer {data['access_token']}"}, client.get('/api/v1/auth/me', headers={'Authorization': f"Bearer {data['access_token']}"}).json()['id']


def test_post_comment_crud_permissions_and_public_privacy(test_settings):
    app = create_application(test_settings)
    with TestClient(app) as client:
        owner, _ = account(client, 'owner@example.com', 'owner'); other, _ = account(client, 'other@example.com', 'other')
        created = client.post('/api/v1/community/posts', headers=owner, json={'title': 'Historical context', 'content': 'A careful question'}); assert created.status_code == 201
        post = created.json(); assert 'email' not in post['author']
        assert client.get('/api/v1/community/posts').json()[0]['id'] == post['id']
        assert client.put(f"/api/v1/community/posts/{post['id']}", headers=other, json={'title': 'Hijacked', 'content': 'No'}).status_code == 403
        updated = client.put(f"/api/v1/community/posts/{post['id']}", headers=owner, json={'title': 'Updated context', 'content': 'More evidence'}); assert updated.status_code == 200
        comment = client.post(f"/api/v1/community/posts/{post['id']}/comments", headers=other, json={'content': '@owner Helpful reply'}); assert comment.status_code == 201
        assert 'email' not in comment.json()['author']
        assert client.put(f"/api/v1/community/comments/{comment.json()['id']}", headers=owner, json={'content': 'No'}).status_code == 403
        assert client.delete(f"/api/v1/community/comments/{comment.json()['id']}", headers=other).status_code == 204
        assert client.delete(f"/api/v1/community/posts/{post['id']}", headers=owner).status_code == 204


def test_administrator_can_manage_others_content(test_settings):
    app = create_application(test_settings)
    with TestClient(app) as client:
        author, _ = account(client, 'author@example.com', 'author'); moderator, moderator_id = account(client, 'mod@example.com', 'moderator')
        with app.state.session_factory() as session:
            user = session.get(User, uuid.UUID(moderator_id)); user.role = 'administrator'; session.commit()
        post = client.post('/api/v1/community/posts', headers=author, json={'title': 'Post', 'content': 'Content'}).json()
        assert client.delete(f"/api/v1/community/posts/{post['id']}", headers=moderator).status_code == 204
