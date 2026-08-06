"""Bounded acquisition of the reviewed HelloAO commentary artifacts."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from hashlib import sha256
import certifi
import json
import os
from pathlib import Path
import re
import socket
import ssl
import stat
from threading import Event, Lock
import time
from typing import Any, BinaryIO, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from .validate import SourceMetadata, load_source_registry


MAX_ARTIFACT_BYTES = 5 * 1024 * 1024
MAX_REVIEWED_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_SOURCE_BYTES = 1024 * 1024 * 1024
HTTP_TIMEOUT_SECONDS = 10
MAX_ATTEMPTS = 3
MAX_CHAPTER_CANDIDATES_PER_BOOK = 200
MAX_CHAPTER_CANDIDATES_PER_SOURCE = 1500
_READ_SIZE = 64 * 1024
_HOST = 'bible.helloao.org'
_CONTENT_RANGE = re.compile(r'bytes ([0-9]+)-([0-9]+)/([0-9]+)\Z')
_REGISTRY_PATH = Path(__file__).resolve().parents[3] / 'data' / 'commentaries' / 'sources.json'
_REVIEWED_ARTIFACTS_PATH = (
    Path(__file__).resolve().parents[3] / 'data' / 'commentaries' / 'reviewed-artifacts.json'
)


@dataclass(frozen=True, slots=True)
class AcquiredArtifact:
    path: Path
    sidecar: Path
    checksum: str
    size: int
    url: str


@dataclass(frozen=True, slots=True)
class _RepresentationValidator:
    header: str
    value: str


@dataclass(frozen=True, slots=True)
class _ChapterPlan:
    first: int | None
    last: int | None
    expected_count: int


class _MissingChapter(ValueError):
    """One bounded catalog candidate is absent upstream and may represent a declared gap."""


class _RestartDownload(Exception):
    """The partial artifact no longer identifies the upstream representation."""


class _PartialDurabilityError(OSError):
    """Partial bytes could not be made durable and must never be resumed."""


class _AcquisitionStopped(Exception):
    """A sibling acquisition failed, so this worker must not publish."""


class _CooperativeStop:
    """Serialize cancellation notification against authoritative publication."""

    def __init__(self):
        self._event = Event()
        self._publication_lock = Lock()

    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._event.wait(timeout)

    def set(self) -> None:
        with self._publication_lock:
            self._event.set()

    @contextmanager
    def publication(self) -> Iterator[None]:
        with self._publication_lock:
            yield


class _SourceByteBudget:
    """Atomically reserve exact artifact bytes before publishing generations."""

    def __init__(self, initial_bytes: int = 0, *, limit: int | None = None):
        maximum = MAX_SOURCE_BYTES if limit is None else limit
        if (
            type(initial_bytes) is not int or initial_bytes < 0
            or type(maximum) is not int or maximum < 0 or initial_bytes > maximum
        ):
            raise ValueError('commentary source exceeds the aggregate byte limit.')
        self._used = initial_bytes
        self._limit = maximum
        self._lock = Lock()

    def reserve(self, size: int) -> None:
        if type(size) is not int or size < 0:
            raise ValueError('artifact size must be a nonnegative integer.')
        with self._lock:
            if self._used + size > self._limit:
                raise ValueError('commentary source exceeds the aggregate byte limit.')
            self._used += size

    def release(self, size: int) -> None:
        with self._lock:
            if type(size) is not int or size < 0 or size > self._used:
                raise RuntimeError('commentary source byte reservation is inconsistent.')
            self._used -= size


def _raise_if_stopped(stop_event: Event | _CooperativeStop | None) -> None:
    if stop_event is not None and stop_event.is_set():
        raise _AcquisitionStopped('commentary acquisition stopped after a sibling failure.')


_FinalizationHook = Callable[[str], None]


def _registry(path: Path | None = None) -> dict[str, SourceMetadata]:
    return load_source_registry(path or _REGISTRY_PATH)


def _reviewed_catalog_artifact(
    source_id: str, url: str, path: Path,
) -> str:
    """Load the independently reviewed raw catalog digest without following links."""
    directory = _open_directory_nofollow(path.parent)
    try:
        raw = _read_regular_at(directory, path.name, MAX_REVIEWED_MANIFEST_BYTES)
    finally:
        os.close(directory)
    if raw is None:
        raise ValueError('reviewed artifact manifest is required for catalog acquisition.')
    try:
        manifest = json.loads(
            raw.decode('utf-8', errors='strict'),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
        source = manifest['sources'][source_id]
        record = source['artifacts']['books.json']
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, RecursionError) as exc:
        raise ValueError('reviewed artifact manifest has no approved catalog record.') from exc
    if (
        type(manifest) is not dict or manifest.get('schema_version') != 1
        or set(manifest) != {'schema_version', 'sources'}
        or type(source) is not dict or set(source) != {'artifacts'}
        or type(source['artifacts']) is not dict
        or type(record) is not dict or set(record) != {'url', 'sha256'}
        or record.get('url') != url
        or type(record.get('sha256')) is not str
        or re.fullmatch(r'[0-9a-f]{64}', record['sha256']) is None
    ):
        raise ValueError('reviewed artifact manifest has no approved catalog record.')
    return record['sha256']


def _catalog_chapter_bounds(
    raw: bytes, source_id: str, expected_books: tuple[str, ...],
) -> dict[str, _ChapterPlan]:
    """Extract only exact, source-owned chapter bounds from a verified catalog."""
    try:
        document = json.loads(
            raw.decode('utf-8', errors='strict'),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
        commentary = document['commentary']
        books = document['books']
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, RecursionError) as exc:
        raise ValueError('catalog must contain documented commentary book metadata.') from exc
    if (
        type(document) is not dict or set(document) != {'commentary', 'books'}
        or type(commentary) is not dict or commentary.get('id') != source_id
        or commentary.get('listOfBooksApiLink') != f'/api/c/{source_id}/books.json'
        or commentary.get('numberOfBooks') != len(expected_books)
        or type(books) is not list or len(books) != len(expected_books)
    ):
        raise ValueError('catalog does not match the reviewed source registry.')
    bounds: dict[str, _ChapterPlan] = {}
    total_chapters = 0
    total_candidates = 0
    for book in books:
        if type(book) is not dict:
            raise ValueError('catalog book metadata must be an object.')
        book_id = book.get('id')
        count = book.get('numberOfChapters')
        first = book.get('firstChapterNumber')
        last = book.get('lastChapterNumber')
        common_invalid = (
            type(book_id) is not str or book_id not in expected_books or book_id in bounds
            or book.get('commentaryId') != source_id
            or type(count) is not int or count < 0
        )
        zero_fields = (
            'firstChapterNumber', 'lastChapterNumber',
            'firstChapterApiLink', 'lastChapterApiLink',
            'firstChapterReference', 'lastChapterReference',
        )
        zero_shape = (
            count == 0 and set(zero_fields).issubset(book)
            and all(book[field] is None for field in zero_fields)
        )
        positive_shape = (
            type(count) is int and count > 0
            and type(first) is int and first == 1
            and type(last) is int and last >= first
            and count <= last - first + 1
            and last - first + 1 <= MAX_CHAPTER_CANDIDATES_PER_BOOK
            and book.get('firstChapterApiLink') == f'/api/c/{source_id}/{book_id}/1.json'
            and book.get('lastChapterApiLink') == f'/api/c/{source_id}/{book_id}/{last}.json'
        )
        if common_invalid or not (zero_shape or positive_shape):
            raise ValueError('catalog book has invalid source, chapter bounds, or links.')
        bounds[book_id] = _ChapterPlan(first, last, count)
        total_chapters += count
        if count:
            total_candidates += last - first + 1  # type: ignore[operator]
    if tuple(bounds) != expected_books or commentary.get('totalNumberOfChapters') != total_chapters:
        raise ValueError('catalog book order or total chapter count does not match the registry.')
    if (
        total_chapters > MAX_CHAPTER_CANDIDATES_PER_SOURCE
        or total_candidates > MAX_CHAPTER_CANDIDATES_PER_SOURCE
    ):
        raise ValueError('catalog exceeds the bounded per-source chapter limit.')
    return bounds


def _approved_url(
    source_id: str, url: str, registry: dict[str, SourceMetadata],
    chapter_bounds: dict[str, _ChapterPlan] | None = None,
) -> tuple[str, str | None, int | None]:
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
    if parts[:4] != ['', 'api', 'c', source_id]:
        raise ValueError('URL must use the exact approved API path for its source.')
    if len(parts) == 5 and parts[4] == 'books.json':
        return 'books.json', None, None
    if len(parts) != 6 or not parts[5].endswith('.json'):
        raise ValueError('URL must identify an approved catalog or chapter JSON artifact.')
    book_id = parts[4]
    raw_chapter = parts[5][:-5]
    if (
        book_id not in registry[source_id].expected_source_books
        or not raw_chapter.isascii() or not raw_chapter.isdigit()
        or raw_chapter.startswith('0')
    ):
        raise ValueError('URL book ID is not approved for this source.')
    chapter = int(raw_chapter)
    bounds = chapter_bounds.get(book_id) if chapter_bounds is not None else None
    if (
        bounds is None or bounds.expected_count == 0
        or bounds.first is None or bounds.last is None
        or chapter < bounds.first or chapter > bounds.last
    ):
        raise ValueError('URL chapter is outside the reviewed catalog bounds.')
    return f'{book_id}-{chapter}.json', book_id, chapter


def _validate_url(
    source_id: str, url: str, registry: dict[str, SourceMetadata],
    chapter_bounds: dict[str, _ChapterPlan] | None = None,
) -> tuple[str, str | None, int | None]:
    return _approved_url(source_id, url, registry, chapter_bounds)


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(
        self, source_id: str, registry: dict[str, SourceMetadata],
        chapter_bounds: dict[str, _ChapterPlan] | None,
    ):
        self._source_id = source_id
        self._registry = registry
        self._chapter_bounds = chapter_bounds
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        _validate_url(self._source_id, newurl, self._registry, self._chapter_bounds)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_opener(
    source_id: str, registry: dict[str, SourceMetadata],
    chapter_bounds: dict[str, _ChapterPlan] | None = None,
):
    context = ssl.create_default_context(cafile=certifi.where())
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise RuntimeError('TLS certificate and hostname verification must remain enabled.')
    return build_opener(
        _SafeRedirectHandler(source_id, registry, chapter_bounds),
        HTTPSHandler(context=context),
    ).open


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


def _regular_size_at(directory_fd: int, name: str) -> int:
    try:
        info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return 0
    if not stat.S_ISREG(info.st_mode):
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


def _read_resume_metadata(
    directory_fd: int, name: str, url: str,
) -> _RepresentationValidator | None:
    try:
        info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_size > 1024:
        raise ValueError('partial artifact metadata must be a small regular file.')
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0),
        dir_fd=directory_fd,
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
    directory_fd: int, name: str, url: str, validator: _RepresentationValidator,
) -> None:
    key = 'etag' if validator.header == 'ETag' else 'last_modified'
    raw = json.dumps(
        {'url': url, key: validator.value}, sort_keys=True, separators=(',', ':'),
    ).encode('utf-8')
    _write_atomic_at(directory_fd, name, raw)


def _cleanup_artifacts_at(directory_fd: int, *names: str) -> None:
    for name in names:
        try:
            _unlink_at(directory_fd, name)
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


def _read_response(
    response: BinaryIO, directory_fd: int, part_name: str, existing: int,
) -> tuple[bytes, int]:
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
    descriptor = os.open(part_name, flags, 0o600, dir_fd=directory_fd)
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


def _fsync_directory(directory_fd: int) -> None:
    descriptor = os.dup(directory_fd)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_sidecar(
    path: Path, checksum: str, filename: str, directory_fd: int,
) -> None:
    _write_atomic_at(
        directory_fd, path.name, f'{checksum}  {filename}\n'.encode('ascii'),
    )


def _open_directory_nofollow(path: Path, *, create: bool = False) -> int:
    """Open a directory by walking every component without following links."""
    absolute = path.expanduser().absolute()
    descriptor = os.open('/', os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        for name in absolute.parts[1:]:
            child, created = _open_or_create_child(
                descriptor, name, create=create,
            )
            try:
                if created:
                    _fsync_directory(descriptor)
            except Exception:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _open_or_create_child(
    parent_fd: int, name: str, *, create: bool,
) -> tuple[int, bool]:
    if '/' in name or name in {'', '.', '..'}:
        raise ValueError('directory name is invalid.')
    created = False
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
            created = True
        except FileExistsError:
            pass
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0),
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise ValueError('output path must not contain a symlink or special node.') from exc
    return descriptor, created


def _open_child_directory(parent_fd: int, name: str, *, create: bool = False) -> int:
    return _open_or_create_child(parent_fd, name, create=create)[0]


def _read_regular_at(directory_fd: int, name: str, maximum: int) -> bytes | None:
    try:
        info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
        raise ValueError(f'{Path(name).name} must be a small regular file.')
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0),
        dir_fd=directory_fd,
    )
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError(f'{Path(name).name} changed while opening.')
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                raise ValueError(f'{Path(name).name} ended while reading.')
            chunks.append(chunk)
            remaining -= len(chunk)
        return b''.join(chunks)
    finally:
        os.close(descriptor)


def _unlink_at(directory_fd: int, name: str) -> None:
    try:
        info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f'{Path(name).name} must be a regular file.')
    os.unlink(name, dir_fd=directory_fd)


def _write_atomic_at(directory_fd: int, name: str, raw: bytes) -> None:
    temporary = name + '.part'
    _unlink_at(directory_fd, temporary)
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
        0o600,
        dir_fd=directory_fd,
    )
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError('atomic file write made no progress.')
            view = view[written:]
        os.fsync(descriptor)
        os.replace(
            temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
        )
    except Exception:
        try:
            _unlink_at(directory_fd, temporary)
        except Exception:
            pass
        raise
    finally:
        os.close(descriptor)


def _path_still_identifies(path: Path, descriptor: int) -> bool:
    try:
        current = os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return False
    opened = os.fstat(descriptor)
    return stat.S_ISDIR(current.st_mode) and (
        current.st_dev, current.st_ino
    ) == (opened.st_dev, opened.st_ino)


def _marker_document(
    source_id: str, filename: str, url: str, checksum: str,
) -> bytes:
    return (json.dumps({
        'schema_version': 1,
        'source_id': source_id,
        'artifact': filename,
        'url': url,
        'sha256': checksum,
        'generation': f'generations/{filename}/{checksum}',
    }, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def _finalize_generation(
    *,
    destination: Path,
    destination_fd: int,
    source_id: str,
    filename: str,
    url: str,
    raw: bytes,
    checksum: str,
    hook: _FinalizationHook | None,
    stop_event: Event | _CooperativeStop | None = None,
) -> tuple[Path, Path]:
    checkpoint = hook or (lambda _step: None)
    artifact_root = destination / 'generations' / filename
    generation = artifact_root / checksum
    artifact = generation / filename
    sidecar = generation / f'{filename}.sha256'
    marker_name = f'{filename}.current.json'
    generations_fd = artifact_root_fd = generation_fd = None
    switched = False
    try:
        _raise_if_stopped(stop_event)
        generations_fd, created = _open_or_create_child(
            destination_fd, 'generations', create=True,
        )
        if created:
            _fsync_directory(destination_fd)
        artifact_root_fd, created = _open_or_create_child(
            generations_fd, filename, create=True,
        )
        if created:
            _fsync_directory(generations_fd)
        generation_fd, created = _open_or_create_child(
            artifact_root_fd, checksum, create=True,
        )
        if created:
            _fsync_directory(artifact_root_fd)
        previous_marker = _read_regular_at(destination_fd, marker_name, 4096)
        _raise_if_stopped(stop_event)
        _write_atomic_at(generation_fd, filename, raw)
        checkpoint('generation_data')
        _write_sidecar(sidecar, checksum, filename, generation_fd)
        checkpoint('generation_sidecar')
        _fsync_directory(generation_fd)
        marker_raw = _marker_document(source_id, filename, url, checksum)
        marker_temporary = marker_name + '.part'
        _raise_if_stopped(stop_event)
        _write_atomic_at(destination_fd, marker_temporary, marker_raw)
        checkpoint('before_marker_switch')
        if not _path_still_identifies(destination, destination_fd):
            raise ValueError('acquisition output directory changed during finalization.')
        publication = (
            stop_event.publication()
            if isinstance(stop_event, _CooperativeStop) else nullcontext()
        )
        with publication:
            _raise_if_stopped(stop_event)
            os.replace(
                marker_temporary, marker_name,
                src_dir_fd=destination_fd, dst_dir_fd=destination_fd,
            )
            switched = True
        checkpoint('after_marker_switch')
        checkpoint('directory_fsync')
        _fsync_directory(destination_fd)
        return artifact, sidecar
    except Exception:
        if switched:
            try:
                if previous_marker is None:
                    _unlink_at(destination_fd, marker_name)
                else:
                    _write_atomic_at(destination_fd, marker_name, previous_marker)
                _fsync_directory(destination_fd)
            except Exception:
                pass
        else:
            try:
                _unlink_at(destination_fd, marker_name + '.part')
                _unlink_at(destination_fd, marker_name + '.part.part')
            except Exception:
                pass
        # Immutable incomplete generations are harmless because readers only
        # follow the durable marker. Leave them for operator cleanup.
        raise
    finally:
        for descriptor in (generation_fd, artifact_root_fd, generations_fd):
            if descriptor is not None:
                os.close(descriptor)


def read_acquired_artifact(
    source_directory: Path, filename: str, *, source_id: str,
) -> tuple[bytes, str, str]:
    """Read and verify only the immutable generation selected by the marker."""
    if '/' in filename or filename in {'', '.', '..'}:
        raise ValueError('Requested artifact name is invalid.')
    source_fd = _open_directory_nofollow(source_directory)
    generations_fd = artifact_root_fd = generation_fd = None
    try:
        raw_marker = _read_regular_at(source_fd, f'{filename}.current.json', 4096)
        if raw_marker is None:
            raise ValueError(f'No current acquired generation exists for {filename}.')
        try:
            value = json.loads(raw_marker.decode('utf-8', errors='strict'))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ValueError('Current artifact marker is invalid.') from exc
        expected_keys = {
            'schema_version', 'source_id', 'artifact', 'url', 'sha256', 'generation',
        }
        if type(value) is not dict or set(value) != expected_keys:
            raise ValueError('Current artifact marker has an invalid shape.')
        checksum = value['sha256']
        generation = value['generation']
        if (
            value['schema_version'] != 1 or value['source_id'] != source_id
            or value['artifact'] != filename or type(value['url']) is not str
            or type(checksum) is not str or not re.fullmatch(r'[0-9a-f]{64}', checksum)
            or generation != f'generations/{filename}/{checksum}'
        ):
            raise ValueError('Current artifact marker does not match the requested artifact.')
        generations_fd = _open_child_directory(source_fd, 'generations')
        artifact_root_fd = _open_child_directory(generations_fd, filename)
        generation_fd = _open_child_directory(artifact_root_fd, checksum)
        raw = _read_regular_at(generation_fd, filename, MAX_ARTIFACT_BYTES)
        if raw is None or sha256(raw).hexdigest() != checksum:
            raise ValueError('Current acquired generation is incomplete or corrupt.')
        return raw, checksum, value['url']
    finally:
        for descriptor in (generation_fd, artifact_root_fd, generations_fd, source_fd):
            if descriptor is not None:
                os.close(descriptor)


def acquire_source(
    source_id: str,
    url: str,
    output: Path,
    *,
    opener: Callable[..., object] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    registry_path: Path | None = None,
    reviewed_artifacts_path: Path | None = None,
    chapter_bounds: dict[str, _ChapterPlan] | None = None,
    finalization_hook: _FinalizationHook | None = None,
    _source_budget: _SourceByteBudget | None = None,
    _stop_event: Event | _CooperativeStop | None = None,
) -> AcquiredArtifact:
    """Acquire one exact allowlisted JSON artifact through a safe resumable file."""
    registry = _registry(registry_path)
    filename, book_id, _chapter = _validate_url(
        source_id, url, registry, chapter_bounds,
    )
    expected_catalog_checksum = (
        _reviewed_catalog_artifact(
            source_id, url, reviewed_artifacts_path or _REVIEWED_ARTIFACTS_PATH,
        )
        if filename == 'books.json' else None
    )
    if not isinstance(output, Path):
        output = Path(output)
    destination = output / source_id
    output_fd = _open_directory_nofollow(output, create=True)
    destination_fd = None
    try:
        destination_fd, created = _open_or_create_child(
            output_fd, source_id, create=True,
        )
        if created:
            _fsync_directory(output_fd)
    except Exception:
        if destination_fd is not None:
            os.close(destination_fd)
            destination_fd = None
        raise
    finally:
        os.close(output_fd)
    try:
        return _acquire_source_from_directory(
            source_id=source_id, url=url, destination=destination,
            destination_fd=destination_fd, filename=filename, book_id=book_id,
            registry=registry, opener=opener, sleeper=sleeper,
            chapter_bounds=chapter_bounds,
            expected_catalog_checksum=expected_catalog_checksum,
            finalization_hook=finalization_hook,
            source_budget=_source_budget, stop_event=_stop_event,
        )
    finally:
        if destination_fd is not None:
            os.close(destination_fd)


def _acquire_source_from_directory(
    *,
    source_id: str,
    url: str,
    destination: Path,
    destination_fd: int,
    filename: str,
    book_id: str | None,
    registry: dict[str, SourceMetadata],
    opener: Callable[..., object] | None,
    sleeper: Callable[[float], None],
    chapter_bounds: dict[str, _ChapterPlan] | None,
    expected_catalog_checksum: str | None,
    finalization_hook: _FinalizationHook | None,
    source_budget: _SourceByteBudget | None,
    stop_event: Event | _CooperativeStop | None,
) -> AcquiredArtifact:
    """Acquire while every mutable file operation stays below one open directory."""
    part_name = f'{filename}.part'
    metadata_name = f'{filename}.part.meta'
    metadata_temporary = metadata_name + '.part'
    existing = _regular_size_at(destination_fd, part_name)
    resume_validator: _RepresentationValidator | None = None
    if existing:
        resume_validator = _read_resume_metadata(destination_fd, metadata_name, url)
        if resume_validator is None:
            _cleanup_artifacts_at(destination_fd, part_name, metadata_name)
            existing = 0
    else:
        _cleanup_artifacts_at(destination_fd, metadata_name)
    transport = opener or _default_opener(source_id, registry, chapter_bounds)

    last_network_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        _raise_if_stopped(stop_event)
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
                _raise_if_stopped(stop_event)
                final_url = response.geturl()  # type: ignore[attr-defined]
                try:
                    final_name, final_book, _final_chapter = _validate_url(
                        source_id, final_url, registry, chapter_bounds,
                    )
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
                        _write_resume_metadata(
                            destination_fd, metadata_name, url, response_validator,
                        )
                    else:
                        _cleanup_artifacts_at(destination_fd, metadata_name)
                raw, size = _read_response(
                    response, destination_fd, part_name, existing,  # type: ignore[arg-type]
                )
                _raise_if_stopped(stop_event)
            break
        except _AcquisitionStopped:
            _cleanup_artifacts_at(destination_fd, part_name, metadata_name)
            raise
        except _RestartDownload as exc:
            last_network_error = exc
            _cleanup_artifacts_at(destination_fd, part_name, metadata_name)
            existing = 0
            resume_validator = None
        except _PartialDurabilityError as exc:
            last_network_error = exc
            _cleanup_artifacts_at(destination_fd, part_name, metadata_name)
            existing = 0
            resume_validator = None
        except HTTPError as exc:
            if exc.code == 404:
                _cleanup_artifacts_at(destination_fd, part_name, metadata_name)
                raise _MissingChapter('catalog candidate chapter is absent upstream.') from exc
            last_network_error = exc
            if exc.code == 416 and _regular_size_at(destination_fd, part_name):
                _cleanup_artifacts_at(destination_fd, part_name, metadata_name)
                existing = 0
                resume_validator = None
        except (URLError, TimeoutError, socket.timeout, ConnectionError, OSError) as exc:
            last_network_error = exc
            # A read timeout can occur after durable bytes were appended. Resume
            # from the descriptor's actual size, never from a stale request offset.
            existing = _regular_size_at(destination_fd, part_name)
            if existing:
                if resume_validator is None:
                    _cleanup_artifacts_at(destination_fd, part_name, metadata_name)
                    existing = 0
                else:
                    persisted = _read_resume_metadata(
                        destination_fd, metadata_name, url,
                    )
                    if persisted != resume_validator:
                        _cleanup_artifacts_at(destination_fd, part_name, metadata_name)
                        existing = 0
                        resume_validator = None
        except ValueError:
            _cleanup_artifacts_at(destination_fd, part_name, metadata_name)
            raise
        if attempt < MAX_ATTEMPTS - 1:
            _raise_if_stopped(stop_event)
            sleeper(float(attempt + 1))
    else:
        raise ValueError('commentary acquisition failed after three attempts.') from last_network_error

    reserved = False
    try:
        _validate_json(raw)
        checksum = sha256(raw).hexdigest()
        if expected_catalog_checksum is not None and checksum != expected_catalog_checksum:
            raise ValueError('artifact checksum does not match the reviewed artifact checksum.')
        _raise_if_stopped(stop_event)
        if source_budget is not None:
            source_budget.reserve(size)
            reserved = True
        _raise_if_stopped(stop_event)
        artifact, sidecar = _finalize_generation(
            destination=destination, destination_fd=destination_fd,
            source_id=source_id, filename=filename, url=url, raw=raw,
            checksum=checksum, hook=finalization_hook,
            stop_event=stop_event,
        )
        _cleanup_artifacts_at(destination_fd, part_name, metadata_name)
    except Exception:
        if reserved:
            source_budget.release(size)  # type: ignore[union-attr]
        _cleanup_artifacts_at(
            destination_fd, part_name, metadata_name, metadata_temporary,
        )
        raise
    return AcquiredArtifact(artifact, sidecar, checksum, size, url)


def acquire_source_bundle(
    source_id: str,
    output: Path,
    *,
    opener: Callable[..., object] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    registry_path: Path | None = None,
    reviewed_artifacts_path: Path | None = None,
) -> tuple[AcquiredArtifact, ...]:
    """Acquire the reviewed catalog, then every exact catalog-declared chapter."""
    registry = _registry(registry_path)
    if source_id not in registry:
        raise ValueError('source must be one of the five approved source IDs.')
    source_budget = _SourceByteBudget()
    catalog = acquire_source(
        source_id, registry[source_id].upstream_url, output,
        opener=opener, sleeper=sleeper, registry_path=registry_path,
        reviewed_artifacts_path=reviewed_artifacts_path,
        _source_budget=source_budget,
    )
    raw_catalog, catalog_digest, catalog_url = read_acquired_artifact(
        output / source_id, 'books.json', source_id=source_id,
    )
    if catalog_digest != catalog.checksum or catalog_url != catalog.url:
        raise ValueError('acquired catalog generation changed before chapter scheduling.')
    chapter_bounds = _catalog_chapter_bounds(
        raw_catalog, source_id, registry[source_id].expected_source_books,
    )
    base = f'https://{_HOST}/api/c/{source_id}'
    candidates = tuple(
        (book_id, chapter, f'{base}/{book_id}/{chapter}.json')
        for book_id in registry[source_id].expected_source_books
        for chapter in (() if chapter_bounds[book_id].expected_count == 0 else range(
            chapter_bounds[book_id].first,  # type: ignore[arg-type]
            chapter_bounds[book_id].last + 1,  # type: ignore[operator]
        ))
    )
    stop_event = _CooperativeStop()

    def acquire_chapter(candidate: tuple[str, int, str]) -> AcquiredArtifact:
        _book_id, _chapter, url = candidate
        return acquire_source(
            source_id, url, output, opener=opener, sleeper=sleeper,
            registry_path=registry_path, reviewed_artifacts_path=reviewed_artifacts_path,
            chapter_bounds=chapter_bounds,
            _source_budget=source_budget, _stop_event=stop_event,
        )

    acquired = _bounded_parallel_acquire(
        candidates, acquire_chapter, initial_bytes=catalog.size, stop_event=stop_event,
    )
    chapters = tuple(item for item in acquired if item is not None)
    successful: dict[str, list[int]] = {
        book_id: [] for book_id in registry[source_id].expected_source_books
    }
    for (book_id, chapter, _url), artifact in zip(candidates, acquired, strict=True):
        if artifact is not None:
            successful[book_id].append(chapter)
    for book_id, plan in chapter_bounds.items():
        chapters_for_book = successful[book_id]
        if plan.expected_count == 0:
            if chapters_for_book:
                raise ValueError('acquired chapters do not match catalog-declared coverage.')
            continue
        if (
            len(chapters_for_book) != plan.expected_count
            or not chapters_for_book
            or chapters_for_book[0] != plan.first
            or chapters_for_book[-1] != plan.last
        ):
            raise ValueError('acquired chapters do not match catalog-declared coverage.')
    return (catalog, *chapters)


def _bounded_parallel_acquire(
    candidates: tuple[tuple[str, int, str], ...],
    operation: Callable[[tuple[str, int, str]], AcquiredArtifact],
    *,
    initial_bytes: int = 0,
    stop_event: Event | _CooperativeStop | None = None,
) -> tuple[AcquiredArtifact | None, ...]:
    """Keep at most eight operations in flight and stop queueing on first failure."""
    if not candidates:
        raise ValueError('catalog must declare at least one bounded chapter candidate.')
    results: list[AcquiredArtifact | None] = [None] * len(candidates)
    executor = ThreadPoolExecutor(max_workers=min(8, len(candidates)))
    pending: dict[Future[AcquiredArtifact], int] = {}
    next_index = 0
    if type(initial_bytes) is not int or initial_bytes < 0 or initial_bytes > MAX_SOURCE_BYTES:
        raise ValueError('commentary source exceeds the aggregate byte limit.')
    total_bytes = initial_bytes
    cooperative_stop = stop_event or _CooperativeStop()
    failure_lock = Lock()
    primary_failure: list[Exception] = []

    def run_one(candidate: tuple[str, int, str]) -> AcquiredArtifact:
        try:
            return operation(candidate)
        except _MissingChapter:
            raise
        except _AcquisitionStopped:
            raise
        except Exception as exc:
            with failure_lock:
                if not primary_failure:
                    primary_failure.append(exc)
            cooperative_stop.set()
            raise

    def submit_one() -> None:
        nonlocal next_index
        future = executor.submit(run_one, candidates[next_index])
        pending[future] = next_index
        next_index += 1

    try:
        while next_index < min(8, len(candidates)):
            submit_one()
        while pending:
            completed, _waiting = wait(tuple(pending), return_when=FIRST_COMPLETED)
            completed_items = sorted(
                ((pending.pop(future), future) for future in completed),
                key=lambda item: item[0],
            )
            for index, future in completed_items:
                try:
                    artifact = future.result()
                except _MissingChapter:
                    artifact = None
                results[index] = artifact
                if artifact is not None:
                    total_bytes += artifact.size
                    if total_bytes > MAX_SOURCE_BYTES:
                        raise ValueError('commentary source exceeds the aggregate byte limit.')
            while next_index < len(candidates) and len(pending) < 8:
                submit_one()
    except Exception as caught:
        cooperative_stop.set()
        for future in pending:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        if isinstance(caught, _AcquisitionStopped) and primary_failure:
            raise primary_failure[0]
        raise
    else:
        executor.shutdown(wait=True, cancel_futures=True)
    return tuple(results)
