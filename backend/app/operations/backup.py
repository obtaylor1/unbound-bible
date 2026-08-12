"""Create PostgreSQL backups and prove they can be restored safely.

The public entry points deliberately accept explicit database and backup
locations.  Commands are always executed as argument arrays and errors are
re-raised without command arguments so database credentials cannot appear in
operator output.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import URL, make_url


BACKUP_PREFIX = "unbound-bible-"
MANIFEST_SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 64 * 1024
DISPOSABLE_DATABASE_PREFIX = "unbound_restore_check_"
_DISPOSABLE_DATABASE_PATTERN = re.compile(r"^unbound_restore_check_[0-9a-f]{24}$")
RELEASE_CRITICAL_TABLES = (
    "biblical_texts",
    "users",
    "study_sessions",
    "user_notes",
    "shared_studies",
    "notifications",
    "community_posts",
    "community_comments",
)


class BackupError(RuntimeError):
    """Base class for safe operator-facing backup errors."""


class BackupPolicyError(BackupError):
    """Raised when an operation would violate the backup policy."""


class BackupOperationError(BackupError):
    """Raised when an external backup command fails."""


class BackupVerificationError(BackupError):
    """Raised when an isolated restoration cannot be verified."""


@dataclass(frozen=True)
class BackupSettings:
    database_url: str
    backup_dir: Path


@dataclass(frozen=True)
class CountComparison:
    ok: bool
    mismatches: dict[str, tuple[int | None, int | None]]


@dataclass(frozen=True)
class RestoreVerification:
    ok: bool
    database_name: str
    counts: CountComparison
    health: Mapping[str, Mapping[str, object]]


def settings_from_environment(environment: Mapping[str, str] | None = None) -> BackupSettings:
    values = os.environ if environment is None else environment
    database_url = values.get("DATABASE_URL", "").strip()
    backup_dir = values.get("BACKUP_DIR", "").strip()
    if not database_url:
        raise BackupPolicyError("DATABASE_URL must be set explicitly")
    if not backup_dir:
        raise BackupPolicyError("BACKUP_DIR must be set explicitly")
    _normalized_postgres_url(database_url)
    return BackupSettings(database_url=database_url, backup_dir=Path(backup_dir))


def backup_filename(moment: datetime) -> str:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("Backup timestamp must be timezone-aware")
    utc = moment.astimezone(timezone.utc)
    return f"{BACKUP_PREFIX}{utc:%Y%m%dT%H%M%SZ}.dump"


def _normalized_postgres_url(database_url: str) -> str:
    try:
        parsed = make_url(database_url)
    except Exception:
        raise BackupPolicyError("DATABASE_URL must be a valid PostgreSQL URL") from None
    if parsed.get_backend_name() != "postgresql" or not parsed.database:
        raise BackupPolicyError("DATABASE_URL must name an explicit PostgreSQL database")
    normalized = parsed.set(drivername="postgresql")
    return normalized.render_as_string(hide_password=False)


def _database_name(database_url: str) -> str:
    parsed = make_url(_normalized_postgres_url(database_url))
    if not parsed.database:
        raise BackupPolicyError("DATABASE_URL must name an explicit PostgreSQL database")
    return parsed.database


def _database_url_with_name(database_url: str, database_name: str) -> str:
    parsed = make_url(_normalized_postgres_url(database_url))
    return parsed.set(database=database_name).render_as_string(hide_password=False)


def _maintenance_database_url(database_url: str) -> str:
    return _database_url_with_name(database_url, "postgres")


def _postgres_cli_connection(database_url: str) -> tuple[str, dict[str, str]]:
    """Return a password-free connection URI and an isolated client environment."""
    parsed = make_url(_normalized_postgres_url(database_url))
    environment = dict(os.environ)
    if parsed.password is None:
        environment.pop("PGPASSWORD", None)
    else:
        environment["PGPASSWORD"] = parsed.password
    safe_url = URL.create(
        drivername=parsed.drivername,
        username=parsed.username,
        host=parsed.host,
        port=parsed.port,
        database=parsed.database,
        query=parsed.query,
    ).render_as_string(hide_password=False)
    return safe_url, environment


def _run_command(
    argv: Sequence[str], *, env: Mapping[str, str] | None = None, cwd: Path | None = None
) -> None:
    arguments = list(argv)
    if not arguments:
        raise BackupPolicyError("External command cannot be empty")
    try:
        subprocess.run(
            arguments,
            check=True,
            shell=False,
            env=None if env is None else dict(env),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        raise BackupOperationError(f"{Path(arguments[0]).name} failed") from None


def _fsync_file(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create_backup(
    database_url: str,
    backup_dir: str | Path,
    *,
    now: datetime | None = None,
) -> Path:
    postgres_url = _normalized_postgres_url(database_url)
    command_url, command_environment = _postgres_cli_connection(postgres_url)
    directory = Path(backup_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    timestamp = now or datetime.now(timezone.utc)
    target = directory / backup_filename(timestamp)
    manifest_target = _manifest_path(target)
    if target.exists() or manifest_target.exists():
        raise BackupPolicyError(f"Backup already exists: {target.name}")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.stem}-", suffix=".tmp", dir=directory
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.chmod(0o600)
    manifest_temporary: Path | None = None
    dump_published = False
    try:
        with _release_snapshot(postgres_url) as (snapshot_id, release_counts):
            _run_command(
                [
                    "pg_dump",
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    "--snapshot",
                    snapshot_id,
                    "--file",
                    str(temporary),
                    "--dbname",
                    command_url,
                ],
                env=command_environment,
            )
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise BackupOperationError("pg_dump produced an empty backup")
        temporary.chmod(0o600)
        _fsync_file(temporary)
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "created_at": timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snapshot": {"strategy": "pg_export_snapshot"},
            "dump": {
                "filename": target.name,
                "format": "postgresql-custom",
                "sha256": _sha256_file(temporary),
            },
            "release_critical_counts": release_counts,
        }
        manifest_temporary = _write_temporary_manifest(directory, target, manifest)
        os.replace(temporary, target)
        dump_published = True
        _fsync_directory(directory)
        os.replace(manifest_temporary, manifest_target)
        _fsync_directory(directory)
        return target
    except Exception:
        temporary.unlink(missing_ok=True)
        if manifest_temporary is not None:
            manifest_temporary.unlink(missing_ok=True)
        if dump_published:
            target.unlink(missing_ok=True)
        manifest_target.unlink(missing_ok=True)
        raise


def _manifest_path(dump_file: Path) -> Path:
    return dump_file.with_suffix(dump_file.suffix + ".manifest.json")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_temporary_manifest(
    directory: Path, dump_target: Path, manifest: Mapping[str, object]
) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{dump_target.stem}-manifest-", suffix=".tmp", dir=directory
    )
    path = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
        return path
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        path.unlink(missing_ok=True)
        raise


def compare_release_counts(
    *, before: Mapping[str, int], after: Mapping[str, int]
) -> CountComparison:
    mismatches: dict[str, tuple[int | None, int | None]] = {}
    for table in sorted(set(before) | set(after)):
        source_count = before.get(table)
        restored_count = after.get(table)
        if source_count != restored_count:
            mismatches[table] = (source_count, restored_count)
    return CountComparison(ok=not mismatches, mismatches=mismatches)


def disposable_database_name() -> str:
    return f"{DISPOSABLE_DATABASE_PREFIX}{secrets.token_hex(12)}"


def assert_disposable_database_name(database_name: str) -> None:
    if not _DISPOSABLE_DATABASE_PATTERN.fullmatch(database_name):
        raise BackupPolicyError("Refusing to operate on a database without a valid disposable name")


def _connect_maintenance(database_url: str):
    try:
        return psycopg2.connect(_maintenance_database_url(database_url))
    except Exception:
        raise BackupOperationError("Could not connect to the PostgreSQL maintenance database") from None


def _create_disposable_database(database_url: str, database_name: str) -> None:
    assert_disposable_database_name(database_name)
    if database_name == _database_name(database_url):
        raise BackupPolicyError("Disposable database must not be the source database")
    connection = _connect_maintenance(database_url)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    except Exception:
        raise BackupOperationError("Could not create the disposable restore database") from None
    finally:
        connection.close()


def _drop_disposable_database(database_url: str, database_name: str) -> None:
    assert_disposable_database_name(database_name)
    if database_name == _database_name(database_url):
        raise BackupPolicyError("Refusing to drop the source database")
    connection = _connect_maintenance(database_url)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (database_name,),
            )
            cursor.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name))
            )
    except Exception:
        raise BackupOperationError("Could not remove the disposable restore database") from None
    finally:
        connection.close()


def _read_release_counts_from_cursor(cursor) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in RELEASE_CRITICAL_TABLES:
        cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
        row = cursor.fetchone()
        if row is None:
            raise BackupVerificationError(f"Could not count release-critical table {table}")
        counts[table] = int(row[0])
    return counts


def _read_release_counts(database_url: str) -> dict[str, int]:
    try:
        connection = psycopg2.connect(_normalized_postgres_url(database_url))
    except Exception:
        raise BackupVerificationError("Could not connect while reading release-critical counts") from None
    try:
        with connection.cursor() as cursor:
            return _read_release_counts_from_cursor(cursor)
    except BackupError:
        raise
    except Exception:
        raise BackupVerificationError("Could not read release-critical table counts") from None
    finally:
        connection.close()


@contextmanager
def _release_snapshot(database_url: str):
    try:
        connection = psycopg2.connect(_normalized_postgres_url(database_url))
    except Exception:
        raise BackupOperationError("Could not connect to export the backup snapshot") from None
    try:
        try:
            connection.set_session(
                isolation_level="REPEATABLE READ", readonly=True, autocommit=False
            )
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_export_snapshot()")
                row = cursor.fetchone()
                if row is None or not isinstance(row[0], str) or not row[0]:
                    raise BackupVerificationError("PostgreSQL did not export a backup snapshot")
                snapshot_id = row[0]
                counts = _read_release_counts_from_cursor(cursor)
        except BackupError:
            raise
        except Exception:
            raise BackupVerificationError(
                "Could not capture release-critical counts for the backup snapshot"
            ) from None
        yield snapshot_id, counts
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def _available_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _read_health(url: str) -> Mapping[str, object]:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status != 200:
                raise BackupVerificationError("Restored application health endpoint was not successful")
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        raise BackupVerificationError("Restored application health endpoint was not reachable") from None
    if not isinstance(payload, dict) or payload.get("status") != "healthy":
        raise BackupVerificationError("Restored application reported an unhealthy status")
    return payload


def _verify_restored_application(database_url: str) -> dict[str, Mapping[str, object]]:
    port = _available_local_port()
    environment = dict(os.environ)
    environment["DATABASE_URL"] = database_url
    backend_root = Path(__file__).resolve().parents[2]
    process = None
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.application:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=backend_root,
            env=environment,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        base = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        primary: Mapping[str, object] | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise BackupVerificationError("Restored application stopped before becoming healthy")
            try:
                primary = _read_health(f"{base}/api/v1/health")
                break
            except BackupVerificationError:
                time.sleep(0.25)
        if primary is None:
            raise BackupVerificationError("Restored application did not become healthy")
        providers = _read_health(f"{base}/api/v1/health/providers")
        return {
            "/api/v1/health": primary,
            "/api/v1/health/providers": providers,
        }
    except BackupError:
        raise
    except Exception:
        raise BackupVerificationError("Could not start the restored application") from None
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def latest_backup(backup_dir: str | Path) -> Path:
    directory = Path(backup_dir)

    def is_complete_pair(path: Path) -> bool:
        try:
            return stat.S_ISREG(path.lstat().st_mode) and stat.S_ISREG(
                _manifest_path(path).lstat().st_mode
            )
        except OSError:
            return False

    candidates = sorted(
        (path for path in directory.glob(f"{BACKUP_PREFIX}*.dump") if is_complete_pair(path)),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    if not candidates:
        raise BackupPolicyError("No backup dump exists in BACKUP_DIR")
    return candidates[0]


def _validated_dump_path(backup_dir: Path, dump_file: str | Path | None) -> Path:
    candidate = latest_backup(backup_dir) if dump_file is None else Path(dump_file)
    try:
        candidate = candidate.resolve(strict=True)
        directory = backup_dir.resolve(strict=True)
    except OSError:
        raise BackupPolicyError("Backup dump does not exist") from None
    if candidate.parent != directory or candidate.suffix != ".dump" or not candidate.is_file():
        raise BackupPolicyError("Backup dump must be a .dump file directly inside BACKUP_DIR")
    if candidate.stat().st_size == 0:
        raise BackupPolicyError("Backup dump is empty")
    return candidate


def _read_secure_manifest(manifest_path: Path) -> bytes:
    try:
        if not stat.S_ISREG(manifest_path.lstat().st_mode):
            raise BackupVerificationError("Backup manifest must be a regular non-symlink file")
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(manifest_path, flags)
    except BackupError:
        raise
    except OSError:
        raise BackupVerificationError("Backup manifest is missing or unsafe") from None

    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise BackupVerificationError("Backup manifest must be a regular file")
        if metadata.st_mode & 0o077:
            raise BackupPolicyError("Backup manifest permissions must be 0600")
        if metadata.st_size > MAX_MANIFEST_BYTES:
            raise BackupVerificationError("Backup manifest is too large")
        chunks: list[bytes] = []
        remaining = MAX_MANIFEST_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 8192))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > MAX_MANIFEST_BYTES:
            raise BackupVerificationError("Backup manifest is too large")
        return payload
    except BackupError:
        raise
    except OSError:
        raise BackupVerificationError("Backup manifest could not be read safely") from None
    finally:
        os.close(descriptor)


def _load_verified_manifest(dump_file: Path) -> dict[str, int]:
    manifest_path = _manifest_path(dump_file)
    try:
        manifest = json.loads(_read_secure_manifest(manifest_path).decode("utf-8"))
    except BackupError:
        raise
    except (OSError, ValueError, TypeError):
        raise BackupVerificationError("Backup manifest is missing or invalid") from None

    if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise BackupVerificationError("Backup manifest schema version is unsupported")
    created_at = manifest.get("created_at")
    if not isinstance(created_at, str):
        raise BackupVerificationError("Backup manifest timestamp is invalid")
    try:
        datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise BackupVerificationError("Backup manifest timestamp is invalid") from None
    snapshot = manifest.get("snapshot")
    if snapshot != {"strategy": "pg_export_snapshot"}:
        raise BackupVerificationError("Backup manifest does not declare an exported snapshot")
    dump = manifest.get("dump")
    if not isinstance(dump, dict):
        raise BackupVerificationError("Backup manifest dump metadata is invalid")
    if dump.get("filename") != dump_file.name or dump.get("format") != "postgresql-custom":
        raise BackupVerificationError("Backup manifest does not identify this custom-format dump")
    expected_digest = dump.get("sha256")
    if not isinstance(expected_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise BackupVerificationError("Backup manifest SHA-256 digest is invalid")
    if not hmac.compare_digest(expected_digest, _sha256_file(dump_file)):
        raise BackupVerificationError("Backup dump digest does not match its manifest")

    counts = manifest.get("release_critical_counts")
    if not isinstance(counts, dict) or set(counts) != set(RELEASE_CRITICAL_TABLES):
        raise BackupVerificationError("Backup manifest release-critical counts are incomplete")
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise BackupVerificationError("Backup manifest release-critical counts are invalid")
    return {table: counts[table] for table in RELEASE_CRITICAL_TABLES}


def verify_restore(
    database_url: str,
    backup_dir: str | Path,
    *,
    dump_file: str | Path | None = None,
) -> RestoreVerification:
    source_url = _normalized_postgres_url(database_url)
    directory = Path(backup_dir)
    dump = _validated_dump_path(directory, dump_file)
    recorded_counts = _load_verified_manifest(dump)
    database_name = disposable_database_name()
    assert_disposable_database_name(database_name)
    if database_name == _database_name(source_url):
        raise BackupPolicyError("Disposable database must not be the source database")
    restored_url = _database_url_with_name(source_url, database_name)
    restore_command_url, restore_environment = _postgres_cli_connection(restored_url)
    cleanup_required = False
    primary_error: BaseException | None = None
    verification: RestoreVerification | None = None
    try:
        # A CREATE DATABASE response can be interrupted after PostgreSQL has
        # committed it, so cleanup must be attempted even when creation raises.
        cleanup_required = True
        _create_disposable_database(source_url, database_name)
        _run_command(
            [
                "pg_restore",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                restore_command_url,
                str(dump),
            ],
            env=restore_environment,
        )
        migration_environment = dict(os.environ)
        migration_environment["DATABASE_URL"] = restored_url
        _run_command(
            ["alembic", "-c", "alembic.ini", "upgrade", "head"],
            env=migration_environment,
            cwd=Path(__file__).resolve().parents[2],
        )
        health = _verify_restored_application(restored_url)
        restored_counts = _read_release_counts(restored_url)
        comparison = compare_release_counts(before=recorded_counts, after=restored_counts)
        if not comparison.ok:
            names = ", ".join(sorted(comparison.mismatches))
            raise BackupVerificationError(f"Release-critical row counts differ: {names}")
        verification = RestoreVerification(
            ok=True,
            database_name=database_name,
            counts=comparison,
            health=health,
        )
    except BaseException as exc:
        primary_error = exc

    cleanup_error: BackupError | None = None
    if cleanup_required:
        try:
            _drop_disposable_database(source_url, database_name)
        except BackupError as exc:
            cleanup_error = exc
        except BaseException:
            cleanup_error = BackupOperationError("Disposable restore database cleanup failed")

    if primary_error is not None:
        if cleanup_error is not None:
            primary_error.add_note(
                "CRITICAL: disposable restore database cleanup also failed; deployment remains blocked"
            )
        raise primary_error
    if cleanup_error is not None:
        raise cleanup_error
    if verification is None:
        raise BackupVerificationError("Restore verification did not complete")
    return verification


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe PostgreSQL backup operations")
    parser.add_argument("operation", choices=("backup", "restore-check"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        settings = settings_from_environment()
        if arguments.operation == "backup":
            output = create_backup(settings.database_url, settings.backup_dir)
            print(f"Backup created: {output}")
        else:
            result = verify_restore(settings.database_url, settings.backup_dir)
            print(f"Restore verification passed for {result.database_name}")
        return 0
    except BackupError as exc:
        print(f"{arguments.operation} failed: {exc}", file=sys.stderr)
        for note in getattr(exc, "__notes__", ()):
            print(note, file=sys.stderr)
        return 1
    except Exception:
        print(f"{arguments.operation} failed; see protected service logs", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
