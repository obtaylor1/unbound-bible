import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app.auth.dependencies import require_admin, require_administrator
from app.auth.models import ROLES, User
from app.database import Base, create_session_factory
from app.library import models as library_models  # noqa: F401
from app.research_library.admin_cli import app
from app.research_library.audit import append_source_audit_event
from app.research_library.models import SourceAuditEvent


runner = CliRunner()


def _user(*, role='reader', active=True) -> User:
    suffix = uuid4().hex
    return User(
        email=f'{suffix}@example.test', email_normalized=f'{suffix}@example.test',
        username=suffix, password_hash='unused', role=role, is_active=active,
    )


@pytest.fixture
def admin_database(tmp_path):
    url = f"sqlite:///{tmp_path / 'admin.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        yield url, factory
    finally:
        engine.dispose()


def _invoke(url: str, user_id, confirmation='GRANT-ADMINISTRATOR'):
    return runner.invoke(app, [
        'assign-initial-administrator', '--database-url', url,
        '--user-id', str(user_id), '--confirmation', confirmation,
    ])


def test_role_vocabulary_and_model_default_are_explicit():
    assert ROLES == frozenset({'reader', 'administrator'})
    assert User.role.property.columns[0].default.arg == 'reader'
    assert str(User.role.property.columns[0].server_default.arg) == 'reader'
    constraints = {constraint.name: str(constraint.sqltext) for constraint in User.__table__.constraints if constraint.name}
    assert "role IN ('reader', 'administrator')" in constraints['ck_users_role']


def test_administrator_dependency_and_compatibility_alias():
    administrator = _user(role='administrator')
    assert require_administrator(administrator) is administrator
    assert require_admin is require_administrator
    with pytest.raises(HTTPException) as error:
        require_administrator(_user(role='reader'))
    assert (error.value.status_code, error.value.detail) == (403, 'Administrator access required')


def test_append_audit_event_validates_action_and_copies_json(admin_database):
    _, factory = admin_database
    with factory() as session:
        actor = _user(); session.add(actor); session.flush()
        prior = {'role': {'from': 'reader'}}
        resulting = {'role': {'to': 'administrator'}}
        checksum = {'sha256': ['abc']}
        event = append_source_audit_event(
            session, actor_id=actor.id, action='assigned', prior_state=prior,
            resulting_state=resulting, checksum_metadata=checksum,
        )
        prior['role']['from'] = 'mutated'
        resulting['role']['to'] = 'mutated'
        checksum['sha256'].append('mutated')
        assert event.prior_state == {'role': {'from': 'reader'}}
        assert event.resulting_state == {'role': {'to': 'administrator'}}
        assert event.checksum_metadata == {'sha256': ['abc']}
        with pytest.raises(ValueError, match='action must be nonblank'):
            append_source_audit_event(
                session, actor_id=actor.id, action='  ', prior_state=None,
                resulting_state={},
            )


def test_cli_requires_explicit_database_and_exact_confirmation(admin_database):
    url, factory = admin_database
    with factory.begin() as session:
        target = _user(); session.add(target); session.flush(); target_id = target.id
    missing = runner.invoke(app, [
        'assign-initial-administrator', '--database-url', ' ',
        '--user-id', str(target_id), '--confirmation', 'GRANT-ADMINISTRATOR',
    ])
    wrong = _invoke(url, target_id, 'grant-administrator')
    assert missing.exit_code != 0 and 'database' in missing.stderr.lower()
    assert wrong.exit_code != 0 and 'confirmation' in wrong.stderr.lower()
    with factory() as session:
        assert session.get(User, target_id).role == 'reader'
        assert session.scalar(select(SourceAuditEvent)) is None


