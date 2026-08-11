from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.operations import backup


DATABASE_URL = "postgresql://staging:super-secret@db:5432/unbound_bible"


def _write_manifest(dump: Path, counts: dict[str, int], *, digest: str | None = None) -> Path:
    path = dump.with_suffix(dump.suffix + ".manifest.json")
    payload = {
        "schema_version": 1,
        "created_at": "2026-08-10T12:00:00Z",
        "snapshot": {"strategy": "pg_export_snapshot"},
        "dump": {
            "filename": dump.name,
            "format": "postgresql-custom",
            "sha256": digest or hashlib.sha256(dump.read_bytes()).hexdigest(),
        },
        "release_critical_counts": counts,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    return path


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
    durability_calls = []
    counts = {table: index for index, table in enumerate(backup.RELEASE_CRITICAL_TABLES, 1)}

    @contextmanager
    def fake_snapshot(_database_url):
        yield "00000003-0000001B-1", counts

    def fake_run(argv, *, env=None, cwd=None):
        calls.append((argv, env, cwd))
        output = Path(argv[argv.index("--file") + 1])
        output.write_bytes(b"PGDMP-test")

    monkeypatch.setattr(backup, "_run_command", fake_run)
    monkeypatch.setattr(backup, "_release_snapshot", fake_snapshot, raising=False)
    monkeypatch.setattr(
        backup, "_fsync_file", lambda path: durability_calls.append(("file", path.name)), raising=False
    )
    monkeypatch.setattr(
        backup,
        "_fsync_directory",
        lambda path: durability_calls.append(("directory", path.name)),
        raising=False,
    )

    output = backup.create_backup(
        DATABASE_URL,
        tmp_path / "nested" / "backups",
        now=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
    )

    assert output.name == "unbound-bible-20260810T120000Z.dump"
    assert output.read_bytes() == b"PGDMP-test"
    assert stat.S_IMODE(output.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    manifest_path = output.with_suffix(".dump.manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert stat.S_IMODE(manifest_path.stat().st_mode) == 0o600
    assert manifest["schema_version"] == 1
    assert manifest["created_at"] == "2026-08-10T12:00:00Z"
    assert manifest["snapshot"] == {"strategy": "pg_export_snapshot"}
    assert manifest["dump"] == {
        "filename": output.name,
        "format": "postgresql-custom",
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    assert manifest["release_critical_counts"] == counts
    argv, env, cwd = calls[0]
    assert argv[:3] == ["pg_dump", "--format=custom", "--no-owner"]
    assert "--no-privileges" in argv
    assert argv[argv.index("--snapshot") + 1] == "00000003-0000001B-1"
    assert DATABASE_URL not in argv
    assert "super-secret" not in " ".join(argv)
    assert argv[argv.index("--dbname") + 1] == "postgresql://staging@db:5432/unbound_bible"
    assert argv[argv.index("--file") + 1] != str(output)
    assert env["PGPASSWORD"] == "super-secret"
    assert cwd is None
    assert not list(output.parent.glob("*.tmp"))
    assert durability_calls[0][0] == "file"
    assert durability_calls.count(("directory", "backups")) == 2


def test_fsync_helpers_sync_the_opened_file_and_directory_descriptors(tmp_path, monkeypatch):
    target = tmp_path / "backup.dump"
    target.write_bytes(b"PGDMP-test")
    calls = []
    real_open = os.open
    real_close = os.close

    def observed_open(path, flags):
        descriptor = real_open(path, flags)
        calls.append(("open", Path(path), descriptor, flags))
        return descriptor

    monkeypatch.setattr(backup.os, "open", observed_open)
    monkeypatch.setattr(backup.os, "fsync", lambda descriptor: calls.append(("fsync", descriptor)))
    monkeypatch.setattr(
        backup.os,
        "close",
        lambda descriptor: (calls.append(("close", descriptor)), real_close(descriptor))[1],
    )

    backup._fsync_file(target)
    backup._fsync_directory(tmp_path)

    opened = [call for call in calls if call[0] == "open"]
    assert len(opened) == 2
    assert [call[1] for call in opened] == [target, tmp_path]
    for _, _, descriptor, _ in opened:
        assert ("fsync", descriptor) in calls
        assert ("close", descriptor) in calls


def test_release_counts_and_dump_share_one_exported_repeatable_read_snapshot(monkeypatch):
    events = []
    rows = iter([("snapshot-42",), *((index,) for index, _ in enumerate(backup.RELEASE_CRITICAL_TABLES, 1))])

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, parameters=None):
            events.append(("execute", str(statement), parameters))

        def fetchone(self):
            return next(rows)

    class Connection:
        def set_session(self, **kwargs):
            events.append(("set_session", kwargs))

        def cursor(self):
            return Cursor()

        def rollback(self):
            events.append(("rollback",))

        def close(self):
            events.append(("close",))

    monkeypatch.setattr(backup.psycopg2, "connect", lambda _url: Connection())

    with backup._release_snapshot(DATABASE_URL) as (snapshot_id, counts):
        events.append(("yield", snapshot_id))
        assert counts == {
            table: index for index, table in enumerate(backup.RELEASE_CRITICAL_TABLES, 1)
        }

    assert snapshot_id == "snapshot-42"
    assert events[0] == (
        "set_session",
        {"isolation_level": "REPEATABLE READ", "readonly": True, "autocommit": False},
    )
    assert "pg_export_snapshot" in events[1][1]
    assert events[-2:] == [("rollback",), ("close",)]


def test_backup_failure_removes_partial_file_and_never_exposes_credentials(tmp_path, monkeypatch):
    @contextmanager
    def fake_snapshot(_database_url):
        yield "snapshot-42", {table: 0 for table in backup.RELEASE_CRITICAL_TABLES}

    def fail(argv, *, env=None, cwd=None):
        Path(argv[argv.index("--file") + 1]).write_bytes(b"partial")
        raise backup.BackupOperationError("pg_dump failed")

    monkeypatch.setattr(backup, "_release_snapshot", fake_snapshot)
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
    _write_manifest(dump, source_counts)

    monkeypatch.setattr(backup, "disposable_database_name", lambda: name)
    monkeypatch.setattr(backup, "_create_disposable_database", lambda url, database: calls.append(("create", url, database)))
    monkeypatch.setattr(backup, "_drop_disposable_database", lambda url, database: calls.append(("drop", url, database)))
    count_urls = []
    monkeypatch.setattr(
        backup,
        "_read_release_counts",
        lambda url: count_urls.append(url) or source_counts.copy(),
    )
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
    assert len(count_urls) == 1
    assert count_urls[0].endswith("/" + name)


def test_restore_check_fails_on_count_mismatch_and_always_cleans_up(tmp_path, monkeypatch):
    dump = tmp_path / "latest.dump"
    dump.write_bytes(b"PGDMP-test")
    name = "unbound_restore_check_" + "e" * 24
    calls = []
    before = {table: 1 for table in backup.RELEASE_CRITICAL_TABLES}
    after = {**before, "biblical_texts": 0}
    _write_manifest(dump, before)

    monkeypatch.setattr(backup, "disposable_database_name", lambda: name)
    monkeypatch.setattr(backup, "_create_disposable_database", lambda *_args: calls.append("create"))
    monkeypatch.setattr(backup, "_drop_disposable_database", lambda *_args: calls.append("drop"))
    monkeypatch.setattr(backup, "_run_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(backup, "_verify_restored_application", lambda *_args: {})
    monkeypatch.setattr(backup, "_read_release_counts", lambda _url: after)

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
    _write_manifest(dump, {table: 1 for table in backup.RELEASE_CRITICAL_TABLES})

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
    _write_manifest(dump, {table: 1 for table in backup.RELEASE_CRITICAL_TABLES})

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


def test_restore_rejects_a_dump_that_does_not_match_its_manifest_before_database_creation(
    tmp_path, monkeypatch
):
    dump = tmp_path / "unbound-bible-20260810T120000Z.dump"
    dump.write_bytes(b"PGDMP-original")
    _write_manifest(dump, {table: 1 for table in backup.RELEASE_CRITICAL_TABLES})
    dump.write_bytes(b"PGDMP-tampered")
    calls = []
    monkeypatch.setattr(backup, "_create_disposable_database", lambda *_args: calls.append("create"))

    with pytest.raises(backup.BackupVerificationError, match="digest"):
        backup.verify_restore(DATABASE_URL, tmp_path, dump_file=dump)

    assert calls == []


def test_restore_rejects_invalid_manifest_timestamp_before_database_creation(
    tmp_path, monkeypatch
):
    dump = tmp_path / "unbound-bible-20260810T120000Z.dump"
    dump.write_bytes(b"PGDMP-test")
    manifest_path = _write_manifest(
        dump, {table: 1 for table in backup.RELEASE_CRITICAL_TABLES}
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["created_at"] = "sometime"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_path.chmod(0o600)
    calls = []
    monkeypatch.setattr(backup, "_create_disposable_database", lambda *_args: calls.append("create"))

    with pytest.raises(backup.BackupVerificationError, match="timestamp"):
        backup.verify_restore(DATABASE_URL, tmp_path, dump_file=dump)

    assert calls == []


def test_latest_backup_ignores_newer_orphan_and_manifest_symlink(tmp_path):
    complete = tmp_path / "unbound-bible-20260810T120000Z.dump"
    complete.write_bytes(b"complete")
    _write_manifest(complete, {table: 1 for table in backup.RELEASE_CRITICAL_TABLES})
    orphan = tmp_path / "unbound-bible-20260810T120001Z.dump"
    orphan.write_bytes(b"orphan")
    symlinked = tmp_path / "unbound-bible-20260810T120002Z.dump"
    symlinked.write_bytes(b"symlinked")
    symlinked.with_suffix(".dump.manifest.json").symlink_to(
        complete.with_suffix(".dump.manifest.json")
    )
    now = time.time_ns()
    os.utime(complete, ns=(now - 3, now - 3))
    os.utime(orphan, ns=(now - 2, now - 2))
    os.utime(symlinked, ns=(now - 1, now - 1))

    assert backup.latest_backup(tmp_path) == complete


def test_latest_complete_but_tampered_pair_fails_without_falling_back(tmp_path, monkeypatch):
    counts = {table: 1 for table in backup.RELEASE_CRITICAL_TABLES}
    older = tmp_path / "unbound-bible-20260810T120000Z.dump"
    older.write_bytes(b"older")
    _write_manifest(older, counts)
    newer = tmp_path / "unbound-bible-20260810T120001Z.dump"
    newer.write_bytes(b"newer")
    _write_manifest(newer, counts, digest="0" * 64)
    now = time.time_ns()
    os.utime(older, ns=(now - 1, now - 1))
    os.utime(newer, ns=(now, now))
    calls = []
    monkeypatch.setattr(backup, "_create_disposable_database", lambda *_args: calls.append("create"))

    assert backup.latest_backup(tmp_path) == newer
    with pytest.raises(backup.BackupVerificationError, match="digest"):
        backup.verify_restore(DATABASE_URL, tmp_path)
    assert calls == []


def test_restore_rejects_symlink_fifo_and_oversized_manifest_without_opening_database(
    tmp_path, monkeypatch
):
    counts = {table: 1 for table in backup.RELEASE_CRITICAL_TABLES}
    calls = []
    monkeypatch.setattr(backup, "_create_disposable_database", lambda *_args: calls.append("create"))

    symlink_dump = tmp_path / "unbound-bible-20260810T120010Z.dump"
    symlink_dump.write_bytes(b"symlink")
    real_manifest = tmp_path / "real-manifest.json"
    _write_manifest(symlink_dump, counts).replace(real_manifest)
    symlink_dump.with_suffix(".dump.manifest.json").symlink_to(real_manifest)
    with pytest.raises(backup.BackupVerificationError, match="manifest"):
        backup.verify_restore(DATABASE_URL, tmp_path, dump_file=symlink_dump)

    fifo_dump = tmp_path / "unbound-bible-20260810T120011Z.dump"
    fifo_dump.write_bytes(b"fifo")
    os.mkfifo(fifo_dump.with_suffix(".dump.manifest.json"), 0o600)
    with pytest.raises(backup.BackupVerificationError, match="manifest"):
        backup.verify_restore(DATABASE_URL, tmp_path, dump_file=fifo_dump)

    large_dump = tmp_path / "unbound-bible-20260810T120012Z.dump"
    large_dump.write_bytes(b"large")
    large_manifest = large_dump.with_suffix(".dump.manifest.json")
    large_manifest.write_bytes(b"{" + b" " * (backup.MAX_MANIFEST_BYTES + 1) + b"}")
    large_manifest.chmod(0o600)
    with pytest.raises(backup.BackupVerificationError, match="too large"):
        backup.verify_restore(DATABASE_URL, tmp_path, dump_file=large_dump)

    assert calls == []


def test_primary_restore_failure_is_preserved_when_guarded_cleanup_also_fails(
    tmp_path, monkeypatch
):
    dump = tmp_path / "unbound-bible-20260810T120000Z.dump"
    dump.write_bytes(b"PGDMP-test")
    _write_manifest(dump, {table: 1 for table in backup.RELEASE_CRITICAL_TABLES})
    name = "unbound_restore_check_" + "2" * 24
    primary = backup.BackupVerificationError("health check failed")

    monkeypatch.setattr(backup, "disposable_database_name", lambda: name)
    monkeypatch.setattr(backup, "_create_disposable_database", lambda *_args: None)
    monkeypatch.setattr(backup, "_drop_disposable_database", lambda *_args: (_ for _ in ()).throw(backup.BackupOperationError("cleanup failed")))
    monkeypatch.setattr(backup, "_run_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(backup, "_verify_restored_application", lambda _url: (_ for _ in ()).throw(primary))

    with pytest.raises(backup.BackupVerificationError, match="health check failed") as caught:
        backup.verify_restore(DATABASE_URL, tmp_path, dump_file=dump)

    assert caught.value is primary
    assert any("cleanup also failed" in note.lower() for note in caught.value.__notes__)
    assert "super-secret" not in " ".join(caught.value.__notes__)


def test_cli_reports_safe_primary_and_cleanup_failures_without_credentials(monkeypatch, capsys):
    primary = backup.BackupVerificationError("restored application health check failed")
    primary.add_note(
        "CRITICAL: disposable restore database cleanup also failed; deployment remains blocked"
    )
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("BACKUP_DIR", "/secure/backups")
    monkeypatch.setattr(backup, "verify_restore", lambda *_args: (_ for _ in ()).throw(primary))

    assert backup.main(["restore-check"]) == 1
    output = capsys.readouterr().err
    assert "restored application health check failed" in output
    assert "cleanup also failed" in output
    assert "deployment remains blocked" in output
    assert "super-secret" not in output


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
