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


def _invoke(
    url: str, user_id, confirmation='GRANT-ADMINISTRATOR', *, operator_user_id=None
):
    operator_user_id = user_id if operator_user_id is None else operator_user_id
    return runner.invoke(app, [
        'assign-initial-administrator', '--database-url', url,
        '--user-id', str(user_id), '--operator-user-id', str(operator_user_id),
        '--confirmation', confirmation,
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
        '--user-id', str(target_id), '--operator-user-id', str(target_id),
        '--confirmation', 'GRANT-ADMINISTRATOR',
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
    with factory.begin() as session:
        operator = _user(); session.add(operator); session.flush(); operator_id = operator.id
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
    result = _invoke(url, target_id, operator_user_id=operator_id)
    assert result.exit_code != 0
    expected_codes = {
        'missing': 'target_not_found',
        'inactive': 'target_inactive',
        'invalid-role': 'target_not_reader',
    }
    assert json.loads(result.stderr)['error_code'] == expected_codes[kind]
    with factory() as session:
        assert session.scalar(select(SourceAuditEvent)) is None


def test_cli_changes_exactly_one_role_and_writes_sanitized_audit(admin_database):
    url, factory = admin_database
    with factory.begin() as session:
        target = _user(); operator = _user(); other = _user()
        session.add_all([target, operator, other]); session.flush()
        target_id, operator_id, other_id = target.id, operator.id, other.id
    result = _invoke(url, target_id, operator_user_id=operator_id)
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
        assert event.actor_id == operator_id
        assert event.action == 'initial_administrator_assigned'
        assert event.prior_state == {
            'operation': 'deployment_bootstrap',
            'operator_user_id': str(operator_id),
            'target_user_id': str(target_id),
            'role': 'reader',
        }
        assert event.resulting_state == {
            'operation': 'deployment_bootstrap',
            'operator_user_id': str(operator_id),
            'target_user_id': str(target_id),
            'role': 'administrator',
        }


def test_cli_allows_explicit_same_operator_and_target(admin_database):
    url, factory = admin_database
    with factory.begin() as session:
        target = _user(); session.add(target); session.flush(); target_id = target.id
    result = _invoke(url, target_id, operator_user_id=target_id)
    assert result.exit_code == 0
    with factory() as session:
        event = session.scalar(select(SourceAuditEvent))
        assert event.actor_id == target_id
        assert event.resulting_state['operator_user_id'] == str(target_id)


@pytest.mark.parametrize('kind', ['missing', 'inactive'])
def test_cli_rejects_missing_or_inactive_operator(admin_database, kind):
    url, factory = admin_database
    with factory.begin() as session:
        target = _user(); session.add(target); session.flush(); target_id = target.id
        if kind == 'inactive':
            operator = _user(active=False); session.add(operator); session.flush()
            operator_id = operator.id
        else:
            operator_id = uuid4()
    result = _invoke(url, target_id, operator_user_id=operator_id)
    assert result.exit_code != 0
    assert json.loads(result.stderr)['error_code'] == f'operator_{kind}'
    with factory() as session:
        assert session.get(User, target_id).role == 'reader'
        assert session.scalar(select(SourceAuditEvent)) is None


def test_cli_is_idempotent_for_sole_administrator_and_refuses_another(admin_database):
    url, factory = admin_database
    with factory.begin() as session:
        first = _user(); second = _user(); session.add_all([first, second]); session.flush()
        first_id, second_id = first.id, second.id
    assert _invoke(url, first_id).exit_code == 0
    rerun = _invoke(url, first_id)
    refusal = _invoke(url, second_id)
    assert rerun.exit_code == 0 and json.loads(rerun.stdout)['changed'] is False
    assert refusal.exit_code != 0
    assert json.loads(refusal.stderr)['error_code'] == 'bootstrap_already_completed'
    with factory() as session:
        assert len(session.scalars(select(SourceAuditEvent)).all()) == 1
        assert session.get(User, second_id).role == 'reader'


def test_cli_rolls_back_role_when_audit_flush_fails(admin_database, monkeypatch):
    url, factory = admin_database
    with factory.begin() as session:
        target = _user(); session.add(target); session.flush(); target_id = target.id
    def fail(*args, **kwargs):
        raise RuntimeError('audit unavailable secret-token@example.test')
    monkeypatch.setattr('app.research_library.admin_cli.append_source_audit_event', fail)
    result = _invoke(url, target_id)
    assert result.exit_code != 0
    error = json.loads(result.stderr)
    assert error == {
        'changed': False,
        'error_code': 'operator_failure',
        'message': 'Administrator assignment failed safely',
    }
    assert 'audit unavailable' not in result.output
    assert 'secret-token@example.test' not in result.output
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
                event = _assign(session, target_id, target_id)
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
    sql = str(locked_user_query(uuid4(), uuid4()).compile(dialect=__import__('sqlalchemy').dialects.postgresql.dialect()))
    assert 'FOR UPDATE' in sql


def test_cli_source_has_no_email_targeting():
    import inspect
    from app.research_library import admin_cli
    source = inspect.getsource(admin_cli)
    assert '--email' not in source
    assert 'User.email' not in source


def test_malformed_user_id_is_fixed_json_and_never_echoed(monkeypatch):
    secret = 'postgresql://admin:hunter2@db.test/prod?owner=secret@example.test'
    engine_called = False

    def fail_if_called(*args, **kwargs):
        nonlocal engine_called
        engine_called = True
        raise AssertionError('engine must not be called')

    monkeypatch.setattr(
        'app.research_library.admin_cli.create_database_engine', fail_if_called
    )
    result = runner.invoke(app, [
        'assign-initial-administrator', '--database-url', 'sqlite:///unused.db',
        '--user-id', secret, '--operator-user-id', str(uuid4()),
        '--confirmation', 'GRANT-ADMINISTRATOR',
    ])
    assert result.exit_code != 0
    assert json.loads(result.stderr) == {
        'changed': False,
        'error_code': 'invalid_user_id',
        'message': 'User ID must be a valid UUID',
    }
    assert secret not in result.output
    assert not engine_called


def test_malformed_operator_user_id_is_fixed_json_and_never_echoed(monkeypatch):
    secret = 'operator-secret@example.test?token=hunter2'
    engine_called = False

    def fail_if_called(*args, **kwargs):
        nonlocal engine_called
        engine_called = True
        raise AssertionError('engine must not be called')

    monkeypatch.setattr(
        'app.research_library.admin_cli.create_database_engine', fail_if_called
    )
    result = runner.invoke(app, [
        'assign-initial-administrator', '--database-url', 'sqlite:///unused.db',
        '--user-id', str(uuid4()), '--operator-user-id', secret,
        '--confirmation', 'GRANT-ADMINISTRATOR',
    ])
    assert result.exit_code != 0
    assert json.loads(result.stderr)['error_code'] == 'invalid_operator_user_id'
    assert secret not in result.output
    assert not engine_called


def test_unsupported_stored_role_is_not_interpolated(admin_database):
    url, factory = admin_database
    target = _user()
    with factory.begin() as session:
        session.add(target); session.flush(); target_id = target.id
    secret_role = 'credential-hunter2-secret@example.test'
    with factory.kw['bind'].begin() as connection:
        connection.exec_driver_sql('PRAGMA ignore_check_constraints=ON')
        connection.execute(
            User.__table__.update().where(User.id == target_id).values(role=secret_role)
        )
        connection.exec_driver_sql('PRAGMA ignore_check_constraints=OFF')
    result = _invoke(url, target_id)
    assert result.exit_code != 0
    assert json.loads(result.stderr)['error_code'] == 'target_not_reader'
    assert secret_role not in result.output


def test_database_setup_failure_is_generic_and_does_not_expose_url(monkeypatch):
    supplied_url = 'postgresql://operator:hunter2@private.example/prod'
    injected = 'engine failed for token=abc123 and owner@example.test'

    def fail(*args, **kwargs):
        raise RuntimeError(injected)

    monkeypatch.setattr('app.research_library.admin_cli.create_database_engine', fail)
    result = _invoke(supplied_url, uuid4())
    assert result.exit_code != 0
    assert json.loads(result.stderr) == {
        'changed': False,
        'error_code': 'operator_failure',
        'message': 'Administrator assignment failed safely',
    }
    combined = result.output
    assert supplied_url not in combined
    assert injected not in combined
    assert 'hunter2' not in combined
    assert 'owner@example.test' not in combined


def test_post_commit_disposal_failure_reports_truthful_success_warning(
    admin_database, monkeypatch
):
    url, factory = admin_database
    engine = factory.kw['bind']
    with factory.begin() as session:
        target = _user(); session.add(target); session.flush(); target_id = target.id
    injected = 'dispose failed postgresql://admin:hunter2@private/prod'
    monkeypatch.setattr(
        'app.research_library.admin_cli.create_database_engine', lambda settings: engine
    )
    monkeypatch.setattr(engine, 'dispose', lambda: (_ for _ in ()).throw(RuntimeError(injected)))
    result = _invoke('sqlite:///not-used.db', target_id)
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['changed'] is True
    assert UUID(payload['audit_event_id'])
    assert payload['warning_code'] == 'engine_cleanup_failed'
    assert result.stderr == ''
    assert injected not in result.output
    clean_engine = create_engine(url)
    clean_factory = create_session_factory(clean_engine)
    with clean_factory() as session:
        assert session.get(User, target_id).role == 'administrator'
        assert len(session.scalars(select(SourceAuditEvent)).all()) == 1
    clean_engine.dispose()


def test_unsupported_database_dialect_is_rejected_before_session_or_mutation(
    admin_database, monkeypatch
):
    url, factory = admin_database
    engine = factory.kw['bind']
    with factory.begin() as session:
        target = _user(); session.add(target); session.flush(); target_id = target.id
    monkeypatch.setattr(
        'app.research_library.admin_cli.create_database_engine', lambda settings: engine
    )
    monkeypatch.setattr(engine.dialect, 'name', 'mysql')
    session_called = False

    def fail_if_called(*args, **kwargs):
        nonlocal session_called
        session_called = True
        raise AssertionError('session factory must not be called')

    monkeypatch.setattr(
        'app.research_library.admin_cli.create_session_factory', fail_if_called
    )
    result = _invoke('mysql://not-used', target_id)
    assert result.exit_code != 0
    assert json.loads(result.stderr)['error_code'] == 'unsupported_database'
    assert not session_called
    clean_engine = create_engine(url)
    with create_session_factory(clean_engine)() as session:
        assert session.get(User, target_id).role == 'reader'
        assert session.scalar(select(SourceAuditEvent)) is None
    clean_engine.dispose()


def test_success_output_is_still_machine_readable_and_secret_free(admin_database):
    url, factory = admin_database
    with factory.begin() as session:
        target = _user(); session.add(target); session.flush(); target_id = target.id
    result = _invoke(url, target_id)
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload['changed'] is True
    assert payload['target_user_id'] == str(target_id)
    assert result.stderr == ''
