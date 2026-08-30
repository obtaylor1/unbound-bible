"""Strict local registry and immutable artifact-lock verification.

This module is an operator-side trust boundary, not protection against a hostile
administrator with write access to the artifact directory.  It prevents common
path, symlink, checksum, host, and time-of-check/time-of-use mistakes while a
reviewed local artifact is being registered.  It never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType
from typing import Any, Mapping
import unicodedata
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit
from uuid import uuid4


REGISTRY_VERSION = 1
LOCK_VERSION = 1
SUPPORTED_FAMILY_IDS = frozenset({
    'world-messianic-bible',
    'murdock-peshitta-1852',
    'kjv-1611-fallback',
    'rh-charles-jubilees-1902',
})
SUPPORTED_ADAPTER_IDS = frozenset({
    'wmb_vpl', 'murdock_sword', 'gutenberg_kjv_apocrypha', 'charles_jubilees',
})
_IDENTIFIER = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
_FILENAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z')
_SHA256 = re.compile(r'[0-9a-f]{64}\Z')
_HOST = re.compile(r'[a-z0-9]+(?:[.-][a-z0-9]+)*\Z')
_BAD_PERCENT = re.compile(r'%(?![0-9A-Fa-f]{2})')
_SECRET_WORDS = (
    'token', 'secret', 'password', 'passwd', 'credential', 'signature',
    'authorization', 'bearer', 'api-key', 'apikey', 'access-key', 'private-key',
)
_SECRET_EXACT = frozenset({'sig', 'key', 'auth'})
_CHUNK_SIZE = 1024 * 1024
_MAX_JSON_BYTES = 2 * 1024 * 1024


class RegistryError(ValueError):
    """A registry or lock document is malformed or unsafe."""


class SourceArtifactError(ValueError):
    """A local artifact does not match its reviewed lock and definition."""


class LockWriteError(OSError):
    """An atomic lock update failed, possibly retaining a recovery backup."""

    def __init__(
        self,
        primary_error: BaseException,
        *,
        recovery_backup: Path | None = None,
        recovery_path: Path | None = None,
        cleanup_errors: tuple[BaseException, ...] = (),
    ) -> None:
        super().__init__('artifact lock transaction failed')
        self.primary_error = primary_error
        self.recovery_backup = recovery_backup
        self.recovery_path = recovery_path
        self.cleanup_errors = cleanup_errors


def _normalized(value: object, name: str, *, maximum: int) -> str:
    if type(value) is not str:
        raise ValueError(f'{name} must be a string.')
    if not value or value != value.strip() or len(value) > maximum:
        raise ValueError(f'{name} must be nonblank, trimmed, and at most {maximum} characters.')
    if (
        unicodedata.normalize('NFC', value) != value
        or any(unicodedata.category(char).startswith('C') for char in value)
    ):
        raise ValueError(
            f'{name} must be NFC-normalized and contain no unsafe control or format characters.'
        )
    return value


def _identifier(value: object, name: str) -> str:
    result = _normalized(value, name, maximum=100)
    if _IDENTIFIER.fullmatch(result) is None:
        raise ValueError(f'{name} must be a normalized lowercase identifier.')
    return result


def _filename(value: object) -> str:
    result = _normalized(value, 'artifact filename', maximum=128)
    if (
        _FILENAME.fullmatch(result) is None
        or result.startswith('.')
        or '..' in result
        or '%' in result
        or Path(result).name != result
    ):
        raise ValueError('artifact filename must be a safe relative basename.')
    return result


def _normalized_host(value: object) -> str:
    result = _normalized(value, 'source host', maximum=253).casefold().rstrip('.')
    try:
        result = result.encode('idna').decode('ascii')
    except UnicodeError as error:
        raise ValueError('source host is invalid.') from error
    if _HOST.fullmatch(result) is None or '..' in result:
        raise ValueError('source host is invalid.')
    return result


def _decoded_url_is_safe(value: str) -> str:
    decoded = value
    for _ in range(len(value) + 1):
        if _BAD_PERCENT.search(decoded):
            raise ValueError('URL contains invalid percent encoding.')
        if (
            any(unicodedata.category(char).startswith('C') for char in decoded)
            or '\\' in decoded
            or any(segment in {'.', '..'} for segment in decoded.split('/'))
        ):
            raise ValueError('URL contains encoded control or traversal content.')
        next_value = unquote(decoded)
        if next_value == decoded:
            return decoded
        decoded = next_value
    raise ValueError('URL percent encoding is excessively nested.')


def validate_https_url(
    value: object, *, allowed_hosts: tuple[str, ...] | None = None,
) -> str:
    """Return a canonical commit-safe HTTPS URL with a lowercase hostname."""
    result = _normalized(value, 'URL', maximum=2048)
    fully_decoded = _decoded_url_is_safe(result)
    try:
        parsed = urlsplit(result)
        port = parsed.port
    except ValueError as error:
        raise ValueError('URL is invalid.') from error
    if parsed.scheme != 'https' or not parsed.hostname or not parsed.netloc:
        raise ValueError('URL must use HTTPS and include a host.')
    if parsed.username is not None or parsed.password is not None:
        raise ValueError('URL credentials are forbidden.')
    if parsed.fragment:
        raise ValueError('URL fragments are forbidden.')
    if port is not None:
        raise ValueError('URL ports are not allowed in reviewed source URLs.')
    host = _normalized_host(parsed.hostname)
    if allowed_hosts is not None and host not in allowed_hosts:
        raise ValueError(f'URL host {host} is not an approved host.')
    queries = (parsed.query, urlsplit(fully_decoded).query)
    for query in queries:
        for key, _ in parse_qsl(query, keep_blank_values=True, strict_parsing=False):
            normalized_key = re.sub(r'[^a-z0-9]+', '-', key.casefold()).strip('-')
            if (
                normalized_key in _SECRET_EXACT
                or any(word in normalized_key for word in _SECRET_WORDS)
            ):
                raise ValueError('URL query parameters must not contain secrets.')
    return urlunsplit(('https', host, parsed.path or '/', parsed.query, ''))


def _unique_normalized(values: object, name: str, *, maximum: int) -> tuple[str, ...]:
    if type(values) not in (list, tuple) or not values or len(values) > maximum:
        raise ValueError(f'{name} must be a nonempty list with at most {maximum} entries.')
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _identifier(value, name[:-1] if name.endswith('s') else name)
        identity = unicodedata.normalize('NFC', item).casefold()
        if identity in seen:
            raise ValueError(f'{name} must be unique after normalization.')
        seen.add(identity)
        result.append(item)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    family_id: str
    landing_url: str
    artifact_url: str | None
    artifact_filename: str
    adapter_id: str
    rights_jurisdiction: str
    allowed_source_hosts: tuple[str, ...]
    max_artifact_bytes: int
    expected_work_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        family_id = _identifier(self.family_id, 'family_id')
        if family_id not in SUPPORTED_FAMILY_IDS:
            raise ValueError(f'unsupported source family {family_id}.')
        if self.adapter_id not in SUPPORTED_ADAPTER_IDS:
            raise ValueError('unsupported adapter ID.')
        hosts_value = self.allowed_source_hosts
        if type(hosts_value) not in (list, tuple) or not hosts_value or len(hosts_value) > 8:
            raise ValueError('allowed source hosts must be a nonempty bounded list.')
        hosts = tuple(_normalized_host(host) for host in hosts_value)
        if len(set(hosts)) != len(hosts):
            raise ValueError('allowed source hosts must be unique after normalization.')
        if type(self.max_artifact_bytes) is not int or not 1 <= self.max_artifact_bytes <= 2**30:
            raise ValueError('max_artifact_bytes must be an integer from 1 through 1073741824.')
        object.__setattr__(self, 'family_id', family_id)
        object.__setattr__(self, 'artifact_filename', _filename(self.artifact_filename))
        object.__setattr__(self, 'adapter_id', _normalized(self.adapter_id, 'adapter_id', maximum=64))
        object.__setattr__(self, 'rights_jurisdiction', _normalized(
            self.rights_jurisdiction, 'rights_jurisdiction', maximum=500,
        ))
        object.__setattr__(self, 'allowed_source_hosts', hosts)
        object.__setattr__(self, 'expected_work_ids', _unique_normalized(
            self.expected_work_ids, 'expected work IDs', maximum=100,
        ))
        object.__setattr__(self, 'landing_url', validate_https_url(
            self.landing_url, allowed_hosts=hosts,
        ))
        if self.artifact_url is not None:
            object.__setattr__(self, 'artifact_url', validate_https_url(
                self.artifact_url, allowed_hosts=hosts,
            ))


# These fixed byte limits and source identities are reviewed policy: 100 MiB for
# the two archive families and 50 MiB for the historical plain-text families.
# The JSON registry is auditable evidence, not a mechanism for changing policy.
APPROVED_SOURCE_DEFINITIONS: Mapping[str, SourceDefinition] = MappingProxyType({
    'world-messianic-bible': SourceDefinition(
        family_id='world-messianic-bible',
        landing_url='https://ebible.org/find/show.php?id=engwmb',
        artifact_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        artifact_filename='engwmb_vpl.zip',
        adapter_id='wmb_vpl',
        rights_jurisdiction=(
            'Public-domain dedication; World Messianic Bible naming condition applies'
        ),
        allowed_source_hosts=('ebible.org',),
        max_artifact_bytes=104_857_600,
        expected_work_ids=(
            'genesis', 'exodus', 'leviticus', 'numbers', 'deuteronomy', 'joshua',
            'judges', 'ruth', '1-samuel', '2-samuel', '1-kings', '2-kings',
            '1-chronicles', '2-chronicles', 'ezra', 'nehemiah', 'esther', 'job',
            'psalms', 'proverbs', 'ecclesiastes', 'song-of-solomon', 'isaiah',
            'jeremiah', 'lamentations', 'ezekiel', 'daniel', 'hosea', 'joel',
            'amos', 'obadiah', 'jonah', 'micah', 'nahum', 'habakkuk', 'zephaniah',
            'haggai', 'zechariah', 'malachi',
        ),
    ),
    'murdock-peshitta-1852': SourceDefinition(
        family_id='murdock-peshitta-1852',
        landing_url='https://crosswire.org/sword/modules/ModInfo.jsp?modName=Murdock',
        artifact_url=(
            'https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/Murdock.zip'
        ),
        artifact_filename='murdock-source.zip',
        adapter_id='murdock_sword',
        rights_jurisdiction='Public domain; historical edition cross-check required',
        allowed_source_hosts=('crosswire.org', 'www.crosswire.org'),
        max_artifact_bytes=104_857_600,
        expected_work_ids=(
            'matthew', 'mark', 'luke', 'john', 'acts', 'romans', '1-corinthians',
            '2-corinthians', 'galatians', 'ephesians', 'philippians', 'colossians',
            '1-thessalonians', '2-thessalonians', '1-timothy', '2-timothy', 'titus',
            'philemon', 'hebrews', 'james', '1-peter', '2-peter', '1-john',
            '2-john', '3-john', 'jude', 'revelation',
        ),
    ),
    'kjv-1611-fallback': SourceDefinition(
        family_id='kjv-1611-fallback',
        landing_url='https://www.gutenberg.org/ebooks/124',
        artifact_url='https://www.gutenberg.org/cache/epub/124/pg124.txt',
        artifact_filename='project-gutenberg-124.txt',
        adapter_id='gutenberg_kjv_apocrypha',
        rights_jurisdiction='Public domain in the USA',
        allowed_source_hosts=('www.gutenberg.org', 'gutenberg.org'),
        max_artifact_bytes=2_097_152,
        expected_work_ids=(
            'baruch', 'letter-of-jeremiah', 'prayer-of-azariah', 'susanna',
            'bel-and-the-dragon', 'prayer-of-manasseh',
        ),
    ),
    'rh-charles-jubilees-1902': SourceDefinition(
        family_id='rh-charles-jubilees-1902',
        landing_url=(
            'https://www.globalgreyebooks.com/'
            'online-ebooks/r-h-charles_book-of-jubilees_complete-text.html'
        ),
        artifact_url=(
            'https://www.globalgreyebooks.com/'
            'online-ebooks/r-h-charles_book-of-jubilees_complete-text.html'
        ),
        artifact_filename='rh-charles-jubilees-1917-authorized-reprint.html',
        adapter_id='charles_jubilees',
        rights_jurisdiction=(
            'Public domain in the USA; authorized 1917 reprint of the 1902 translation'
        ),
        allowed_source_hosts=('www.globalgreyebooks.com', 'globalgreyebooks.com'),
        max_artifact_bytes=2_097_152,
        expected_work_ids=('jubilees',),
    ),
})


def _utc_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif type(value) is str and len(value) <= 40:
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError as error:
            raise ValueError('retrieved_at must be an aware UTC datetime.') from error
    else:
        raise ValueError('retrieved_at must be an aware UTC datetime.')
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError('retrieved_at must be an aware UTC datetime.')
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ArtifactLockRecord:
    family_id: str
    artifact_path: str
    source_url: str
    landing_url: str
    retrieved_at: datetime | str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        family_id = _identifier(self.family_id, 'family_id')
        if family_id not in SUPPORTED_FAMILY_IDS:
            raise ValueError('unsupported source family.')
        path = _normalized(self.artifact_path, 'artifact_path', maximum=256)
        if (
            Path(path).is_absolute() or '\\' in path or '%' in path
            or any(part in {'', '.', '..'} for part in path.split('/'))
            or any(ord(char) < 32 for char in path)
        ):
            raise ValueError('artifact_path must be a safe relative path.')
        if type(self.size_bytes) is not int or self.size_bytes < 0 or self.size_bytes > 2**40:
            raise ValueError('size_bytes must be a bounded nonnegative integer.')
        if type(self.sha256) is not str or _SHA256.fullmatch(self.sha256) is None:
            raise ValueError('sha256 must be lowercase 64-character hexadecimal.')
        object.__setattr__(self, 'family_id', family_id)
        object.__setattr__(self, 'artifact_path', path)
        object.__setattr__(self, 'source_url', validate_https_url(self.source_url))
        object.__setattr__(self, 'landing_url', validate_https_url(self.landing_url))
        object.__setattr__(self, 'retrieved_at', _utc_datetime(self.retrieved_at))


@dataclass(frozen=True, slots=True)
class SourceRegistry:
    version: int
    families: Mapping[str, SourceDefinition]

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version != REGISTRY_VERSION:
            raise ValueError('registry version must be 1.')
        if type(self.families) is not dict or set(self.families) != SUPPORTED_FAMILY_IDS:
            raise ValueError('registry must define exactly the four supported source families.')
        for key, definition in self.families.items():
            if type(key) is not str or key != definition.family_id:
                raise ValueError('registry family key must match family_id.')
        all_works = [work for definition in self.families.values() for work in definition.expected_work_ids]
        if len(all_works) != len(set(all_works)):
            raise ValueError('expected work IDs must not overlap across source families.')
        if self.families != APPROVED_SOURCE_DEFINITIONS:
            raise ValueError('registry definitions must exactly match the approved source contract.')
        object.__setattr__(self, 'families', MappingProxyType(dict(self.families)))


@dataclass(frozen=True, slots=True)
class ArtifactLock:
    version: int
    artifacts: Mapping[str, ArtifactLockRecord]

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version != LOCK_VERSION:
            raise ValueError('artifact lock version must be 1.')
        if type(self.artifacts) is not dict or len(self.artifacts) > len(SUPPORTED_FAMILY_IDS):
            raise ValueError('artifacts must be a bounded mapping.')
        for key, record in self.artifacts.items():
            if key not in SUPPORTED_FAMILY_IDS or key != record.family_id:
                raise ValueError('artifact key must match a supported family_id.')
        object.__setattr__(self, 'artifacts', MappingProxyType(dict(self.artifacts)))


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    normalized: set[str] = set()
    for key, value in pairs:
        identity = unicodedata.normalize('NFC', key).casefold()
        if identity in normalized:
            raise RegistryError(f'duplicate JSON member: {key}')
        normalized.add(identity)
        result[key] = value
    return result


def _load_json(path: Path) -> Any:
    try:
        if path.stat().st_size > _MAX_JSON_BYTES:
            raise RegistryError('JSON document is too large.')
        return json.loads(
            path.read_text(encoding='utf-8'), object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(RegistryError(
                f'non-finite JSON value is forbidden: {value}'
            )),
        )
    except RegistryError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RegistryError('unable to load strict JSON document.') from error


def _fields(value: object, expected: set[str], context: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise RegistryError(f'{context} must be an object.')
    extras = set(value) - expected
    missing = expected - set(value)
    if extras:
        raise RegistryError(f'{context} has an extra field: {sorted(extras)[0]}.')
    if missing:
        raise RegistryError(f'{context} is missing field: {sorted(missing)[0]}.')
    return value


def load_source_registry(path: Path) -> SourceRegistry:
    payload = _fields(_load_json(path), {'version', 'families'}, 'registry')
    families_payload = payload['families']
    if type(families_payload) is not dict:
        raise RegistryError('families must be an object.')
    definitions: dict[str, SourceDefinition] = {}
    expected = {
        'family_id', 'landing_url', 'artifact_url', 'artifact_filename', 'adapter_id',
        'rights_jurisdiction', 'allowed_source_hosts', 'max_artifact_bytes',
        'expected_work_ids',
    }
    try:
        for key, value in families_payload.items():
            if type(value) is not dict:
                raise RegistryError(f'family {key} must be an object.')
            fields = _fields(
                {**value, 'artifact_url': value.get('artifact_url')},
                expected,
                f'family {key}',
            )
            definition = SourceDefinition(**fields)
            if key != definition.family_id:
                raise ValueError('family mapping key must exactly match family_id.')
            definitions[key] = definition
        return SourceRegistry(version=payload['version'], families=definitions)
    except (TypeError, ValueError) as error:
        raise RegistryError(str(error)) from error


def load_artifact_lock(path: Path) -> ArtifactLock:
    payload = _fields(_load_json(path), {'version', 'artifacts'}, 'artifact lock')
    if type(payload['artifacts']) is not dict:
        raise RegistryError('artifacts must be an object.')
    expected = {
        'family_id', 'artifact_path', 'source_url', 'landing_url', 'retrieved_at',
        'size_bytes', 'sha256',
    }
    records: dict[str, ArtifactLockRecord] = {}
    try:
        for key, value in payload['artifacts'].items():
            fields = _fields(value, expected, f'artifact {key}')
            record = ArtifactLockRecord(**fields)
            if key != record.family_id:
                raise ValueError('artifact mapping key must exactly match family_id.')
            records[key] = record
        return ArtifactLock(version=payload['version'], artifacts=records)
    except (TypeError, ValueError) as error:
        raise RegistryError(str(error)) from error


def _datetime_text(value: datetime | str) -> str:
    parsed = _utc_datetime(value)
    return parsed.isoformat().replace('+00:00', 'Z')


def _lock_payload(lock: ArtifactLock) -> dict[str, Any]:
    return {
        'version': lock.version,
        'artifacts': {
            key: {
                'family_id': record.family_id,
                'artifact_path': record.artifact_path,
                'source_url': record.source_url,
                'landing_url': record.landing_url,
                'retrieved_at': _datetime_text(record.retrieved_at),
                'size_bytes': record.size_bytes,
                'sha256': record.sha256,
            }
            for key, record in sorted(lock.artifacts.items())
        },
    }


def lock_json_bytes(lock: ArtifactLock) -> bytes:
    # Reconstructing validates programmatic callers before any write.
    validated = ArtifactLock(lock.version, dict(lock.artifacts))
    return (json.dumps(
        _lock_payload(validated), ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False,
    ) + '\n').encode('utf-8')


def write_artifact_lock(path: Path, lock: ArtifactLock) -> None:
    """Atomically commit one lock while keeping the canonical old lock readable."""
    data = lock_json_bytes(lock)
    path.parent.mkdir(parents=True, exist_ok=True)
    had_old_lock = False
    try:
        existing = os.lstat(path)
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(existing.st_mode) or not stat.S_ISREG(existing.st_mode):
            raise RegistryError('existing artifact lock must be a nonsymlink regular file.')
        load_artifact_lock(path)
        had_old_lock = True

    transaction_id = f'{os.getpid()}-{uuid4().hex}'
    temporary = path.with_name(f'.{path.name}.tmp-{transaction_id}')
    backup = path.with_name(f'.{path.name}.bak-{transaction_id}')
    backup_created = False
    committed = False
    old_bytes: bytes | None = None
    owned_files: set[Path] = set()

    def cleanup(value: Path, errors: list[BaseException]) -> bool:
        if value not in owned_files:
            return True
        try:
            value.unlink()
        except FileNotFoundError:
            owned_files.discard(value)
            return True
        except BaseException as error:
            errors.append(error)
            return False
        owned_files.discard(value)
        return True

    def write_new_file(value: Path, payload: bytes) -> None:
        descriptor = os.open(
            value,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
            0o600,
        )
        owned_files.add(value)
        try:
            with os.fdopen(descriptor, 'wb', closefd=True) as stream:
                descriptor = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def read_canonical_bytes() -> bytes:
        before_path = os.lstat(path)
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(path, flags)
        chunks: list[bytes] = []
        total = 0
        try:
            before_descriptor = os.fstat(descriptor)
            if not stat.S_ISREG(before_descriptor.st_mode):
                raise RegistryError('existing artifact lock must be a regular file.')
            with os.fdopen(descriptor, 'rb', closefd=True) as stream:
                descriptor = -1
                while chunk := stream.read(_CHUNK_SIZE):
                    total += len(chunk)
                    if total > _MAX_JSON_BYTES:
                        raise RegistryError('existing artifact lock is too large.')
                    chunks.append(chunk)
                after_descriptor = os.fstat(stream.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        after_path = os.lstat(path)
        if (
            not stat.S_ISREG(before_path.st_mode)
            or not stat.S_ISREG(after_path.st_mode)
            or not _same_file(before_path, before_descriptor)
            or not _same_file(before_descriptor, after_descriptor)
            or not _same_file(after_descriptor, after_path)
        ):
            raise RegistryError('existing artifact lock changed while creating recovery copy.')
        return b''.join(chunks)

    def sync_directory() -> None:
        flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
        directory = os.open(path.parent, flags)
        try:
            os.fsync(directory)
        except BaseException as primary_error:
            try:
                os.close(directory)
            except BaseException as close_error:
                primary_error.add_note(
                    f'directory descriptor cleanup also failed: {type(close_error).__name__}'
                )
            raise
        else:
            os.close(directory)

    try:
        write_new_file(temporary, data)
        if had_old_lock:
            old_bytes = read_canonical_bytes()
            write_new_file(backup, old_bytes)
            backup_created = True
            load_artifact_lock(backup)
            sync_directory()
        os.replace(temporary, path)
        owned_files.discard(temporary)
        owned_files.add(path)
        committed = True
        sync_directory()
        if backup_created:
            backup.unlink()
            owned_files.discard(backup)
            backup_created = False
            # A successful return means the recovery name cannot reappear after crash.
            sync_directory()
    except BaseException as primary_error:
        cleanup_errors: list[BaseException] = []
        recovery_backup: Path | None = None
        recovery_path: Path | None = None
        canonical_old = had_old_lock and not committed
        if committed:
            if had_old_lock:
                if not backup_created and old_bytes is not None:
                    try:
                        write_new_file(backup, old_bytes)
                        backup_created = True
                        load_artifact_lock(backup)
                        try:
                            sync_directory()
                        except BaseException as sync_error:
                            cleanup_errors.append(sync_error)
                    except BaseException as recreate_error:
                        cleanup_errors.append(recreate_error)
                if backup_created:
                    try:
                        os.replace(backup, path)
                        owned_files.discard(backup)
                        owned_files.discard(path)
                        backup_created = False
                        committed = False
                        canonical_old = True
                    except BaseException as restore_error:
                        cleanup_errors.append(restore_error)
                        recovery_backup = backup
                        recovery_path = path
                else:
                    recovery_path = path
            else:
                committed = not cleanup(path, cleanup_errors)
                if committed:
                    recovery_path = path

        cleanup(temporary, cleanup_errors)
        if not backup_created:
            cleanup(backup, cleanup_errors)
        if canonical_old and backup_created:
            if cleanup(backup, cleanup_errors):
                backup_created = False
            else:
                recovery_backup = backup
        try:
            sync_directory()
        except BaseException as sync_error:
            cleanup_errors.append(sync_error)
        if backup_created and recovery_backup is None:
            recovery_backup = backup
        raise LockWriteError(
            primary_error,
            recovery_backup=recovery_backup,
            recovery_path=recovery_path,
            cleanup_errors=tuple(cleanup_errors),
        ) from primary_error


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    size_bytes: int
    sha256: str


def _stream_identity(
    path: Path, maximum: int,
) -> tuple[ArtifactIdentity, os.stat_result, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    try:
        descriptor = os.open(path, flags)
    except (FileNotFoundError, OSError) as error:
        raise SourceArtifactError('artifact is missing, a symlink, or cannot be opened.') from error
    digest = sha256()
    total = 0
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise SourceArtifactError('artifact must be a regular file.')
        with os.fdopen(descriptor, 'rb', closefd=True) as stream:
            descriptor = -1
            while chunk := stream.read(_CHUNK_SIZE):
                total += len(chunk)
                if total > maximum:
                    raise SourceArtifactError('artifact exceeds the configured maximum size.')
                digest.update(chunk)
            after_stream = os.fstat(stream.fileno())
        return ArtifactIdentity(total, digest.hexdigest()), opened, after_stream
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def compute_artifact_identity(path: Path, maximum: int) -> ArtifactIdentity:
    identity, opened, after_stream = _stream_identity(path, maximum)
    if not _same_file(opened, after_stream):
        raise SourceArtifactError('artifact changed while it was being hashed.')
    return identity


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev, left.st_ino, left.st_mode, left.st_size,
        left.st_mtime_ns, getattr(left, 'st_ctime_ns', None),
    ) == (
        right.st_dev, right.st_ino, right.st_mode, right.st_size,
        right.st_mtime_ns, getattr(right, 'st_ctime_ns', None),
    )


def verify_artifact(
    lock_record: ArtifactLockRecord,
    definition: SourceDefinition,
    artifact_root: Path,
) -> ArtifactIdentity:
    """Verify one local artifact with no-follow open and pre/post identity checks.

    These checks reasonably narrow local TOCTOU races, but the operator must still
    keep the evidence directory under trusted local administrative control.
    """
    if lock_record.family_id != definition.family_id:
        raise SourceArtifactError('lock family does not match registry definition.')
    if lock_record.artifact_path != definition.artifact_filename:
        raise SourceArtifactError('locked artifact path must exactly match the registry filename.')
    if lock_record.landing_url != definition.landing_url:
        raise SourceArtifactError('locked landing URL does not match the registry landing URL.')
    try:
        source_url = validate_https_url(
            lock_record.source_url, allowed_hosts=definition.allowed_source_hosts,
        )
    except ValueError as error:
        raise SourceArtifactError(str(error)) from error
    if source_url != lock_record.source_url:
        raise SourceArtifactError('source URL is not canonical.')
    if definition.artifact_url is not None and source_url != definition.artifact_url:
        raise SourceArtifactError('source URL does not match the canonical artifact URL.')
    if lock_record.size_bytes > definition.max_artifact_bytes:
        raise SourceArtifactError('locked artifact exceeds the configured maximum size.')

    root = artifact_root.resolve(strict=True)
    path = root / lock_record.artifact_path
    try:
        before = os.stat(path, follow_symlinks=False)
    except OSError as error:
        raise SourceArtifactError('artifact is missing.') from error
    if stat.S_ISLNK(before.st_mode):
        raise SourceArtifactError('artifact must not be a symlink.')
    if not stat.S_ISREG(before.st_mode):
        raise SourceArtifactError('artifact must be a regular file.')
    identity, opened, after_stream = _stream_identity(
        path, definition.max_artifact_bytes,
    )
    try:
        after = os.stat(path, follow_symlinks=False)
    except OSError as error:
        raise SourceArtifactError('artifact changed while it was being verified.') from error
    if (
        not _same_file(before, opened)
        or not _same_file(opened, after_stream)
        or not _same_file(after_stream, after)
    ):
        raise SourceArtifactError('artifact changed while it was being verified.')
    if identity.size_bytes != lock_record.size_bytes:
        raise SourceArtifactError('artifact size mismatch.')
    if identity.sha256 != lock_record.sha256:
        raise SourceArtifactError('artifact checksum mismatch.')
    return identity
