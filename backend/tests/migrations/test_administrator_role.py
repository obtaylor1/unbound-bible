from io import StringIO
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg2
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError


BACKEND_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = BACKEND_ROOT / 'alembic/versions/0015_administrator_role.py'


def _config(url):
    config = Config(str(BACKEND_ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND_ROOT / 'alembic'))
    config.set_main_option('sqlalchemy.url', url)
    return config


def _seed(connection, roles):
    ids = {}
    for role in roles:
        user_id = uuid4().hex; ids[role] = user_id
        connection.execute(text(
            "INSERT INTO users (id,email,email_normalized,username,password_hash,role,is_active) "
            "VALUES (:id,:email,:email,:username,'x',:role,1)"
        ), {'id': user_id, 'email': f'{role}@example.test', 'username': role, 'role': role})
    session_id = uuid4().hex
    connection.execute(text(
        "INSERT INTO auth_sessions (id,user_id,refresh_token_hash,expires_at) "
        "VALUES (:id,:user,'hash',CURRENT_TIMESTAMP)"
    ), {'id': session_id, 'user': next(iter(ids.values()))})
    return ids, session_id


def test_revision_is_frozen():
    source = MIGRATION.read_text()
    assert 'from app' not in source and 'Base.metadata' not in source


def test_sqlite_upgrade_downgrade_and_reupgrade_preserve_rows_and_fk(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    url = f"sqlite:///{tmp_path / 'roles.db'}"; config = _config(url)
    command.upgrade(config, '0014_research_library_core')
    engine = create_engine(url)
    with engine.begin() as connection:
        ids, session_id = _seed(connection, ['member', 'admin', 'moderator', 'reader', 'administrator'])
        connection.execute(text(
            'UPDATE users SET legacy_forum_user_id=77 WHERE username=\'member\''
        ))
        original_created_at = connection.scalar(text(
            "SELECT created_at FROM users WHERE username='member'"
        ))
    command.upgrade(config, '0015_administrator_role')
    with engine.connect() as connection:
        roles = dict(connection.execute(text('SELECT username, role FROM users')).all())
        assert roles == {'member':'reader','admin':'administrator','moderator':'reader','reader':'reader','administrator':'administrator'}
        assert connection.scalar(text('SELECT user_id FROM auth_sessions WHERE id=:id'), {'id': session_id}) == ids['member']
        assert connection.scalar(text("SELECT legacy_forum_user_id FROM users WHERE username='member'")) == 77
        assert connection.scalar(text("SELECT created_at FROM users WHERE username='member'")) == original_created_at
    assert {index['name'] for index in inspect(engine).get_indexes('users')} >= {
        'ux_users_email_normalized', 'ux_users_username'
    }
    assert any(
        fk['referred_table'] == 'users'
        for fk in inspect(engine).get_foreign_keys('auth_sessions')
    )
    role_column = next(c for c in inspect(engine).get_columns('users') if c['name'] == 'role')
    assert role_column['nullable'] is False and 'reader' in str(role_column['default'])
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO users (id,email,email_normalized,username,password_hash,is_active) "
            "VALUES (:id,'default@x','default@x','default','x',1)"
        ), {'id': uuid4().hex})
        assert connection.scalar(text("SELECT role FROM users WHERE username='default'")) == 'reader'
        with pytest.raises(IntegrityError):
            connection.execute(text(
                "INSERT INTO users (id,email,email_normalized,username,password_hash,role,is_active) "
                "VALUES (:id,'x@x','x@x','x','x','admin',1)"
            ), {'id': uuid4().hex})
    command.downgrade(config, '0014_research_library_core')
    with engine.connect() as connection:
        assert set(connection.execute(text('SELECT role FROM users')).scalars()) <= {'member', 'admin'}
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO users (id,email,email_normalized,username,password_hash,is_active) "
            "VALUES (:id,'down@x','down@x','down','x',1)"
        ), {'id': uuid4().hex})
        assert connection.scalar(text("SELECT role FROM users WHERE username='down'")) == 'member'
    command.upgrade(config, '0015_administrator_role')
    with engine.connect() as connection:
        assert set(connection.execute(text('SELECT role FROM users')).scalars()) <= {'reader', 'administrator'}
    engine.dispose()


