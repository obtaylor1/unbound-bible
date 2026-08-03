from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_unified_identity_migration_upgrades_empty_database(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', '   ')
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    inspector = inspect(create_engine(database_url))
    assert {"users", "auth_sessions", "revoked_tokens"} <= set(inspector.get_table_names())

    user_indexes = {index["name"] for index in inspector.get_indexes("users")}
    session_indexes = {index["name"] for index in inspector.get_indexes("auth_sessions")}
    revoked_indexes = {index["name"] for index in inspector.get_indexes("revoked_tokens")}
    assert "ux_users_email_normalized" in user_indexes
    assert "ux_auth_sessions_refresh_token_hash" in session_indexes
    assert "ux_revoked_tokens_jti" in revoked_indexes


def test_unified_identity_migration_is_reversible(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    tables = set(inspect(create_engine(database_url)).get_table_names())
    assert not ({"users", "auth_sessions", "revoked_tokens"} & tables)


def test_alembic_database_url_environment_overrides_configured_fallback(tmp_path, monkeypatch):
    intended_path = tmp_path / 'environment%catalog.db'
    fallback_path = tmp_path / 'configured-fallback.db'
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / 'alembic.ini'))
    config.set_main_option('script_location', str(backend_root / 'alembic'))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{fallback_path}')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{intended_path}')

    command.upgrade(config, 'head')

    assert intended_path.exists()
    migrated_tables = set(inspect(create_engine(f'sqlite:///{intended_path}')).get_table_names())
    assert {
        'users',
        'auth_sessions',
        'library_works',
        'canon_entries',
        'edition_coverage',
    } <= migrated_tables
    assert not fallback_path.exists()
