"""Local-only, explicit operator bootstrap for the first administrator."""

from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID
import json

import typer
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.auth.models import User
from app.config import Settings
from app.database import create_database_engine, create_session_factory
from app.research_library.audit import append_source_audit_event


app = typer.Typer(no_args_is_help=True)


@app.callback()
def _root() -> None:
    """Protected research-library operator commands."""


def _fail(message: str) -> NoReturn:
    typer.echo(json.dumps({'error': message, 'changed': False}), err=True)
    raise typer.Exit(code=1)


def locked_user_query(user_id: UUID):
    return (
        select(User)
        .where(or_(User.id == user_id, User.role == 'administrator'))
        .order_by(User.id)
        .with_for_update()
    )


def _assign(session: Session, target_id: UUID):
    dialect = session.get_bind().dialect.name
    if dialect == 'postgresql':
        session.execute(text('SELECT pg_advisory_xact_lock(731150015)'))
    users = session.scalars(locked_user_query(target_id)).all()
    target = next((user for user in users if user.id == target_id), None)
    administrators = [user for user in users if user.role == 'administrator']
    if target is None:
        raise ValueError('missing target user')
    if not target.is_active:
        raise ValueError('inactive target user')
    if len(administrators) == 1 and administrators[0].id == target.id:
        return None
    if administrators:
        raise ValueError('one-time bootstrap refused: another administrator exists')
    if target.role != 'reader':
        raise ValueError(f'invalid target role: {target.role}')
    prior = {'target_user_id': str(target.id), 'role': 'reader'}
    resulting = {
        'target_user_id': str(target.id),
        'role': 'administrator',
        'bootstrap_actor': 'target_account',
    }
    target.role = 'administrator'
    session.flush()
    return append_source_audit_event(
        session,
        actor_id=target.id,
        action='initial_administrator_assigned',
        prior_state=prior,
        resulting_state=resulting,
    )


@app.command('assign-initial-administrator')
def assign_initial_administrator(
    database_url: Annotated[str, typer.Option('--database-url')],
    user_id: Annotated[UUID, typer.Option('--user-id')],
    confirmation: Annotated[str, typer.Option('--confirmation')],
) -> None:
    if not database_url or not database_url.strip():
        _fail('An explicit nonblank database URL is required')
    if confirmation != 'GRANT-ADMINISTRATOR':
        _fail('confirmation must exactly equal GRANT-ADMINISTRATOR')
    engine = None
    try:
        engine = create_database_engine(Settings(
            environment='development', database_url=database_url.strip()
        ))
        factory = create_session_factory(engine)
        with factory() as session:
            if engine.dialect.name == 'sqlite':
                session.connection().exec_driver_sql('BEGIN IMMEDIATE')
                event = _assign(session, user_id)
                session.commit()
            else:
                with session.begin():
                    event = _assign(session, user_id)
        typer.echo(json.dumps({
            'target_user_id': str(user_id),
            'changed': event is not None,
            'audit_event_id': str(event.id) if event is not None else None,
            'next_action': 'administrator_ready',
        }, sort_keys=True))
    except typer.Exit:
        raise
    except Exception as error:
        _fail(str(error))
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    app()
