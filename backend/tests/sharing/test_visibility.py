from fastapi.testclient import TestClient
from app.application import create_application


def account(client, email, username):
    data = client.post('/api/v1/auth/register', json={'email': email, 'username': username, 'password': 'correct-horse-battery-staple'}).json()
    return {'Authorization': f"Bearer {data['access_token']}"}


def create_study(client, headers):
    study = client.post('/api/v1/studies', headers=headers, json={'title': 'Grace study'}).json()
    client.post(f"/api/v1/studies/{study['id']}/messages", headers=headers, json={'role': 'user', 'content': 'What is grace?'})
    return study


def test_private_unlisted_public_visibility_and_revocation(test_settings):
    with TestClient(create_application(test_settings)) as client:
        owner, stranger = account(client, 'owner@example.com', 'owner'), account(client, 'other@example.com', 'other')
        study = create_study(client, owner)
        private = client.post('/api/v1/shares', headers=owner, json={'study_id': study['id'], 'visibility': 'private'}).json()
        assert client.get(f"/api/v1/shares/{private['share_id']}", headers=owner).status_code == 200
        assert client.get(f"/api/v1/shares/{private['share_id']}", headers=stranger).status_code == 404
        assert client.get(f"/api/v1/shares/{private['share_id']}").status_code == 404

        changed = client.patch(f"/api/v1/shares/{private['share_id']}", headers=owner, json={'visibility': 'unlisted'})
        assert changed.status_code == 200
        assert client.get(f"/api/v1/shares/{private['share_id']}").status_code == 200
        assert client.get('/api/v1/shares/public').json() == []

        client.patch(f"/api/v1/shares/{private['share_id']}", headers=owner, json={'visibility': 'public'})
        assert len(client.get('/api/v1/shares/public').json()) == 1
        assert client.post(f"/api/v1/shares/{private['share_id']}/revoke", headers=owner).status_code == 200
        assert client.get(f"/api/v1/shares/{private['share_id']}").status_code == 410


def test_snapshot_is_immutable_and_can_be_duplicated(test_settings):
    with TestClient(create_application(test_settings)) as client:
        owner, reader = account(client, 'owner@example.com', 'owner'), account(client, 'reader@example.com', 'reader')
        study = create_study(client, owner)
        share = client.post('/api/v1/shares', headers=owner, json={'study_id': study['id'], 'visibility': 'unlisted'}).json()
        client.post(f"/api/v1/studies/{study['id']}/messages", headers=owner, json={'role': 'user', 'content': 'Later private message'})
        snapshot = client.get(f"/api/v1/shares/{share['share_id']}").json()
        assert len(snapshot['messages']) == 1
        duplicate = client.post(f"/api/v1/shares/{share['share_id']}/duplicate", headers=reader)
        assert duplicate.status_code == 201
        assert duplicate.json()['title'] == 'Grace study'
        assert client.delete(f"/api/v1/shares/{share['share_id']}", headers=owner).status_code == 204
