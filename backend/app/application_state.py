"""Shared runtime state wiring for modular and legacy FastAPI launchers."""

import httpx
from fastapi import FastAPI
from sqlalchemy import Engine

from app.config import Settings
from app.database import create_session_factory, ensure_sqlite_foreign_keys
from app.security.rate_limits import InMemoryRateLimiter


def _create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30)


def _requires_http_client(settings: Settings) -> bool:
    return any(
        provider != 'demo'
        for provider in (
            settings.ai_chat_provider,
            settings.ai_embedding_provider,
            settings.ai_transcription_provider,
        )
    )


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
    application.state.http_client = None
    if not hasattr(application.state, 'rate_limiter'):
        application.state.rate_limiter = InMemoryRateLimiter()

    async def start_http_client() -> None:
        if (
            application.state.http_client is None
            and _requires_http_client(settings)
        ):
            application.state.http_client = _create_http_client()

    async def close_http_client() -> None:
        client = application.state.http_client
        if client is not None:
            application.state.http_client = None
            await client.aclose()

    application.router.add_event_handler('startup', start_http_client)
    application.router.add_event_handler('shutdown', close_http_client)
