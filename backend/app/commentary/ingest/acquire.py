"""Bounded acquisition of the reviewed HelloAO commentary artifacts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import socket
import stat
import time
from typing import Any, BinaryIO
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .validate import SourceMetadata, load_source_registry


MAX_ARTIFACT_BYTES = 5 * 1024 * 1024
HTTP_TIMEOUT_SECONDS = 10
MAX_ATTEMPTS = 3
_READ_SIZE = 64 * 1024
_HOST = 'bible.helloao.org'
_CONTENT_RANGE = re.compile(r'bytes ([0-9]+)-([0-9]+)/([0-9]+)\Z')
_REGISTRY_PATH = Path(__file__).resolve().parents[3] / 'data' / 'commentaries' / 'sources.json'


@dataclass(frozen=True, slots=True)
class AcquiredArtifact:
    path: Path
    sidecar: Path
    checksum: str
    size: int


@dataclass(frozen=True, slots=True)
class _RepresentationValidator:
    header: str
    value: str


class _RestartDownload(Exception):
    """The partial artifact no longer identifies the upstream representation."""


class _PartialDurabilityError(OSError):
    """Partial bytes could not be made durable and must never be resumed."""


def _registry(path: Path | None = None) -> dict[str, SourceMetadata]:
    return load_source_registry(path or _REGISTRY_PATH)


def _approved_url(
    source_id: str, url: str, registry: dict[str, SourceMetadata],
) -> tuple[str, str | None]:
    if type(source_id) is not str or source_id not in registry:
        raise ValueError('source must be one of the five approved source IDs.')
    if type(url) is not str or any(character.isspace() for character in url):
        raise ValueError('URL must use the approved host and path.')
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError('URL must use the approved host and path.') from exc
    if (
        parsed.scheme != 'https' or parsed.hostname != _HOST or port is not None
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment
    ):
        raise ValueError('URL must use HTTPS on the approved host without credentials or options.')
    if unquote(parsed.path) != parsed.path or '\\' in parsed.path:
        raise ValueError('URL must use the exact approved API path.')
    parts = parsed.path.split('/')
    if len(parts) != 5 or parts[:4] != ['', 'api', 'c', source_id]:
        raise ValueError('URL must use the exact approved API path for its source.')
    filename = parts[4]
    # Exact paths have no trailing slash and split into five path components.
    if not filename:
        raise ValueError('URL must use the exact approved API path.')
    if filename == 'books.json':
        return filename, None
    if not filename.endswith('.json'):
        raise ValueError('URL must identify an approved JSON artifact.')
    book_id = filename[:-5]
    if book_id not in registry[source_id].expected_source_books:
        raise ValueError('URL book ID is not approved for this source.')
    return filename, book_id


def _validate_url(source_id: str, url: str, registry: dict[str, SourceMetadata]) -> tuple[str, str | None]:
    return _approved_url(source_id, url, registry)


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, source_id: str, registry: dict[str, SourceMetadata]):
        self._source_id = source_id
        self._registry = registry
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        _validate_url(self._source_id, newurl, self._registry)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_opener(source_id: str, registry: dict[str, SourceMetadata]):
    return build_opener(_SafeRedirectHandler(source_id, registry)).open


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('artifact contains duplicate JSON members.')
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValueError('artifact contains a nonstandard JSON constant.')


def _validate_json(raw: bytes) -> None:
    try:
        text = raw.decode('utf-8', errors='strict')
        json.loads(
            text, object_pairs_hook=_reject_duplicate_pairs, parse_constant=_reject_constant,
        )
    except UnicodeDecodeError as exc:
        raise ValueError('artifact must be valid UTF-8 JSON.') from exc
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('artifact must contain valid JSON.') from exc


def _check_path_components(path: Path) -> None:
    absolute = path.expanduser().absolute()
    for component in reversed((absolute, *absolute.parents)):
        try:
            info = os.lstat(component)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('output path must not contain a symlink.')


def _ensure_directory(path: Path) -> None:
    _check_path_components(path)
    path.mkdir(parents=True, exist_ok=True)
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ValueError('output path must be a real directory, not a symlink or special file.')


def _regular_size(path: Path) -> int:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return 0
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ValueError('partial artifact must be a regular file.')
    if info.st_size > MAX_ARTIFACT_BYTES:
        raise ValueError('artifact must be no larger than 5 MiB.')
    return info.st_size


def _response_status(response: object) -> int:
    status = getattr(response, 'status', None)
    if type(status) is int:
        return status
    getcode = getattr(response, 'getcode', None)
    value = getcode() if callable(getcode) else None
    if type(value) is not int:
        raise ValueError('HTTP response did not include a status code.')
    return value


def _content_type(response: object) -> str:
    headers = getattr(response, 'headers', None)
    value = headers.get_content_type() if hasattr(headers, 'get_content_type') else ''
    if value != 'application/json' and not value.endswith('+json'):
        raise ValueError('HTTP response must have a JSON content type.')
    return value


def _content_length(response: object) -> int | None:
    headers = getattr(response, 'headers', None)
    raw = headers.get('Content-Length') if headers is not None else None
    if raw is None:
        return None
    if not raw.isascii() or not raw.isdigit():
        raise ValueError('HTTP Content-Length must be a nonnegative integer.')
    return int(raw)


def _response_validator(response: object) -> _RepresentationValidator | None:
    headers = getattr(response, 'headers', None)
    etag = headers.get('ETag') if headers is not None else None
    if (
        type(etag) is str and len(etag) <= 200 and etag.startswith('"')
        and etag.endswith('"') and not etag.startswith('W/')
        and not any(character in '\r\n' for character in etag)
    ):
        return _RepresentationValidator('ETag', etag)
    modified = headers.get('Last-Modified') if headers is not None else None
    if (
        type(modified) is str and 0 < len(modified) <= 200
        and modified == modified.strip()
        and not any(character in '\r\n' for character in modified)
    ):
        return _RepresentationValidator('Last-Modified', modified)
    return None


def _read_resume_metadata(path: Path, url: str) -> _RepresentationValidator | None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_size > 1024:
        raise ValueError('partial artifact metadata must be a small regular file.')
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0),
    )
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
        ):
            raise ValueError('partial artifact metadata changed while opening.')
        raw = os.read(descriptor, 1025)
    finally:
        os.close(descriptor)
    try:
        value = json.loads(raw.decode('utf-8', errors='strict'))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('partial artifact metadata must contain valid JSON.') from exc
    if type(value) is not dict or set(value) not in ({'url', 'etag'}, {'url', 'last_modified'}):
        raise ValueError('partial artifact metadata has an invalid shape.')
    if value.get('url') != url:
        raise ValueError('partial artifact metadata belongs to another URL.')
    if 'etag' in value:
        validator = _RepresentationValidator('ETag', value['etag'])
    else:
        validator = _RepresentationValidator('Last-Modified', value['last_modified'])
    if (
        type(validator.value) is not str or not validator.value or len(validator.value) > 200
        or any(character in '\r\n' for character in validator.value)
        or validator.header == 'ETag'
        and not (validator.value.startswith('"') and validator.value.endswith('"'))
    ):
        raise ValueError('partial artifact metadata has an invalid validator.')
    return validator


def _write_resume_metadata(
    path: Path, url: str, validator: _RepresentationValidator,
) -> None:
    key = 'etag' if validator.header == 'ETag' else 'last_modified'
    raw = json.dumps(
        {'url': url, key: validator.value}, sort_keys=True, separators=(',', ':'),
    ).encode('utf-8')
    temporary = path.with_name(path.name + '.part')
    if temporary.exists() or temporary.is_symlink():
        _regular_size(temporary)
        temporary.unlink()
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
        0o600,
    )
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError('partial metadata write made no progress.')
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)


def _remove_regular(path: Path) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    if stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode):
        path.unlink()
        return
    raise ValueError(f'unsafe cleanup path: {path.name}.')


def _cleanup_artifacts(*paths: Path) -> None:
    for path in paths:
        try:
            _remove_regular(path)
        except (OSError, ValueError):
            # Cleanup is best effort here; the original safety failure remains
            # the command result and unsafe nodes are never followed.
            pass


def _resume_mode(response: object, existing: int) -> tuple[bool, int | None]:
    status = _response_status(response)
    length = _content_length(response)
    if existing == 0:
        if status != 200:
            raise ValueError('initial acquisition requires an HTTP 200 response.')
        return False, length
    if status == 200:
        return False, length
    if status != 206:
        raise ValueError('resumed acquisition requires HTTP 206 or a full HTTP 200 restart.')
    headers = getattr(response, 'headers', None)
    raw = headers.get('Content-Range') if headers is not None else None
    match = _CONTENT_RANGE.fullmatch(raw or '')
    if match is None:
        raise ValueError('resumed acquisition requires a valid Content-Range.')
    start, end, total = (int(item) for item in match.groups())
    if total > MAX_ARTIFACT_BYTES:
        raise ValueError('artifact must be no larger than 5 MiB.')
    if start != existing or end < start or total != end + 1:
        raise ValueError('resumed acquisition Content-Range does not match the partial artifact.')
    if length is not None and length != end - start + 1:
        raise ValueError('resumed acquisition Content-Length conflicts with Content-Range.')
    return True, total


def _read_response(response: BinaryIO, part: Path, existing: int) -> tuple[bytes, int]:
    _content_type(response)
    append, declared_total = _resume_mode(response, existing)
    offset = existing if append else 0
    if declared_total is not None:
        total = declared_total if append else offset + declared_total
        if total > MAX_ARTIFACT_BYTES:
            raise ValueError('artifact must be no larger than 5 MiB.')
    flags = (
        os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
        | getattr(os, 'O_NONBLOCK', 0)
    )
    flags |= os.O_APPEND if append else os.O_TRUNC
    descriptor = os.open(part, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError('partial artifact must be a regular file.')
        total = offset
        while True:
            chunk = response.read(min(_READ_SIZE, MAX_ARTIFACT_BYTES + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ARTIFACT_BYTES:
                raise ValueError('artifact must be no larger than 5 MiB.')
            view = memoryview(chunk)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError('artifact write made no progress.')
                view = view[written:]
        if declared_total is not None and total != declared_total:
            raise ValueError('HTTP response ended before its declared size.')
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = total
        while remaining:
            chunk = os.read(descriptor, min(_READ_SIZE, remaining))
            if not chunk:
                raise OSError('durable artifact ended before its expected size.')
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b''.join(chunks)
    finally:
        try:
            # Persist every byte written even when response.read raised. The
            # next request derives its Range only after this succeeds.
            os.fsync(descriptor)
        except OSError as exc:
            raise _PartialDurabilityError('partial artifact could not be fsynced.') from exc
        finally:
            os.close(descriptor)
    return raw, total


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_sidecar(path: Path, checksum: str, filename: str) -> None:
    temporary = path.with_name(path.name + '.part')
    if temporary.exists() or temporary.is_symlink():
        _regular_size(temporary)
        temporary.unlink()
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
        0o600,
    )
    try:
        payload = memoryview(f'{checksum}  {filename}\n'.encode('ascii'))
        while payload:
            written = os.write(descriptor, payload)
            if written <= 0:
                raise OSError('checksum sidecar write made no progress.')
            payload = payload[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)


def acquire_source(
    source_id: str,
    url: str,
    output: Path,
    *,
    opener: Callable[..., object] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    registry_path: Path | None = None,
) -> AcquiredArtifact:
    """Acquire one exact allowlisted JSON artifact through a safe resumable file."""
    registry = _registry(registry_path)
    filename, book_id = _validate_url(source_id, url, registry)
    if not isinstance(output, Path):
        output = Path(output)
    _ensure_directory(output)
    destination = output / source_id
    _ensure_directory(destination)
    target = destination / filename
    sidecar = destination / f'{filename}.sha256'
    part = destination / f'{filename}.part'
    resume_metadata = destination / f'{filename}.part.meta'
    existing = _regular_size(part)
    resume_validator: _RepresentationValidator | None = None
    if existing:
        resume_validator = _read_resume_metadata(resume_metadata, url)
        if resume_validator is None:
            _cleanup_artifacts(part, resume_metadata)
            existing = 0
    elif resume_metadata.exists() or resume_metadata.is_symlink():
        _cleanup_artifacts(resume_metadata)
    if target.exists() and (not target.is_file() or target.is_symlink()):
        raise ValueError('final artifact must be a regular file.')
    if sidecar.exists() and (not sidecar.is_file() or sidecar.is_symlink()):
        raise ValueError('checksum sidecar must be a regular file.')
    transport = opener or _default_opener(source_id, registry)

    last_network_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        request = Request(url, headers={
            'Accept': 'application/json',
            'User-Agent': 'Unbound-Bible-Commentary-Importer/1',
        })
        if existing:
            request.add_header('Range', f'bytes={existing}-')
            request.add_header('If-Range', resume_validator.value)  # type: ignore[union-attr]
        try:
            response = transport(request, timeout=HTTP_TIMEOUT_SECONDS)
            with response:  # type: ignore[attr-defined]
                final_url = response.geturl()  # type: ignore[attr-defined]
                try:
                    final_name, final_book = _validate_url(source_id, final_url, registry)
                except ValueError as exc:
                    raise ValueError('HTTP redirect left the approved URL boundary.') from exc
                if (final_name, final_book) != (filename, book_id):
                    raise ValueError('HTTP redirect changed the approved artifact identity.')
                response_validator = _response_validator(response)
                status = _response_status(response)
                if existing and status == 206:
                    if response_validator != resume_validator:
                        raise _RestartDownload(
                            'upstream representation changed during resumed acquisition.'
                        )
                elif status == 200:
                    resume_validator = response_validator
                    if response_validator is not None:
                        _write_resume_metadata(resume_metadata, url, response_validator)
                    else:
                        _cleanup_artifacts(resume_metadata)
                raw, size = _read_response(response, part, existing)  # type: ignore[arg-type]
            break
        except _RestartDownload as exc:
            last_network_error = exc
            _cleanup_artifacts(part, resume_metadata)
            existing = 0
            resume_validator = None
        except _PartialDurabilityError as exc:
            last_network_error = exc
            _cleanup_artifacts(part, resume_metadata)
            existing = 0
            resume_validator = None
        except HTTPError as exc:
            last_network_error = exc
            if exc.code == 416 and part.exists():
                _cleanup_artifacts(part, resume_metadata)
                existing = 0
                resume_validator = None
        except (URLError, TimeoutError, socket.timeout, ConnectionError, OSError) as exc:
            last_network_error = exc
            # A read timeout can occur after durable bytes were appended. Resume
            # from the descriptor's actual size, never from a stale request offset.
            existing = _regular_size(part)
            if existing:
                if resume_validator is None:
                    _cleanup_artifacts(part, resume_metadata)
                    existing = 0
                else:
                    persisted = _read_resume_metadata(resume_metadata, url)
                    if persisted != resume_validator:
                        _cleanup_artifacts(part, resume_metadata)
                        existing = 0
                        resume_validator = None
        except ValueError:
            _cleanup_artifacts(part, resume_metadata)
            raise
        if attempt < MAX_ATTEMPTS - 1:
            sleeper(float(attempt + 1))
    else:
        raise ValueError('commentary acquisition failed after three attempts.') from last_network_error

    try:
        _validate_json(raw)
        checksum = sha256(raw).hexdigest()
        expected = registry[source_id].source_checksum if filename == 'books.json' else None
        if expected is not None and checksum != expected:
            raise ValueError('artifact checksum does not match the reviewed registry checksum.')
        # Materialize both members before the durability boundary. A failure at
        # either rename or fsync removes the pair, never exposing a half result.
        _write_sidecar(sidecar, checksum, filename)
        os.replace(part, target)
        _cleanup_artifacts(resume_metadata)
        _fsync_directory(destination)
    except Exception:
        _cleanup_artifacts(
            target, sidecar, part, resume_metadata,
            sidecar.with_name(sidecar.name + '.part'),
            resume_metadata.with_name(resume_metadata.name + '.part'),
        )
        try:
            _fsync_directory(destination)
        except OSError:
            pass
        raise
    return AcquiredArtifact(target, sidecar, checksum, size)


def acquire_source_bundle(
    source_id: str,
    output: Path,
    *,
    opener: Callable[..., object] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    registry_path: Path | None = None,
) -> tuple[AcquiredArtifact, ...]:
    """Acquire the reviewed source catalog and every exact allowlisted book artifact."""
    registry = _registry(registry_path)
    if source_id not in registry:
        raise ValueError('source must be one of the five approved source IDs.')
    base = f'https://{_HOST}/api/c/{source_id}'
    urls = [registry[source_id].upstream_url]
    urls.extend(f'{base}/{book_id}.json' for book_id in registry[source_id].expected_source_books)
    return tuple(
        acquire_source(
            source_id, url, output, opener=opener, sleeper=sleeper,
            registry_path=registry_path,
        )
        for url in urls
    )
