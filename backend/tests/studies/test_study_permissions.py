from fastapi.testclient import TestClient

from app.application import create_application


def account(client: TestClient, email: str, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "correct-horse-battery-staple"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_notes_are_private_and_owner_scoped(test_settings):
    with TestClient(create_application(test_settings)) as client:
        owner = account(client, "owner@example.com", "owner")
        stranger = account(client, "stranger@example.com", "stranger")
        created = client.post(
            "/api/v1/notes",
            headers=owner,
            json={"passage_reference": "John 3:16", "content": "Grace is given, not earned."},
        )
        assert created.status_code == 201
        note_id = created.json()["id"]
        assert client.get("/api/v1/notes", headers=owner).json()[0]["id"] == note_id
        assert client.get(f"/api/v1/notes/{note_id}", headers=stranger).status_code == 404
        assert client.put(f"/api/v1/notes/{note_id}", headers=stranger, json={"content": "changed"}).status_code == 404
        assert client.delete(f"/api/v1/notes/{note_id}", headers=stranger).status_code == 404
        assert client.get("/api/v1/notes").status_code == 401


def test_studies_and_messages_are_private(test_settings):
    with TestClient(create_application(test_settings)) as client:
        owner = account(client, "owner@example.com", "owner")
        stranger = account(client, "stranger@example.com", "stranger")
        created = client.post("/api/v1/studies", headers=owner, json={"title": "The Beatitudes"})
        assert created.status_code == 201
        study_id = created.json()["id"]
        message = client.post(
            f"/api/v1/studies/{study_id}/messages",
            headers=owner,
            json={"role": "user", "content": "What does blessed mean here?"},
        )
        assert message.status_code == 201
        assert client.get(f"/api/v1/studies/{study_id}", headers=owner).json()["messages"][0]["content"].startswith("What")
        assert client.get(f"/api/v1/studies/{study_id}", headers=stranger).status_code == 404
        assert client.delete(f"/api/v1/studies/{study_id}", headers=stranger).status_code == 404
