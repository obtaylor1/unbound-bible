from __future__ import annotations

import os
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.operations import backup


DATABASE_URL = "postgresql://staging:super-secret@db:5432/unbound_bible"


def test_backup_filename_is_deterministic_utc_and_contains_no_credentials():
    name = backup.backup_filename(datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc))

    assert name == "unbound-bible-20260810T120000Z.dump"
    assert "postgres" not in name
    with pytest.raises(ValueError, match="timezone-aware"):
        backup.backup_filename(datetime(2026, 8, 10, 12, 0))


@pytest.mark.parametrize("missing", ["DATABASE_URL", "BACKUP_DIR"])
def test_environment_requires_explicit_database_url_and_backup_dir(monkeypatch, missing):
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("BACKUP_DIR", "/secure/backups")
    monkeypatch.delenv(missing)

    with pytest.raises(backup.BackupPolicyError, match=missing):
        backup.settings_from_environment()


def test_backup_uses_custom_format_atomic_output_and_restrictive_permissions(tmp_path, monkeypatch):
    calls = []

    def fake_run(argv, *, env=None, cwd=None):
        calls.append((argv, env, cwd))
        output = Path(argv[argv.index("--file") + 1])
        output.write_bytes(b"PGDMP-test")

    monkeypatch.setattr(backup, "_run_command", fake_run)

    output = backup.create_backup(
        DATABASE_URL,
        tmp_path / "nested" / "backups",
        now=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
    )

    assert output.name == "unbound-bible-20260810T120000Z.dump"
    assert output.read_bytes() == b"PGDMP-test"
    assert stat.S_IMODE(output.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    argv, env, cwd = calls[0]
    assert argv[:3] == ["pg_dump", "--format=custom", "--no-owner"]
    assert "--no-privileges" in argv
    assert DATABASE_URL not in argv
    assert "super-secret" not in " ".join(argv)
    assert argv[argv.index("--dbname") + 1] == "postgresql://staging@db:5432/unbound_bible"
    assert argv[argv.index("--file") + 1] != str(output)
    assert env["PGPASSWORD"] == "super-secret"
    assert cwd is None
    assert not list(output.parent.glob("*.tmp"))


def test_backup_failure_removes_partial_file_and_never_exposes_credentials(tmp_path, monkeypatch):
    def fail(argv, *, env=None, cwd=None):
        Path(argv[argv.index("--file") + 1]).write_bytes(b"partial")
        raise backup.BackupOperationError("pg_dump failed")

    monkeypatch.setattr(backup, "_run_command", fail)

    with pytest.raises(backup.BackupOperationError) as caught:
        backup.create_backup(DATABASE_URL, tmp_path)

    assert "super-secret" not in str(caught.value)
    assert list(tmp_path.iterdir()) == []


def test_command_runner_uses_argument_array_without_shell_and_redacts_failure(monkeypatch):
    observed = {}

    def fake_run(argv, **kwargs):
        observed.update(argv=argv, kwargs=kwargs)
        raise subprocess.CalledProcessError(2, argv, stderr=f"could not connect to {DATABASE_URL}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(backup.BackupOperationError) as caught:
        backup._run_command(["pg_dump", "--dbname", DATABASE_URL])

    assert isinstance(observed["argv"], list)
    assert observed["kwargs"]["shell"] is False
    assert observed["kwargs"]["check"] is True
    assert "super-secret" not in str(caught.value)
    assert DATABASE_URL not in str(caught.value)


def test_restore_verification_reports_release_count_mismatches():
    result = backup.compare_release_counts(
        before={"biblical_texts": 38_938, "users": 4},
        after={"biblical_texts": 38_937, "users": 4},
    )

    assert result.ok is False
    assert result.mismatches == {"biblical_texts": (38_938, 38_937)}


def test_disposable_database_names_are_random_and_strictly_guarded(monkeypatch):
    tokens = iter(["a" * 24, "b" * 24])
    monkeypatch.setattr(backup.secrets, "token_hex", lambda _length: next(tokens))

    first = backup.disposable_database_name()
    second = backup.disposable_database_name()

    assert first == "unbound_restore_check_" + "a" * 24
    assert first != second
    backup.assert_disposable_database_name(first)
    for unsafe in ["unbound_bible", "postgres", "unbound_restore_check_", "unbound_restore_check_bad-name"]:
        with pytest.raises(backup.BackupPolicyError, match="disposable"):
            backup.assert_disposable_database_name(unsafe)


def test_database_create_and_cleanup_use_parameterized_termination_and_identifier(monkeypatch):
    executed = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, parameters=None):
            executed.append((statement, parameters))

    connection = SimpleNamespace(autocommit=False, cursor=lambda: Cursor(), close=lambda: executed.append(("closed", None)))
    monkeypatch.setattr(backup.psycopg2, "connect", lambda _url: connection)
    name = "unbound_restore_check_" + "c" * 24

    backup._create_disposable_database(DATABASE_URL, name)
    backup._drop_disposable_database(DATABASE_URL, name)

    assert connection.autocommit is True
    assert executed[0][1] is None
    terminate_statement, terminate_parameters = executed[2]
    assert terminate_parameters == (name,)
    assert "%s" in str(terminate_statement)
    assert executed[-2][1] is None
    assert sum(item == ("closed", None) for item in executed) == 2


def test_restore_check_restores_migrates_starts_app_checks_health_compares_and_cleans_up(
    tmp_path, monkeypatch
):
    dump = tmp_path / "unbound-bible-20260810T120000Z.dump"
    dump.write_bytes(b"PGDMP-test")
    name = "unbound_restore_check_" + "d" * 24
    calls = []
    source_counts = {table: index for index, table in enumerate(backup.RELEASE_CRITICAL_TABLES, 1)}

    monkeypatch.setattr(backup, "disposable_database_name", lambda: name)
    monkeypatch.setattr(backup, "_create_disposable_database", lambda url, database: calls.append(("create", url, database)))
    monkeypatch.setattr(backup, "_drop_disposable_database", lambda url, database: calls.append(("drop", url, database)))
    monkeypatch.setattr(backup, "_read_release_counts", lambda url: source_counts.copy())
    monkeypatch.setattr(backup, "_run_command", lambda argv, **kwargs: calls.append(("command", argv, kwargs)))
    monkeypatch.setattr(
        backup,
        "_verify_restored_application",
        lambda url: calls.append(("health", url)) or {
            "/api/v1/health": {"status": "healthy"},
            "/api/v1/health/providers": {"status": "healthy"},
        },
    )

    result = backup.verify_restore(DATABASE_URL, tmp_path, dump_file=dump)

    assert result.ok is True
    assert result.database_name == name
    assert "restored_database_url" not in result.__dict__
    restored_url = next(call[1][call[1].index("--dbname") + 1] for call in calls if call[0] == "command" and call[1][0] == "pg_restore")
    assert restored_url.endswith("/" + name)
    assert "super-secret" not in restored_url
    assert restored_url != DATABASE_URL
    commands = [call for call in calls if call[0] == "command"]
    assert commands[0][1][0] == "pg_restore"
    assert commands[0][1][commands[0][1].index("--dbname") + 1] == restored_url
    assert commands[0][2]["env"]["PGPASSWORD"] == "super-secret"
    assert commands[1][1] == ["alembic", "-c", "alembic.ini", "upgrade", "head"]
    assert commands[1][2]["env"]["DATABASE_URL"].endswith("/" + name)
    assert commands[1][2]["env"]["DATABASE_URL"] != DATABASE_URL
    health_url = next(call[1] for call in calls if call[0] == "health")
    assert health_url.endswith("/" + name)
    assert health_url != DATABASE_URL
    assert calls[-1] == ("drop", DATABASE_URL, name)


def test_restore_check_fails_on_count_mismatch_and_always_cleans_up(tmp_path, monkeypatch):
    dump = tmp_path / "latest.dump"
    dump.write_bytes(b"PGDMP-test")
    name = "unbound_restore_check_" + "e" * 24
    calls = []
    before = {table: 1 for table in backup.RELEASE_CRITICAL_TABLES}
    after = {**before, "biblical_texts": 0}

    monkeypatch.setattr(backup, "disposable_database_name", lambda: name)
    monkeypatch.setattr(backup, "_create_disposable_database", lambda *_args: calls.append("create"))
    monkeypatch.setattr(backup, "_drop_disposable_database", lambda *_args: calls.append("drop"))
    monkeypatch.setattr(backup, "_run_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(backup, "_verify_restored_application", lambda *_args: {})
    monkeypatch.setattr(backup, "_read_release_counts", lambda url: before if url == DATABASE_URL else after)

    with pytest.raises(backup.BackupVerificationError, match="biblical_texts"):
        backup.verify_restore(DATABASE_URL, tmp_path, dump_file=dump)

    assert calls == ["create", "drop"]


def test_restore_check_cleans_up_after_migration_or_health_failure_without_leaking_credentials(
    tmp_path, monkeypatch
):
    dump = tmp_path / "latest.dump"
    dump.write_bytes(b"PGDMP-test")
    name = "unbound_restore_check_" + "f" * 24
    calls = []

    monkeypatch.setattr(backup, "disposable_database_name", lambda: name)
    monkeypatch.setattr(backup, "_create_disposable_database", lambda *_args: calls.append("create"))
    monkeypatch.setattr(backup, "_drop_disposable_database", lambda *_args: calls.append("drop"))
    monkeypatch.setattr(backup, "_read_release_counts", lambda _url: {table: 1 for table in backup.RELEASE_CRITICAL_TABLES})
    monkeypatch.setattr(backup, "_run_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        backup,
        "_verify_restored_application",
        lambda _url: (_ for _ in ()).throw(backup.BackupVerificationError("health check failed")),
    )

    with pytest.raises(backup.BackupVerificationError) as caught:
        backup.verify_restore(DATABASE_URL, tmp_path, dump_file=dump)

    assert calls == ["create", "drop"]
    assert "super-secret" not in str(caught.value)


def test_restore_check_attempts_guarded_cleanup_when_database_creation_partially_fails(
    tmp_path, monkeypatch
):
    dump = tmp_path / "latest.dump"
    dump.write_bytes(b"PGDMP-test")
    name = "unbound_restore_check_" + "1" * 24
    calls = []

    monkeypatch.setattr(backup, "disposable_database_name", lambda: name)
    monkeypatch.setattr(
        backup,
        "_create_disposable_database",
        lambda *_args: (_ for _ in ()).throw(backup.BackupOperationError("create failed")),
    )
    monkeypatch.setattr(backup, "_drop_disposable_database", lambda *_args: calls.append("drop"))
    monkeypatch.setattr(backup, "_read_release_counts", lambda _url: {table: 1 for table in backup.RELEASE_CRITICAL_TABLES})

    with pytest.raises(backup.BackupOperationError, match="create failed"):
        backup.verify_restore(DATABASE_URL, tmp_path, dump_file=dump)

    assert calls == ["drop"]


def test_latest_backup_rejects_empty_or_non_dump_directory(tmp_path):
    with pytest.raises(backup.BackupPolicyError, match="No backup dump"):
        backup.latest_backup(tmp_path)
    (tmp_path / "notes.txt").write_text("not a dump", encoding="utf-8")
    with pytest.raises(backup.BackupPolicyError, match="No backup dump"):
        backup.latest_backup(tmp_path)


def test_shell_scripts_are_minimal_executable_exec_wrappers():
    root = Path(__file__).parents[3]
    expectations = {
        "scripts/backup-staging.sh": "python -m app.operations.backup backup",
        "scripts/restore-check-staging.sh": "python -m app.operations.backup restore-check",
    }

    for relative, command in expectations.items():
        path = root / relative
        text = path.read_text(encoding="utf-8")
        assert stat.S_IMODE(path.stat().st_mode) == 0o755
        assert text.splitlines() == ["#!/bin/sh", "set -eu", f"exec {command}"]
