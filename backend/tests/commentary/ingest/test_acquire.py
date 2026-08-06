from __future__ import annotations

from email.message import Message
from hashlib import sha256
import io
import json
from pathlib import Path
import socket
import ssl
from urllib.error import URLError

import pytest


def test_default_opener_uses_certifi_with_certificate_and_hostname_verification(monkeypatch):
    from app.commentary.ingest import acquire

    calls = {}

    class Context:
        check_hostname = True
        verify_mode = ssl.CERT_REQUIRED

    context = Context()

    def create_default_context(*, cafile):
        calls['cafile'] = cafile
        return context

    class Handler:
        def __init__(self, *, context):
            calls['context'] = context

    class Opener:
        open = object()

    monkeypatch.setattr(acquire.ssl, 'create_default_context', create_default_context)
    monkeypatch.setattr(acquire, 'HTTPSHandler', Handler)
    monkeypatch.setattr(acquire, 'build_opener', lambda *handlers: (
        calls.setdefault('handlers', handlers), Opener()
    )[1])

    opener = acquire._default_opener('matthew-henry', acquire._registry())

    assert calls['cafile'] == acquire.certifi.where()
    assert calls['context'] is context
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert opener is Opener.open


class Response(io.BytesIO):
    def __init__(self, body: bytes, *, url: str, status: int = 200, headers=None):
        super().__init__(body)
        self.status = status
        self._url = url
        self.headers = Message()
        for name, value in (headers or {'Content-Type': 'application/json'}).items():
            self.headers[name] = value

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def _acquire_chapter(*args, **kwargs):
    from app.commentary.ingest.acquire import _ChapterPlan, acquire_source

    kwargs.setdefault('chapter_bounds', {'GEN': _ChapterPlan(1, 1, 1)})
    return acquire_source(*args, **kwargs)


