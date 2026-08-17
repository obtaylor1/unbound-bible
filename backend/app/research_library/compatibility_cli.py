"""Explicit operator command for metadata-only legacy source registration."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Annotated, NoReturn
from uuid import UUID

import typer
from sqlalchemy.engine import make_url

from app.config import Settings
from app.database import create_database_engine, create_session_factory
from app.research_library.compatibility import (
    LegacyRegistrationError,
    register_legacy_sources,
)


app = typer.Typer(no_args_is_help=True)


@app.callback()
def _root() -> None:
    """Register legacy source metadata for explicit rights review."""


def _fail(code: str, message: str) -> NoReturn:
    typer.echo(json.dumps({
        'changed': False,
        'error_code': code,
        'message': message,
    }, sort_keys=True), err=True)
    raise typer.Exit(code=1)


@app.command('register')
def register(
    database_url: Annotated[str, typer.Option('--database-url')],
    actor_id: Annotated[str, typer.Option('--actor-id')],
) -> None:
    if not database_url or not database_url.strip():
        _fail('missing_database_url', 'An explicit nonblank database URL is required')
    try:
        parsed_actor_id = UUID(actor_id)
    except (ValueError, TypeError, AttributeError):
        _fail('invalid_actor_id', 'Actor ID must be a valid UUID')
    try:
        requested_dialect = make_url(database_url.strip()).get_backend_name()
    except Exception:
        _fail('invalid_database_url', 'Database URL is invalid')
    if requested_dialect not in {'sqlite', 'postgresql'}:
        _fail(
            'unsupported_database',
            'Legacy source registration requires SQLite or PostgreSQL',
        )

    engine = None
    committed = False
    failure: tuple[str, str] | None = None
    payload: dict[str, object] | None = None
    try:
        engine = create_database_engine(Settings(
            environment='development', database_url=database_url.strip()
        ))
        if engine.dialect.name not in {'sqlite', 'postgresql'}:
            raise LegacyRegistrationError(
                'unsupported_database',
                'Legacy source registration requires SQLite or PostgreSQL',
            )
        factory = create_session_factory(engine)
        with factory() as session:
            if engine.dialect.name == 'sqlite':
                session.connection().exec_driver_sql('BEGIN IMMEDIATE')
                result = register_legacy_sources(session, parsed_actor_id)
                session.commit()
            else:
                with session.begin():
                    result = register_legacy_sources(session, parsed_actor_id)
            committed = True
        result_counts = asdict(result)
        payload = {
            **result_counts,
            'changed': any(
                value
                for field, value in result_counts.items()
                if field.startswith('created_')
            ),
            'next_action': 'review_source_rights',
        }
    except LegacyRegistrationError as error:
        failure = (error.code, error.safe_message)
    except Exception:
        failure = (
            'registration_failure',
            'Legacy source registration failed safely',
        )
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                if committed and payload is not None:
                    payload['warning_code'] = 'engine_cleanup_failed'
                elif failure is None:
                    failure = (
                        'registration_failure',
                        'Legacy source registration failed safely',
                    )
    if failure is not None:
        _fail(*failure)
    typer.echo(json.dumps(payload, sort_keys=True))


if __name__ == '__main__':
    app()
