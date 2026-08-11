from pathlib import Path

import run_e2e_server


def test_isolated_database_ignores_external_database_url_and_cleans_up(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/must-not-be-used.db")

    with run_e2e_server.isolated_database() as database_path:
        assert database_path.parent.name.startswith("unbound-bible-e2e-")
        assert database_path.name == "playwright.db"
        assert run_e2e_server.os.environ["DATABASE_URL"] == f"sqlite:///{database_path}"
        database_path.touch()

    assert not database_path.parent.exists()


def test_isolated_database_fails_closed_outside_test_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")

    try:
        with run_e2e_server.isolated_database():
            raise AssertionError("context should not start")
    except RuntimeError as error:
        assert str(error) == "Playwright backend requires ENVIRONMENT=test"
