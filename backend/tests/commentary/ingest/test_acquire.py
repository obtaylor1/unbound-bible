from __future__ import annotations

from email.message import Message
from hashlib import sha256
import io
import json
from pathlib import Path
import socket
from urllib.error import URLError

import pytest


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


def test_acquire_rejects_unapproved_host(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    with pytest.raises(ValueError, match='approved host'):
        acquire_source('matthew-henry', 'https://example.com/data.json', tmp_path)


@pytest.mark.parametrize('url', [
    'http://bible.helloao.org/api/c/matthew-henry/books.json',
    'https://bible.helloao.org/other/c/matthew-henry/books.json',
    'https://bible.helloao.org/api/c/john-gill/books.json',
    'https://bible.helloao.org/api/c/matthew-henry/../../secrets.json',
    'https://bible.helloao.org/api/c/matthew-henry/SNG.json',
])
def test_acquire_rejects_unapproved_scheme_path_source_and_book(tmp_path, url):
    from app.commentary.ingest.acquire import acquire_source

    with pytest.raises(ValueError):
        acquire_source('matthew-henry', url, tmp_path)


def test_acquire_writes_valid_json_atomically_with_checksum_sidecar(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    body = json.dumps({'ok': True}).encode()
    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    calls = []

    def opener(request, *, timeout):
        calls.append((request, timeout))
        return Response(body, url=url, headers={
            'Content-Type': 'application/json; charset=utf-8',
            'Content-Length': str(len(body)),
        })

    artifact = acquire_source('matthew-henry', url, tmp_path, opener=opener)

    assert calls[0][1] == 10
    assert artifact.path == tmp_path / 'matthew-henry' / 'GEN.json'
    assert artifact.path.read_bytes() == body
    assert artifact.checksum == sha256(body).hexdigest()
    assert artifact.sidecar.read_text(encoding='ascii') == f'{artifact.checksum}  GEN.json\n'
    assert not artifact.path.with_name('GEN.json.part').exists()


def test_acquire_resumes_a_safe_partial_file(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    target_dir = tmp_path / 'matthew-henry'
    target_dir.mkdir()
    part = target_dir / 'GEN.json.part'
    part.write_bytes(b'{"ok"')
    tail = b':true}'

    def opener(request, *, timeout):
        assert request.headers['Range'] == 'bytes=5-'
        return Response(tail, url=url, status=206, headers={
            'Content-Type': 'application/json',
            'Content-Length': str(len(tail)),
            'Content-Range': 'bytes 5-10/11',
        })

    artifact = acquire_source('matthew-henry', url, tmp_path, opener=opener)
    assert artifact.path.read_bytes() == b'{"ok":true}'


def test_acquire_restarts_when_server_ignores_range(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    target_dir = tmp_path / 'matthew-henry'
    target_dir.mkdir()
    (target_dir / 'GEN.json.part').write_bytes(b'garbage')
    body = b'{"fresh":true}'

    def opener(request, *, timeout):
        assert request.headers['Range'] == 'bytes=7-'
        return Response(body, url=url, status=200, headers={'Content-Type': 'application/json'})

    artifact = acquire_source('matthew-henry', url, tmp_path, opener=opener)
    assert artifact.path.read_bytes() == body


@pytest.mark.parametrize('headers,body,error', [
    ({'Content-Type': 'text/html'}, b'{}', 'JSON content type'),
    ({'Content-Type': 'application/json'}, b'{bad', 'valid JSON'),
    ({'Content-Type': 'application/json'}, b'{"x":1,"x":2}', 'duplicate JSON'),
    ({'Content-Type': 'application/json', 'Content-Length': str(5 * 1024 * 1024 + 1)}, b'{}', '5 MiB'),
])
def test_acquire_rejects_unsafe_responses_without_final_artifacts(tmp_path, headers, body, error):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'

    def opener(request, *, timeout):
        return Response(body, url=url, headers=headers)

    with pytest.raises(ValueError, match=error):
        acquire_source('matthew-henry', url, tmp_path, opener=opener)
    destination = tmp_path / 'matthew-henry'
    assert not (destination / 'GEN.json').exists()
    assert not (destination / 'GEN.json.sha256').exists()


def test_acquire_enforces_streaming_cap_including_resumed_bytes(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    directory = tmp_path / 'matthew-henry'
    directory.mkdir()
    (directory / 'GEN.json.part').write_bytes(b'x' * (5 * 1024 * 1024))

    def opener(request, *, timeout):
        return Response(b'x', url=url, status=206, headers={
            'Content-Type': 'application/json',
            'Content-Range': f'bytes {5 * 1024 * 1024}-{5 * 1024 * 1024}/{5 * 1024 * 1024 + 1}',
        })

    with pytest.raises(ValueError, match='5 MiB'):
        acquire_source('matthew-henry', url, tmp_path, opener=opener)


def test_acquire_retries_three_times_with_injected_sleeper(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    attempts = 0
    delays = []

    def opener(request, *, timeout):
        nonlocal attempts
        attempts += 1
        raise URLError(socket.timeout('timed out'))

    with pytest.raises(ValueError, match='three attempts'):
        acquire_source('matthew-henry', url, tmp_path, opener=opener, sleeper=delays.append)
    assert attempts == 3
    assert delays == [1.0, 2.0]


def test_acquire_rejects_redirected_final_url(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'

    def opener(request, *, timeout):
        return Response(b'{}', url='https://evil.example/GEN.json')

    with pytest.raises(ValueError, match='redirect'):
        acquire_source('matthew-henry', url, tmp_path, opener=opener)


def test_acquire_rejects_symlink_output_and_special_part(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    real = tmp_path / 'real'
    real.mkdir()
    output = tmp_path / 'output'
    output.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        acquire_source('matthew-henry', url, output)

    output.unlink()
    output.mkdir()
    source = output / 'matthew-henry'
    source.mkdir()
    (source / 'GEN.json.part').symlink_to(tmp_path / 'missing')
    with pytest.raises(ValueError, match='regular file'):
        acquire_source('matthew-henry', url, output)


def test_catalog_checksum_mismatch_leaves_no_final_artifacts(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/books.json'

    def opener(request, *, timeout):
        return Response(b'{}', url=url)

    with pytest.raises(ValueError, match='registry checksum'):
        acquire_source('matthew-henry', url, tmp_path, opener=opener)
    source = tmp_path / 'matthew-henry'
    assert not (source / 'books.json').exists()
    assert not (source / 'books.json.sha256').exists()


def test_bundle_acquisition_requests_only_registry_artifacts(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    calls = []

    def fake_acquire(source_id, url, output, **options):
        calls.append((source_id, url))
        return acquire.AcquiredArtifact(tmp_path / 'x', tmp_path / 'x.sha256', 'a' * 64, 2)

    monkeypatch.setattr(acquire, 'acquire_source', fake_acquire)
    artifacts = acquire.acquire_source_bundle('keil-delitzsch', tmp_path)
    registry = acquire._registry()
    expected = registry['keil-delitzsch'].expected_source_books
    assert len(artifacts) == len(expected) + 1
    assert calls[0] == ('keil-delitzsch', registry['keil-delitzsch'].upstream_url)
    assert [url.rsplit('/', 1)[-1] for _, url in calls[1:]] == [f'{book}.json' for book in expected]


def test_retry_resumes_from_bytes_persisted_before_read_timeout(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    directory = tmp_path / 'matthew-henry'
    directory.mkdir()
    (directory / 'GEN.json.part').write_bytes(b'{"ok"')
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
            })
        assert request.headers['Range'] == 'bytes=6-'
        return Response(b'true}', url=url, status=206, headers={
            'Content-Type': 'application/json', 'Content-Range': 'bytes 6-10/11',
        })

    artifact = acquire_source(
        'matthew-henry', url, tmp_path, opener=opener, sleeper=lambda _delay: None,
    )
    assert artifact.path.read_bytes() == b'{"ok":true}'