@pytest.mark.parametrize('kind', ['missing', 'inactive', 'invalid-role'])
def test_cli_rejects_ineligible_targets(admin_database, kind):
    url, factory = admin_database
    target_id = uuid4()
    if kind == 'invalid-role':
        target = _user(role='reader')
        with factory.begin() as session:
            session.add(target); session.flush(); target_id = target.id
        engine = factory.kw['bind']
        with engine.begin() as connection:
            connection.exec_driver_sql('PRAGMA ignore_check_constraints=ON')
            connection.execute(User.__table__.update().where(User.id == target_id).values(role='legacy'))
            connection.exec_driver_sql('PRAGMA ignore_check_constraints=OFF')
    elif kind != 'missing':
        with factory.begin() as session:
            target = _user(active=kind != 'inactive')
            session.add(target); session.flush(); target_id = target.id
    result = _invoke(url, target_id)
    assert result.exit_code != 0
    assert kind.split('-')[0] in result.stderr.lower()
    with factory() as session:
        assert session.scalar(select(SourceAuditEvent)) is None


def test_cli_changes_exactly_one_role_and_writes_sanitized_audit(admin_database):
    url, factory = admin_database
    with factory.begin() as session:
        target = _user(); other = _user(); session.add_all([target, other]); session.flush()
        target_id, other_id = target.id, other.id
    result = _invoke(url, target_id)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload['target_user_id'] == str(target_id)
    assert payload['changed'] is True and UUID(payload['audit_event_id'])
    assert 'email' not in result.stdout.lower()
    with factory() as session:
        assert session.get(User, target_id).role == 'administrator'
        assert session.get(User, other_id).role == 'reader'
        events = session.scalars(select(SourceAuditEvent)).all()
        assert len(events) == 1
        event = events[0]
        assert event.actor_id == target_id
        assert event.action == 'initial_administrator_assigned'
        assert event.prior_state == {'target_user_id': str(target_id), 'role': 'reader'}
        assert event.resulting_state == {
            'target_user_id': str(target_id), 'role': 'administrator',
            'bootstrap_actor': 'target_account',
        }


def test_cli_is_idempotent_for_sole_administrator_and_refuses_another(admin_database):
    url, factory = admin_database
    with factory.begin() as session:
        first = _user(); second = _user(); session.add_all([first, second]); session.flush()
        first_id, second_id = first.id, second.id
    assert _invoke(url, first_id).exit_code == 0
    rerun = _invoke(url, first_id)
    refusal = _invoke(url, second_id)
    assert rerun.exit_code == 0 and json.loads(rerun.stdout)['changed'] is False
    assert refusal.exit_code != 0 and 'one-time' in refusal.stderr.lower()
    with factory() as session:
        assert len(session.scalars(select(SourceAuditEvent)).all()) == 1
        assert session.get(User, second_id).role == 'reader'


def test_cli_rolls_back_role_when_audit_flush_fails(admin_database, monkeypatch):
    url, factory = admin_database
    with factory.begin() as session:
        target = _user(); session.add(target); session.flush(); target_id = target.id
    def fail(*args, **kwargs):
        raise RuntimeError('audit unavailable')
    monkeypatch.setattr('app.research_library.admin_cli.append_source_audit_event', fail)
    result = _invoke(url, target_id)
    assert result.exit_code != 0 and 'audit unavailable' in result.stderr
    with factory() as session:
        assert session.get(User, target_id).role == 'reader'


def test_sqlite_bootstrap_serializes_concurrent_attempts(admin_database):
    from app.research_library.admin_cli import _assign

    _, factory = admin_database
    with factory.begin() as session:
        first = _user(); second = _user(); session.add_all([first, second]); session.flush()
        target_ids = (first.id, second.id)

    def attempt(target_id):
        try:
            with factory() as session:
                session.connection().exec_driver_sql('BEGIN IMMEDIATE')
                event = _assign(session, target_id)
                session.commit()
                return event is not None
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, target_ids))
    assert sorted(results) == [False, True]
    with factory() as session:
        assert session.scalar(select(User).where(User.role == 'administrator')) is not None
        assert len(session.scalars(select(SourceAuditEvent)).all()) == 1


def test_assignment_lock_compiles_for_postgresql():
    from app.research_library.admin_cli import locked_user_query
    sql = str(locked_user_query(uuid4()).compile(dialect=__import__('sqlalchemy').dialects.postgresql.dialect()))
    assert 'FOR UPDATE' in sql


def test_cli_source_has_no_email_targeting():
    import inspect
    from app.research_library import admin_cli
    source = inspect.getsource(admin_cli)
    assert '--email' not in source
    assert 'User.email' not in source