def test_unknown_role_fails_without_mutating_roles(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    url = f"sqlite:///{tmp_path / 'unknown.db'}"; config = _config(url)
    command.upgrade(config, '0014_research_library_core')
    engine = create_engine(url)
    with engine.begin() as connection:
        _seed(connection, ['member', 'mystery'])
    with pytest.raises(Exception, match='Unsupported user roles.*mystery'):
        command.upgrade(config, '0015_administrator_role')
    with engine.connect() as connection:
        assert dict(connection.execute(text('SELECT username, role FROM users')).all()) == {'member':'member','mystery':'mystery'}
    engine.dispose()


def test_postgresql_offline_ddl_has_mapping_default_and_check():
    config = _config('postgresql://user:pass@localhost/db')
    output = StringIO(); config.output_buffer = output
    command.upgrade(config, '0014_research_library_core:0015_administrator_role', sql=True)
    sql = output.getvalue().lower()
    assert "update users set role = 'reader'" in sql
    assert 'alter column role set default' in sql
    assert 'constraint ck_users_role check' in sql
    assert 'for update' not in sql


@pytest.mark.skipif(not __import__('os').environ.get('TEST_POSTGRES_DATABASE_URL'), reason='TEST_POSTGRES_DATABASE_URL not configured')
def test_live_postgresql_role_migration():
    service_url = os.environ['TEST_POSTGRES_DATABASE_URL']
    parsed = make_url(service_url)
    database_name = f'unbound_roles_{uuid4().hex}'
    admin = psycopg2.connect(
        host=parsed.host, port=parsed.port, user=parsed.username,
        password=parsed.password, dbname=parsed.database,
    )
    admin.autocommit = True
    engine = None
    try:
        with admin.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{database_name}"')
        isolated_url = parsed.set(database=database_name).render_as_string(hide_password=False)
        config = _config(isolated_url)
        command.upgrade(config, '0014_research_library_core')
        engine = create_engine(isolated_url)
        with engine.begin() as connection:
            ids, session_id = _seed(connection, ['member', 'admin', 'moderator'])
        engine.dispose(); engine = None

        command.upgrade(config, '0015_administrator_role')
        engine = create_engine(isolated_url)
        with engine.begin() as connection:
            assert dict(connection.execute(text('SELECT username, role FROM users')).all()) == {
                'member': 'reader', 'admin': 'administrator', 'moderator': 'reader'
            }
            assert str(connection.scalar(text(
                'SELECT user_id FROM auth_sessions WHERE id=:id'
            ), {'id': session_id})).replace('-', '') == ids['member']
            connection.execute(text(
                "INSERT INTO users (id,email,email_normalized,username,password_hash,is_active) "
                "VALUES (:id,'default@x','default@x','default','x',true)"
            ), {'id': uuid4()})
            assert connection.scalar(text("SELECT role FROM users WHERE username='default'")) == 'reader'
        with engine.connect() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(text(
                    "INSERT INTO users (id,email,email_normalized,username,password_hash,role,is_active) "
                    "VALUES (:id,'bad@x','bad@x','bad','x','admin',true)"
                ), {'id': uuid4()})
            connection.rollback()

        from app.database import create_session_factory
        from app.research_library.admin_cli import (
            AdministratorAssignmentError,
            _assign,
        )

        attempts = []
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM users WHERE username='admin'"))
            for name in ('operator-one', 'target-one', 'operator-two', 'target-two'):
                user_id = uuid4(); attempts.append((name, user_id))
                connection.execute(text(
                    "INSERT INTO users "
                    "(id,email,email_normalized,username,password_hash,is_active) "
                    "VALUES (:id,:email,:email,:name,'x',true)"
                ), {'id': user_id, 'email': f'{name}@example.test', 'name': name})
        ids_by_name = dict(attempts)
        barrier = Barrier(2)
        factory = create_session_factory(engine)

        def bootstrap(operator_name, target_name):
            barrier.wait()
            try:
                with factory.begin() as session:
                    event = _assign(
                        session, ids_by_name[target_name], ids_by_name[operator_name]
                    )
                    return ('changed', str(event.id))
            except AdministratorAssignmentError as error:
                return ('refused', error.code)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda names: bootstrap(*names),
                (('operator-one', 'target-one'), ('operator-two', 'target-two')),
            ))
        assert sorted(result[0] for result in results) == ['changed', 'refused']
        assert ('refused', 'bootstrap_already_completed') in results
        with engine.connect() as connection:
            assert connection.scalar(text(
                "SELECT count(*) FROM users WHERE role='administrator'"
            )) == 1
            assert connection.scalar(text('SELECT count(*) FROM source_audit_events')) == 1
            audit_actor, resulting_state = connection.execute(text(
                'SELECT actor_id, resulting_state FROM source_audit_events'
            )).one()
            state = resulting_state if isinstance(resulting_state, dict) else __import__('json').loads(resulting_state)
            assert str(audit_actor) == state['operator_user_id']
            assert state['operation'] == 'deployment_bootstrap'
        engine.dispose(); engine = None

        command.downgrade(config, '0014_research_library_core')
        engine = create_engine(isolated_url)
        with engine.begin() as connection:
            assert set(connection.execute(text('SELECT role FROM users')).scalars()) <= {'member', 'admin'}
            connection.execute(text(
                "INSERT INTO users (id,email,email_normalized,username,password_hash,is_active) "
                "VALUES (:id,'down@x','down@x','down','x',true)"
            ), {'id': uuid4()})
            assert connection.scalar(text("SELECT role FROM users WHERE username='down'")) == 'member'
    finally:
        if engine is not None:
            engine.dispose()
        with admin.cursor() as cursor:
            cursor.execute(
                'SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
                'WHERE datname=%s AND pid <> pg_backend_pid()', (database_name,)
            )
            cursor.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        admin.close()
