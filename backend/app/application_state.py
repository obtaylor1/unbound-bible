"""Shared runtime state wiring for modular and legacy FastAPI launchers."""

from fastapi import FastAPI
from sqlalchemy import Engine

from app.config import Settings
from app.database import create_session_factory, ensure_sqlite_foreign_keys
from app.security.rate_limits import InMemoryRateLimiter


def wire_application_state(
    application: FastAPI,
    settings: Settings,
    database_engine: Engine,
) -> None:
    """Attach modular dependencies to an app using its existing database engine."""
    ensure_sqlite_foreign_keys(database_engine)
    application.state.settings = settings
    application.state.database_engine = database_engine
    application.state.session_factory = create_session_factory(database_engine)
    if not hasattr(application.state, 'rate_limiter'):
        application.state.rate_limiter = InMemoryRateLimiter()
