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


class AdministratorAssignmentError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


def _fail(code: str, message: str) -> NoReturn:
    typer.echo(json.dumps({
        'changed': False,
        'error_code': code,
        'message': message,
    }, sort_keys=True), err=True)
    raise typer.Exit(code=1)


def locked_user_query(target_user_id: UUID, operator_user_id: UUID):
    return (
        select(User)
        .where(or_(
            User.id.in_((target_user_id, operator_user_id)),
            User.role == 'administrator',
        ))
        .order_by(User.id)
        .with_for_update()
    )


def _assign(session: Session, target_id: UUID, operator_id: UUID):
    dialect = session.get_bind().dialect.name
    if dialect == 'postgresql':
        session.execute(text('SELECT pg_advisory_xact_lock(731150015)'))
    users = session.scalars(locked_user_query(target_id, operator_id)).all()
    target = next((user for user in users if user.id == target_id), None)
    operator = next((user for user in users if user.id == operator_id), None)
    administrators = [user for user in users if user.role == 'administrator']
    if operator is None:
        raise AdministratorAssignmentError(
            'operator_missing', 'Operator user was not found'
        )
    if not operator.is_active:
        raise AdministratorAssignmentError(
            'operator_inactive', 'Operator user is inactive'
        )
    if target is None:
        raise AdministratorAssignmentError(
            'target_not_found', 'Target user was not found'
        )
    if not target.is_active:
        raise AdministratorAssignmentError(
            'target_inactive', 'Target user is inactive'
        )
    if len(administrators) == 1 and administrators[0].id == target.id:
        return None
    if administrators:
        raise AdministratorAssignmentError(
            'bootstrap_already_completed',
            'Initial administrator has already been assigned',
        )
    if target.role != 'reader':
        raise AdministratorAssignmentError(
            'target_not_reader', 'Target user must have the reader role'
        )
    audit_identity = {
        'operation': 'deployment_bootstrap',
        'operator_user_id': str(operator.id),
        'target_user_id': str(target.id),
    }
    prior = {**audit_identity, 'role': 'reader'}
    resulting = {
        **audit_identity,
        'role': 'administrator',
    }
    target.role = 'administrator'
    session.flush()
    return append_source_audit_event(
        session,
        actor_id=operator.id,
        action='initial_administrator_assigned',
        prior_state=prior,
        resulting_state=resulting,
    )


@app.command('assign-initial-administrator')
def assign_initial_administrator(
    database_url: Annotated[str, typer.Option('--database-url')],
    user_id: Annotated[str, typer.Option('--user-id')],
    operator_user_id: Annotated[str, typer.Option('--operator-user-id')],
    confirmation: Annotated[str, typer.Option('--confirmation')],
) -> None:
    if not database_url or not database_url.strip():
        _fail('missing_database_url', 'An explicit nonblank database URL is required')
    if confirmation != 'GRANT-ADMINISTRATOR':
        _fail(
            'invalid_confirmation',
            'Confirmation must exactly equal GRANT-ADMINISTRATOR',
        )
    try:
        target_id = UUID(user_id)
    except (ValueError, TypeError, AttributeError):
        _fail('invalid_user_id', 'User ID must be a valid UUID')
    try:
        operator_id = UUID(operator_user_id)
    except (ValueError, TypeError, AttributeError):
        _fail('invalid_operator_user_id', 'Operator user ID must be a valid UUID')
    engine = None
    committed = False
    failure: tuple[str, str] | None = None
    payload: dict[str, object] | None = None
    try:
        engine = create_database_engine(Settings(
            environment='development', database_url=database_url.strip()
        ))
        if engine.dialect.name not in {'sqlite', 'postgresql'}:
            raise AdministratorAssignmentError(
                'unsupported_database',
                'Administrator bootstrap requires SQLite or PostgreSQL',
            )
        factory = create_session_factory(engine)
        with factory() as session:
            if engine.dialect.name == 'sqlite':
                session.connection().exec_driver_sql('BEGIN IMMEDIATE')
                event = _assign(session, target_id, operator_id)
                session.commit()
            else:
                with session.begin():
                    event = _assign(session, target_id, operator_id)
            committed = True
        payload = {
            'target_user_id': str(target_id),
            'operator_user_id': str(operator_id),
            'changed': event is not None,
            'audit_event_id': str(event.id) if event is not None else None,
            'next_action': 'administrator_ready',
        }
    except AdministratorAssignmentError as error:
        failure = (error.code, error.safe_message)
    except Exception:
        failure = ('operator_failure', 'Administrator assignment failed safely')
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                if committed and payload is not None:
                    payload['warning_code'] = 'engine_cleanup_failed'
                elif failure is None:
                    failure = (
                        'operator_failure',
                        'Administrator assignment failed safely',
                    )
    if failure is not None:
        _fail(*failure)
    typer.echo(json.dumps(payload, sort_keys=True))


if __name__ == '__main__':
    app()
