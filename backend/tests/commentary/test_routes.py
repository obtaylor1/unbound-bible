from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.application import create_application
from app.auth.dependencies import require_admin
from app.auth.models import User


def _register(client: TestClient, *, email: str, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 201
    return response.json()


def _mount_probe(application) -> None:
    router = APIRouter()

    @router.get("/admin-probe")
    def admin_probe(user: User = Depends(require_admin)) -> dict[str, bool]:
        return {"allowed": True}

    application.include_router(router)


def test_admin_probe_rejects_registered_member(test_settings):
    application = create_application(test_settings)
    _mount_probe(application)
    with TestClient(application) as client:
        tokens = _register(client, email="member@example.com", username="member")
        response = client.get(
            "/admin-probe", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Administrator access required"}


def test_admin_probe_allows_registered_administrator(test_settings):
    application = create_application(test_settings)
    _mount_probe(application)
    with TestClient(application) as client:
        tokens = _register(client, email="admin@example.com", username="admin")
        with application.state.session_factory() as session:
            user = session.query(User).filter_by(email="admin@example.com").one()
            user.role = "admin"
            session.commit()

        response = client.get(
            "/admin-probe", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

    assert response.status_code == 200
    assert response.json() == {"allowed": True}