def test_acquire_rejects_unapproved_host(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    with pytest.raises(ValueError, match='approved host'):
        _acquire_chapter('matthew-henry', 'https://example.com/data.json', tmp_path)


@pytest.mark.parametrize('url', [
    'http://bible.helloao.org/api/c/matthew-henry/books.json',
    'https://bible.helloao.org/other/c/matthew-henry/books.json',
    'https://bible.helloao.org/api/c/john-gill/books.json',
    'https://bible.helloao.org/api/c/matthew-henry/../../secrets.json',
    'https://bible.helloao.org/api/c/matthew-henry/SNG.json',
    'https://bible.helloao.org/api/c/matthew-henry/GEN.json',
    'https://bible.helloao.org/api/c/matthew-henry/GEN/0.json',
    'https://bible.helloao.org/api/c/matthew-henry/GEN/01.json',
    'https://bible.helloao.org/api/c/matthew-henry/GEN/2.json',
])
def test_acquire_rejects_unapproved_scheme_path_source_and_book(tmp_path, url):
    from app.commentary.ingest.acquire import acquire_source

    with pytest.raises(ValueError):
        _acquire_chapter('matthew-henry', url, tmp_path)


def test_acquire_writes_valid_json_atomically_with_checksum_sidecar(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    body = json.dumps({'ok': True}).encode()
    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    calls = []

    def opener(request, *, timeout):
        calls.append((request, timeout))
        return Response(body, url=url, headers={
            'Content-Type': 'application/json; charset=utf-8',
            'Content-Length': str(len(body)),
        })

    artifact = _acquire_chapter('matthew-henry', url, tmp_path, opener=opener)

    assert calls[0][1] == 10
    assert artifact.path == (
        tmp_path / 'matthew-henry' / 'generations' / 'GEN-1.json'
        / artifact.checksum / 'GEN-1.json'
    )
    assert artifact.path.read_bytes() == body
    assert artifact.checksum == sha256(body).hexdigest()
    assert artifact.sidecar.read_text(encoding='ascii') == f'{artifact.checksum}  GEN-1.json\n'
    assert not artifact.path.with_name('GEN-1.json.part').exists()


def test_acquire_resumes_a_safe_partial_file(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    target_dir = tmp_path / 'matthew-henry'
    target_dir.mkdir()
    part = target_dir / 'GEN-1.json.part'
    part.write_bytes(b'{"ok"')
    (target_dir / 'GEN-1.json.part.meta').write_text(
        json.dumps({'url': url, 'etag': '"v1"'}), encoding='utf-8',
    )
    tail = b':true}'

    def opener(request, *, timeout):
        assert request.headers['Range'] == 'bytes=5-'
        assert request.headers['If-range'] == '"v1"'
        return Response(tail, url=url, status=206, headers={
            'Content-Type': 'application/json',
            'Content-Length': str(len(tail)),
            'Content-Range': 'bytes 5-10/11',
            'ETag': '"v1"',
        })

    artifact = _acquire_chapter('matthew-henry', url, tmp_path, opener=opener)
    assert artifact.path.read_bytes() == b'{"ok":true}'


def test_acquire_restarts_when_server_ignores_range(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    target_dir = tmp_path / 'matthew-henry'
    target_dir.mkdir()
    (target_dir / 'GEN-1.json.part').write_bytes(b'garbage')
    (target_dir / 'GEN-1.json.part.meta').write_text(
        json.dumps({'url': url, 'etag': '"v1"'}), encoding='utf-8',
    )
    body = b'{"fresh":true}'

    def opener(request, *, timeout):
        assert request.headers['Range'] == 'bytes=7-'
        assert request.headers['If-range'] == '"v1"'
        return Response(body, url=url, status=200, headers={
            'Content-Type': 'application/json', 'ETag': '"v2"',
        })

    artifact = _acquire_chapter('matthew-henry', url, tmp_path, opener=opener)
    assert artifact.path.read_bytes() == body


@pytest.mark.parametrize('headers,body,error', [
    ({'Content-Type': 'text/html'}, b'{}', 'JSON content type'),
    ({'Content-Type': 'application/json'}, b'{bad', 'valid JSON'),
    ({'Content-Type': 'application/json'}, b'{"x":1,"x":2}', 'duplicate JSON'),
    ({'Content-Type': 'application/json', 'Content-Length': str(5 * 1024 * 1024 + 1)}, b'{}', '5 MiB'),
])
def test_acquire_rejects_unsafe_responses_without_final_artifacts(tmp_path, headers, body, error):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'

    def opener(request, *, timeout):
        return Response(body, url=url, headers=headers)

    with pytest.raises(ValueError, match=error):
        _acquire_chapter('matthew-henry', url, tmp_path, opener=opener)
    destination = tmp_path / 'matthew-henry'
    assert not (destination / 'GEN-1.json').exists()
    assert not (destination / 'GEN-1.json.sha256').exists()


def test_acquire_enforces_streaming_cap_including_resumed_bytes(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    directory = tmp_path / 'matthew-henry'
    directory.mkdir()
    (directory / 'GEN-1.json.part').write_bytes(b'x' * (5 * 1024 * 1024))
    (directory / 'GEN-1.json.part.meta').write_text(
        json.dumps({'url': url, 'etag': '"v1"'}), encoding='utf-8',
    )

    def opener(request, *, timeout):
        return Response(b'x', url=url, status=206, headers={
            'Content-Type': 'application/json',
            'Content-Range': f'bytes {5 * 1024 * 1024}-{5 * 1024 * 1024}/{5 * 1024 * 1024 + 1}',
            'ETag': '"v1"',
        })

    with pytest.raises(ValueError, match='5 MiB'):
        _acquire_chapter('matthew-henry', url, tmp_path, opener=opener)


def test_acquire_retries_three_times_with_injected_sleeper(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    attempts = 0
    delays = []

    def opener(request, *, timeout):
        nonlocal attempts
        attempts += 1
        raise URLError(socket.timeout('timed out'))

    with pytest.raises(ValueError, match='three attempts'):
        _acquire_chapter('matthew-henry', url, tmp_path, opener=opener, sleeper=delays.append)
    assert attempts == 3
    assert delays == [1.0, 2.0]


def test_acquire_rejects_redirected_final_url(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'

    def opener(request, *, timeout):
        return Response(b'{}', url='https://evil.example/GEN-1.json')

    with pytest.raises(ValueError, match='redirect'):
        _acquire_chapter('matthew-henry', url, tmp_path, opener=opener)


def test_acquire_rejects_symlink_output_and_special_part(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    real = tmp_path / 'real'
    real.mkdir()
    output = tmp_path / 'output'
    output.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        _acquire_chapter('matthew-henry', url, output)

    output.unlink()
    output.mkdir()
    source = output / 'matthew-henry'
    source.mkdir()
    (source / 'GEN-1.json.part').symlink_to(tmp_path / 'missing')
    with pytest.raises(ValueError, match='regular file'):
        _acquire_chapter('matthew-henry', url, output)


def _reviewed_catalog(tmp_path, checksum):
    path = tmp_path / 'reviewed-artifacts.json'
    path.write_text(json.dumps({
        'schema_version': 1,
        'sources': {'matthew-henry': {'artifacts': {'books.json': {
            'url': 'https://bible.helloao.org/api/c/matthew-henry/books.json',
            'sha256': checksum,
        }}}},
    }), encoding='utf-8')
    return path


def test_catalog_artifact_digest_is_not_conflated_with_provider_dataset_digest(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/books.json'
    body = b'{}'
    reviewed = _reviewed_catalog(tmp_path, sha256(body).hexdigest())

    def opener(request, *, timeout):
        return Response(body, url=url)

    artifact = _acquire_chapter(
        'matthew-henry', url, tmp_path / 'raw', opener=opener,
        reviewed_artifacts_path=reviewed,
    )

    assert artifact.checksum == sha256(body).hexdigest()
    assert artifact.checksum != (
        acquire_source.__globals__['_registry']()['matthew-henry']
        .provider_dataset_checksum
    )


def test_catalog_checksum_mismatch_leaves_no_final_artifacts(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/books.json'
    output = tmp_path / 'raw'
    reviewed = _reviewed_catalog(tmp_path, 'a' * 64)

    def opener(request, *, timeout):
        return Response(b'{}', url=url)

    with pytest.raises(ValueError, match='reviewed artifact checksum'):
        _acquire_chapter(
            'matthew-henry', url, output, opener=opener,
            reviewed_artifacts_path=reviewed,
        )
    source = output / 'matthew-henry'
    assert not (source / 'books.json').exists()
    assert not (source / 'books.json.sha256').exists()


def test_bundle_acquisition_requests_only_registry_artifacts(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    calls = []

    def fake_acquire(source_id, url, output, **options):
        calls.append((source_id, url))
        return acquire.AcquiredArtifact(
            tmp_path / 'x', tmp_path / 'x.sha256', 'a' * 64, 2, url,
        )

    monkeypatch.setattr(acquire, 'acquire_source', fake_acquire)
    registry = acquire._registry()
    expected = registry['keil-delitzsch'].expected_source_books
    monkeypatch.setattr(
        acquire, 'read_acquired_artifact',
        lambda *_args, **_kwargs: (
            b'{}', 'a' * 64, registry['keil-delitzsch'].upstream_url,
        ),
    )
    monkeypatch.setattr(
        acquire, '_catalog_chapter_bounds',
        lambda *_args: {book: acquire._ChapterPlan(1, 1, 1) for book in expected},
    )
    artifacts = acquire.acquire_source_bundle('keil-delitzsch', tmp_path)
    assert len(artifacts) == len(expected) + 1
    assert artifacts[0].url == registry['keil-delitzsch'].upstream_url
    assert [artifact.url for artifact in artifacts[1:]] == [
        f'https://bible.helloao.org/api/c/keil-delitzsch/{book}/1.json'
        for book in expected
    ]
    assert all(not artifact.url.endswith(f'/{book}.json') for artifact, book in zip(
        artifacts[1:], expected, strict=True,
    ))


def test_bundle_acquisition_accepts_only_count_verified_internal_404_gap(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    registry = acquire._registry()
    expected = registry['keil-delitzsch'].expected_source_books

    def fake_acquire(source_id, url, output, **options):
        if url.endswith('/GEN/2.json'):
            raise acquire._MissingChapter('declared candidate gap')
        return acquire.AcquiredArtifact(
            tmp_path / url.rsplit('/', 1)[-1], tmp_path / 'x.sha256',
            'a' * 64, 2, url,
        )

    plans = {book: acquire._ChapterPlan(1, 1, 1) for book in expected}
    plans['GEN'] = acquire._ChapterPlan(1, 3, 2)
    monkeypatch.setattr(acquire, 'acquire_source', fake_acquire)
    monkeypatch.setattr(
        acquire, 'read_acquired_artifact',
        lambda *_args, **_kwargs: (
            b'{}', 'a' * 64, registry['keil-delitzsch'].upstream_url,
        ),
    )
    monkeypatch.setattr(acquire, '_catalog_chapter_bounds', lambda *_args: plans)

    artifacts = acquire.acquire_source_bundle('keil-delitzsch', tmp_path)

    urls = [artifact.url for artifact in artifacts]
    assert not any(url.endswith('/GEN/2.json') for url in urls)
    assert any(url.endswith('/GEN/1.json') for url in urls)
    assert any(url.endswith('/GEN/3.json') for url in urls)
    assert len(artifacts) == 1 + sum(plan.expected_count for plan in plans.values())


def test_bundle_acquisition_rejects_unexpected_404_coverage_loss(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    registry = acquire._registry()
    expected = registry['keil-delitzsch'].expected_source_books

    def fake_acquire(source_id, url, output, **options):
        if url.endswith('/GEN/2.json'):
            raise acquire._MissingChapter('unexpected gap')
        return acquire.AcquiredArtifact(tmp_path / 'x', tmp_path / 'y', 'a' * 64, 1, url)

    plans = {book: acquire._ChapterPlan(1, 1, 1) for book in expected}
    plans['GEN'] = acquire._ChapterPlan(1, 3, 3)
    monkeypatch.setattr(acquire, 'acquire_source', fake_acquire)
    monkeypatch.setattr(
        acquire, 'read_acquired_artifact',
        lambda *_args, **_kwargs: (b'{}', 'a' * 64, registry['keil-delitzsch'].upstream_url),
    )
    monkeypatch.setattr(acquire, '_catalog_chapter_bounds', lambda *_args: plans)

    with pytest.raises(ValueError, match='catalog-declared coverage'):
        acquire.acquire_source_bundle('keil-delitzsch', tmp_path)


def test_catalog_bounds_accept_declared_gap_and_enforce_caps():
    from app.commentary.ingest import acquire

    def catalog(*, count=67, last=68):
        return json.dumps({
            'commentary': {
                'id': 'matthew-henry', 'listOfBooksApiLink':
                '/api/c/matthew-henry/books.json', 'numberOfBooks': 1,
                'totalNumberOfChapters': count,
            },
            'books': [{
                'id': 'ISA', 'commentaryId': 'matthew-henry',
                'numberOfChapters': count, 'firstChapterNumber': 1,
                'lastChapterNumber': last,
                'firstChapterApiLink': '/api/c/matthew-henry/ISA/1.json',
                'lastChapterApiLink': f'/api/c/matthew-henry/ISA/{last}.json',
            }],
        }).encode()

    plan = acquire._catalog_chapter_bounds(
        catalog(), 'matthew-henry', ('ISA',),
    )['ISA']
    assert (plan.first, plan.last, plan.expected_count) == (1, 68, 67)

    with pytest.raises(ValueError, match='invalid source, chapter bounds, or links'):
        acquire._catalog_chapter_bounds(
            catalog(count=200, last=201), 'matthew-henry', ('ISA',),
        )


def test_catalog_bounds_accept_real_zero_chapter_book_shape_without_candidate():
    from app.commentary.ingest import acquire

    raw = json.dumps({
        'commentary': {
            'id': 'keil-delitzsch',
            'listOfBooksApiLink': '/api/c/keil-delitzsch/books.json',
            'numberOfBooks': 2, 'totalNumberOfChapters': 1,
        },
        'books': [{
            'id': 'GEN', 'commentaryId': 'keil-delitzsch',
            'numberOfChapters': 1, 'firstChapterNumber': 1,
            'lastChapterNumber': 1,
            'firstChapterApiLink': '/api/c/keil-delitzsch/GEN/1.json',
            'lastChapterApiLink': '/api/c/keil-delitzsch/GEN/1.json',
        }, {
            'id': 'SNG', 'commentaryId': 'keil-delitzsch',
            'numberOfChapters': 0, 'firstChapterNumber': None,
            'lastChapterNumber': None, 'firstChapterApiLink': None,
            'lastChapterApiLink': None, 'firstChapterReference': None,
            'lastChapterReference': None,
        }],
    }).encode()

    plans = acquire._catalog_chapter_bounds(
        raw, 'keil-delitzsch', ('GEN', 'SNG'),
    )

    assert tuple(plans) == ('GEN', 'SNG')
    assert plans['SNG'] == acquire._ChapterPlan(None, None, 0)


@pytest.mark.parametrize(('field', 'value'), [
    ('numberOfChapters', -1),
    ('numberOfChapters', 1),
    ('firstChapterNumber', 1),
    ('lastChapterNumber', 1),
    ('firstChapterApiLink', '/api/c/keil-delitzsch/SNG/1.json'),
    ('lastChapterApiLink', '/api/c/keil-delitzsch/SNG/1.json'),
    ('firstChapterReference', {
        'commentaryId': 'keil-delitzsch', 'book': 'SNG', 'chapter': 1,
    }),
    ('lastChapterReference', {
        'commentaryId': 'keil-delitzsch', 'book': 'SNG', 'chapter': 1,
    }),
])
def test_catalog_bounds_reject_invalid_or_partial_zero_chapter_shape(field, value):
    from app.commentary.ingest import acquire

    book = {
        'id': 'SNG', 'commentaryId': 'keil-delitzsch',
        'numberOfChapters': 0, 'firstChapterNumber': None,
        'lastChapterNumber': None, 'firstChapterApiLink': None,
        'lastChapterApiLink': None, 'firstChapterReference': None,
        'lastChapterReference': None,
    }
    book[field] = value
    raw = json.dumps({
        'commentary': {
            'id': 'keil-delitzsch',
            'listOfBooksApiLink': '/api/c/keil-delitzsch/books.json',
            'numberOfBooks': 1, 'totalNumberOfChapters': 0,
        },
        'books': [book],
    }).encode()

    with pytest.raises(ValueError, match='invalid source, chapter bounds, or links'):
        acquire._catalog_chapter_bounds(raw, 'keil-delitzsch', ('SNG',))


@pytest.mark.parametrize('missing_field', [
    'firstChapterNumber', 'lastChapterNumber',
    'firstChapterApiLink', 'lastChapterApiLink',
    'firstChapterReference', 'lastChapterReference',
])
def test_catalog_bounds_reject_zero_chapter_shape_with_missing_field(missing_field):
    from app.commentary.ingest import acquire

    book = {
        'id': 'SNG', 'commentaryId': 'keil-delitzsch',
        'numberOfChapters': 0, 'firstChapterNumber': None,
        'lastChapterNumber': None, 'firstChapterApiLink': None,
        'lastChapterApiLink': None, 'firstChapterReference': None,
        'lastChapterReference': None,
    }
    del book[missing_field]
    raw = json.dumps({
        'commentary': {
            'id': 'keil-delitzsch',
            'listOfBooksApiLink': '/api/c/keil-delitzsch/books.json',
            'numberOfBooks': 1, 'totalNumberOfChapters': 0,
        },
        'books': [book],
    }).encode()

    with pytest.raises(ValueError, match='invalid source, chapter bounds, or links'):
        acquire._catalog_chapter_bounds(raw, 'keil-delitzsch', ('SNG',))


def test_bundle_acquisition_does_not_schedule_zero_chapter_book(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    calls = []
    registry = acquire._registry()
    expected = registry['keil-delitzsch'].expected_source_books
    plans = {book: acquire._ChapterPlan(1, 1, 1) for book in expected}
    plans['SNG'] = acquire._ChapterPlan(None, None, 0)

    def fake_acquire(source_id, url, output, **options):
        calls.append(url)
        return acquire.AcquiredArtifact(tmp_path / 'x', tmp_path / 'y', 'a' * 64, 1, url)

    monkeypatch.setattr(acquire, 'acquire_source', fake_acquire)
    monkeypatch.setattr(
        acquire, 'read_acquired_artifact',
        lambda *_args, **_kwargs: (b'{}', 'a' * 64, registry['keil-delitzsch'].upstream_url),
    )
    monkeypatch.setattr(acquire, '_catalog_chapter_bounds', lambda *_args: plans)

    artifacts = acquire.acquire_source_bundle('keil-delitzsch', tmp_path)

    assert not any('/SNG/' in url for url in calls)
    assert len(artifacts) == len(expected)


def test_bounded_parallel_acquisition_preserves_order_and_caps_workers(tmp_path):
    from app.commentary.ingest import acquire
    import threading
    import time

    lock = threading.Lock()
    active = 0
    maximum = 0
    candidates = tuple(('GEN', index + 1, f'https://example.test/{index}') for index in range(20))

    def operation(candidate):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.002)
        with lock:
            active -= 1
        url = candidate[2]
        return acquire.AcquiredArtifact(
            tmp_path / url.rsplit('/', 1)[-1], tmp_path / 'x.sha256', 'a' * 64, 2, url,
        )

    artifacts = acquire._bounded_parallel_acquire(candidates, operation)

    assert maximum <= 8
    assert [artifact.url for artifact in artifacts] == [item[2] for item in candidates]


def test_bounded_parallel_acquisition_stops_submitting_after_first_failure(tmp_path):
    from app.commentary.ingest import acquire
    import threading
    import time

    lock = threading.Lock()
    started = []
    candidates = tuple(('GEN', index + 1, f'https://example.test/{index}') for index in range(100))

    def operation(candidate):
        with lock:
            started.append(candidate[1])
        if candidate[1] == 1:
            raise ValueError('stop')
        time.sleep(0.02)
        return acquire.AcquiredArtifact(tmp_path / 'x', tmp_path / 'y', 'a' * 64, 1, candidate[2])

    with pytest.raises(ValueError, match='stop'):
        acquire._bounded_parallel_acquire(candidates, operation)

    assert len(started) <= 8


def test_bounded_parallel_acquisition_enforces_aggregate_source_bytes(tmp_path):
    from app.commentary.ingest import acquire

    candidate = (('GEN', 1, 'https://example.test/1'),)
    artifact = acquire.AcquiredArtifact(
        tmp_path / 'x', tmp_path / 'y', 'a' * 64, 2, candidate[0][2],
    )

    with pytest.raises(ValueError, match='aggregate byte limit'):
        acquire._bounded_parallel_acquire(
            candidate, lambda _candidate: artifact,
            initial_bytes=acquire.MAX_SOURCE_BYTES - 1,
        )


def test_concurrent_acquisition_reserves_bytes_before_any_generation_finalizes(tmp_path):
    from app.commentary.ingest import acquire
    import threading

    source_id = 'matthew-henry'
    candidates = tuple(
        ('GEN', chapter, f'https://bible.helloao.org/api/c/{source_id}/GEN/{chapter}.json')
        for chapter in range(1, 9)
    )
    bounds = {'GEN': acquire._ChapterPlan(1, 8, 8)}
    all_active = threading.Barrier(8)
    stop = threading.Event()
    budget = acquire._SourceByteBudget(initial_bytes=1, limit=5)

    def opener(request, *, timeout):
        assert timeout == 10
        all_active.wait(timeout=2)
        return Response(b'{}', url=request.full_url)

    def operation(candidate):
        return acquire.acquire_source(
            source_id, candidate[2], tmp_path, opener=opener,
            chapter_bounds=bounds, _source_budget=budget, _stop_event=stop,
        )

    with pytest.raises(ValueError, match='aggregate byte limit'):
        acquire._bounded_parallel_acquire(
            candidates, operation, initial_bytes=1, stop_event=stop,
        )

    markers = tuple((tmp_path / source_id).glob('GEN-*.json.current.json'))
    assert 1 + 2 * len(markers) <= 5


def test_bundle_reserves_catalog_bytes_before_catalog_finalization(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    source_id = 'matthew-henry'
    url = acquire._registry()[source_id].upstream_url
    body = b'{}'
    reviewed = _reviewed_catalog(tmp_path, sha256(body).hexdigest())
    monkeypatch.setattr(acquire, 'MAX_SOURCE_BYTES', 1)

    with pytest.raises(ValueError, match='aggregate byte limit'):
        acquire.acquire_source_bundle(
            source_id, tmp_path / 'raw',
            opener=lambda *_args, **_kwargs: Response(body, url=url),
            reviewed_artifacts_path=reviewed,
        )

    source = tmp_path / 'raw' / source_id
    assert not (source / 'books.json.current.json').exists()


def test_first_worker_failure_stops_seven_active_workers_before_finalization(tmp_path):
    from app.commentary.ingest import acquire
    import threading

    source_id = 'matthew-henry'
    candidates = tuple(
        ('GEN', chapter, f'https://bible.helloao.org/api/c/{source_id}/GEN/{chapter}.json')
        for chapter in range(1, 9)
    )
    bounds = {'GEN': acquire._ChapterPlan(1, 8, 8)}
    held_lock = threading.Lock()
    seven_held = threading.Event()
    stop = threading.Event()
    held = 0

    def opener(request, *, timeout):
        nonlocal held
        chapter = int(request.full_url.rsplit('/', 1)[-1][:-5])
        if chapter == 1:
            assert seven_held.wait(timeout=2)
            raise ValueError('primary worker failure')
        with held_lock:
            held += 1
            if held == 7:
                seven_held.set()
        assert stop.wait(timeout=2)
        return Response(b'{}', url=request.full_url)

    def operation(candidate):
        return acquire.acquire_source(
            source_id, candidate[2], tmp_path, opener=opener,
            chapter_bounds=bounds, _source_budget=acquire._SourceByteBudget(),
            _stop_event=stop,
        )

    with pytest.raises(ValueError, match='primary worker failure'):
        acquire._bounded_parallel_acquire(candidates, operation, stop_event=stop)

    assert held == 7
    assert tuple((tmp_path / source_id).glob('GEN-*.json.current.json')) == ()


def test_failure_during_final_path_check_wins_before_authoritative_marker_switch(
    monkeypatch, tmp_path,
):
    from app.commentary.ingest import acquire
    import threading

    source_id = 'matthew-henry'
    candidates = tuple(
        ('GEN', chapter, f'https://bible.helloao.org/api/c/{source_id}/GEN/{chapter}.json')
        for chapter in range(1, 3)
    )
    bounds = {'GEN': acquire._ChapterPlan(1, 2, 2)}
    path_check_started = threading.Event()
    stop = acquire._CooperativeStop()
    budget = acquire._SourceByteBudget()
    real_path_check = acquire._path_still_identifies

    def held_path_check(path, descriptor):
        path_check_started.set()
        assert stop.wait(timeout=2)
        return real_path_check(path, descriptor)

    def opener(request, *, timeout):
        chapter = int(request.full_url.rsplit('/', 1)[-1][:-5])
        if chapter == 1:
            assert path_check_started.wait(timeout=2)
            raise ValueError('boundary worker failure')
        return Response(b'{}', url=request.full_url)

    def operation(candidate):
        return acquire.acquire_source(
            source_id, candidate[2], tmp_path, opener=opener,
            chapter_bounds=bounds, _source_budget=budget, _stop_event=stop,
        )

    monkeypatch.setattr(acquire, '_path_still_identifies', held_path_check)

    with pytest.raises(ValueError, match='boundary worker failure'):
        acquire._bounded_parallel_acquire(candidates, operation, stop_event=stop)

    assert tuple((tmp_path / source_id).glob('GEN-*.json.current.json')) == ()


def test_retry_resumes_from_bytes_persisted_before_read_timeout(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    directory = tmp_path / 'matthew-henry'
    directory.mkdir()
    (directory / 'GEN-1.json.part').write_bytes(b'{"ok"')
    (directory / 'GEN-1.json.part.meta').write_text(
        json.dumps({'url': url, 'etag': '"v1"'}), encoding='utf-8',
    )
    requests = []

    class Interrupted(Response):
        reads = 0

        def read(self, _size=-1):
            self.reads += 1
            if self.reads == 1:
                return b':'
            raise socket.timeout('read timed out')

    def opener(request, *, timeout):
        requests.append(request)
        if len(requests) == 1:
            return Interrupted(b'', url=url, status=206, headers={
                'Content-Type': 'application/json', 'Content-Range': 'bytes 5-5/6',
                'ETag': '"v1"',
            })
        assert request.headers['Range'] == 'bytes=6-'
        return Response(b'true}', url=url, status=206, headers={
            'Content-Type': 'application/json', 'Content-Range': 'bytes 6-10/11',
            'ETag': '"v1"',
        })

    artifact = _acquire_chapter(
        'matthew-henry', url, tmp_path, opener=opener, sleeper=lambda _delay: None,
    )
    assert artifact.path.read_bytes() == b'{"ok":true}'


@pytest.mark.parametrize('failure_point', ['sidecar', 'directory_fsync'])
def test_finalization_failure_removes_both_final_artifacts(monkeypatch, tmp_path, failure_point):
    from app.commentary.ingest import acquire

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'

    def opener(request, *, timeout):
        return Response(b'{"ok":true}', url=url, headers={
            'Content-Type': 'application/json', 'ETag': '"v1"',
        })

    if failure_point == 'sidecar':
        monkeypatch.setattr(
            acquire, '_write_sidecar',
            lambda *_args: (_ for _ in ()).throw(OSError('sidecar failed')),
        )
    else:
        monkeypatch.setattr(
            acquire, '_fsync_directory',
            lambda *_args: (_ for _ in ()).throw(OSError('directory fsync failed')),
        )

    with pytest.raises(OSError):
        _acquire_chapter('matthew-henry', url, tmp_path, opener=opener)
    directory = tmp_path / 'matthew-henry'
    assert not (directory / 'GEN-1.json').exists()
    assert not (directory / 'GEN-1.json.sha256').exists()
    assert list(directory.glob('GEN-1.json*.part*')) == []


def test_partial_bytes_are_fsynced_before_retry(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    fsync_calls = []
    real_fsync = acquire.os.fsync
    attempts = 0

    class Interrupted(Response):
        reads = 0

        def read(self, _size=-1):
            self.reads += 1
            if self.reads == 1:
                return b'{'
            raise socket.timeout('read timed out')

    def tracking_fsync(descriptor):
        fsync_calls.append(descriptor)
        return real_fsync(descriptor)

    def opener(request, *, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return Interrupted(b'', url=url, headers={
                'Content-Type': 'application/json', 'ETag': '"v1"',
            })
        assert request.headers['Range'] == 'bytes=1-'
        assert request.headers['If-range'] == '"v1"'
        return Response(b'"ok":true}', url=url, status=206, headers={
            'Content-Type': 'application/json', 'ETag': '"v1"',
            'Content-Range': 'bytes 1-10/11',
        })

    monkeypatch.setattr(acquire.os, 'fsync', tracking_fsync)

    def sleeper(_delay):
        assert fsync_calls, 'partial descriptor was not fsynced before retry delay'

    artifact = _acquire_chapter(
        'matthew-henry', url, tmp_path, opener=opener, sleeper=sleeper,
    )
    assert artifact.path.read_bytes() == b'{"ok":true}'


def test_changed_etag_on_partial_response_restarts_from_zero(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    directory = tmp_path / 'matthew-henry'
    directory.mkdir()
    (directory / 'GEN-1.json.part').write_bytes(b'{"old"')
    (directory / 'GEN-1.json.part.meta').write_text(
        json.dumps({'url': url, 'etag': '"v1"'}), encoding='utf-8',
    )
    attempts = 0

    def opener(request, *, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            assert request.headers['If-range'] == '"v1"'
            return Response(b':false}', url=url, status=206, headers={
                'Content-Type': 'application/json', 'ETag': '"v2"',
                'Content-Range': 'bytes 6-12/13',
            })
        assert 'Range' not in request.headers
        return Response(b'{"fresh":true}', url=url, headers={
            'Content-Type': 'application/json', 'ETag': '"v2"',
        })

    artifact = _acquire_chapter(
        'matthew-henry', url, tmp_path, opener=opener, sleeper=lambda _delay: None,
    )
    assert artifact.path.read_bytes() == b'{"fresh":true}'


def test_failed_reacquisition_preserves_the_known_good_generation(tmp_path):
    from app.commentary.ingest.acquire import acquire_source, read_acquired_artifact

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    first = b'{"generation":1}'
    _acquire_chapter(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(first, url=url, headers={
            'Content-Type': 'application/json', 'ETag': '"v1"',
        }),
    )

    with pytest.raises(ValueError, match='valid JSON'):
        _acquire_chapter(
            'matthew-henry', url, tmp_path,
            opener=lambda *_args, **_kwargs: Response(b'{bad', url=url, headers={
                'Content-Type': 'application/json', 'ETag': '"v2"',
            }),
        )

    raw, digest, acquired_url = read_acquired_artifact(
        tmp_path / 'matthew-henry', 'GEN-1.json', source_id='matthew-henry',
    )
    assert raw == first
    assert digest == sha256(first).hexdigest()
    assert acquired_url == url


@pytest.mark.parametrize('checkpoint', [
    'generation_data', 'generation_sidecar', 'before_marker_switch',
    'after_marker_switch', 'directory_fsync',
])
def test_failure_at_each_generation_switch_step_restores_previous(
    tmp_path, checkpoint,
):
    from app.commentary.ingest.acquire import acquire_source, read_acquired_artifact

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    old = b'{"generation":"old"}'
    _acquire_chapter(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(old, url=url),
    )

    def hook(step):
        if step == checkpoint:
            raise OSError(f'injected {step}')

    with pytest.raises(OSError, match='injected'):
        _acquire_chapter(
            'matthew-henry', url, tmp_path,
            opener=lambda *_args, **_kwargs: Response(b'{"generation":"new"}', url=url),
            finalization_hook=hook,
        )
    assert read_acquired_artifact(
        tmp_path / 'matthew-henry', 'GEN-1.json', source_id='matthew-henry',
    )[0] == old


def test_unreferenced_incomplete_generation_does_not_replace_current(tmp_path):
    from app.commentary.ingest.acquire import acquire_source, read_acquired_artifact

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    trusted = b'{"trusted":true}'
    _acquire_chapter(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(trusted, url=url),
    )
    stale = tmp_path / 'matthew-henry' / 'generations' / 'GEN-1.json' / ('f' * 64)
    stale.mkdir(parents=True)
    (stale / 'artifact.json').write_text('{"incomplete":true}', encoding='utf-8')

    assert read_acquired_artifact(
        tmp_path / 'matthew-henry', 'GEN-1.json', source_id='matthew-henry',
    )[0] == trusted


def test_output_directory_swap_cannot_redirect_authoritative_marker(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    output = tmp_path / 'output'
    attacker = tmp_path / 'attacker'
    attacker.mkdir()

    def swap(step):
        if step == 'before_marker_switch':
            (output / 'matthew-henry').rename(output / 'original-source')
            (output / 'matthew-henry').symlink_to(attacker, target_is_directory=True)

    with pytest.raises(ValueError, match='changed during finalization'):
        _acquire_chapter(
            'matthew-henry', url, output,
            opener=lambda *_args, **_kwargs: Response(b'{"safe":true}', url=url),
            finalization_hook=swap,
        )

    assert list(attacker.iterdir()) == []
    assert not (output / 'original-source' / 'GEN-1.json.current.json').exists()


@pytest.mark.parametrize('swap_level', ['source', 'ancestor'])
def test_network_callback_swap_cannot_redirect_partial_files(tmp_path, swap_level):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    output = tmp_path / 'output'
    attacker = tmp_path / 'attacker'
    attacker_source = attacker / 'matthew-henry'
    attacker_source.mkdir(parents=True)
    hostile_part = attacker_source / 'GEN-1.json.part'
    hostile_meta = attacker_source / 'GEN-1.json.part.meta'
    hostile_part.write_bytes(b'hostile-part')
    hostile_meta.write_bytes(b'hostile-meta')

    def opener(_request, *, timeout):
        assert timeout == 10
        if swap_level == 'source':
            (output / 'matthew-henry').rename(output / 'original-source')
            (output / 'matthew-henry').symlink_to(
                attacker_source, target_is_directory=True,
            )
        else:
            output.rename(tmp_path / 'original-output')
            output.symlink_to(attacker, target_is_directory=True)
        return Response(b'{"safe":true}', url=url, headers={
            'Content-Type': 'application/json', 'ETag': '"v1"',
        })

    with pytest.raises(ValueError, match='changed during finalization'):
        _acquire_chapter('matthew-henry', url, output, opener=opener)

    assert hostile_part.read_bytes() == b'hostile-part'
    assert hostile_meta.read_bytes() == b'hostile-meta'


def test_fresh_generation_fsyncs_each_new_parent_before_marker(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    body = b'{"durable":true}'
    digest = sha256(body).hexdigest()
    events = []

    def track(descriptor):
        info = acquire.os.fstat(descriptor)
        candidates = {
            'output': tmp_path,
            'source': tmp_path / 'matthew-henry',
            'generations': tmp_path / 'matthew-henry' / 'generations',
            'artifact-root': tmp_path / 'matthew-henry' / 'generations' / 'GEN-1.json',
            'generation': (
                tmp_path / 'matthew-henry' / 'generations' / 'GEN-1.json' / digest
            ),
        }
        for label, path in candidates.items():
            if path.exists():
                current = path.stat()
                if (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino):
                    events.append(label)
                    return
        raise AssertionError('unexpected directory fsync')

    monkeypatch.setattr(acquire, '_fsync_directory', track)
    _acquire_chapter(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(body, url=url),
    )

    assert events == [
        'output', 'source', 'generations', 'artifact-root', 'generation', 'source',
    ]


def test_existing_generation_only_fsyncs_contents_and_marker_parent(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    body = b'{"durable":true}'
    _acquire_chapter(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(body, url=url),
    )
    events = []
    source = tmp_path / 'matthew-henry'
    generation = source / 'generations' / 'GEN-1.json' / sha256(body).hexdigest()

    def track(descriptor):
        info = acquire.os.fstat(descriptor)
        for label, path in (('generation', generation), ('source', source)):
            current = path.stat()
            if (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino):
                events.append(label)
                return
        raise AssertionError('existing parent was unnecessarily fsynced')

    monkeypatch.setattr(acquire, '_fsync_directory', track)
    _acquire_chapter(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(body, url=url),
    )

    assert events == ['generation', 'source']
