from fastapi.testclient import TestClient

from app.application import create_application


def register(client: TestClient, *, email="reader@example.com", username="reader"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "correct-horse-battery-staple"},
    )


def test_registration_login_and_me(test_settings):
    with TestClient(create_application(test_settings)) as client:
        response = register(client)
        assert response.status_code == 201
        tokens = response.json()
        assert tokens["access_token"] and tokens["refresh_token"]

        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        assert me.status_code == 200
        assert me.json()["email"] == "reader@example.com"
        assert "password_hash" not in me.json()

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "READER@example.com", "password": "correct-horse-battery-staple"},
        )
        assert login.status_code == 200


def test_duplicate_email_and_invalid_password_are_rejected(test_settings):
    with TestClient(create_application(test_settings)) as client:
        assert register(client).status_code == 201
        assert register(client, username="reader-two").status_code == 409
        invalid = client.post(
            "/api/v1/auth/login",
            json={"email": "reader@example.com", "password": "incorrect-password"},
        )
        assert invalid.status_code == 401


def test_refresh_rotates_and_logout_revokes_refresh_token(test_settings):
    with TestClient(create_application(test_settings)) as client:
        original = register(client).json()
        rotated_response = client.post("/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]})
        assert rotated_response.status_code == 200
        rotated = rotated_response.json()
        assert rotated["refresh_token"] != original["refresh_token"]
        assert client.post("/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}).status_code == 401

        assert client.post("/api/v1/auth/logout", json={"refresh_token": rotated["refresh_token"]}).status_code == 204
        assert client.post("/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]}).status_code == 401


def test_profile_update_and_anonymous_access(test_settings):
    with TestClient(create_application(test_settings)) as client:
        assert client.get("/api/v1/auth/me").status_code == 401
        tokens = register(client).json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        response = client.put("/api/v1/auth/profile", headers=headers, json={"username": "studious-reader"})
        assert response.status_code == 200
        assert response.json()["username"] == "studious-reader"
