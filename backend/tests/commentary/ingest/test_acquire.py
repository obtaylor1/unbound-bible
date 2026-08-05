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
    assert artifact.path == (
        tmp_path / 'matthew-henry' / 'generations' / 'GEN.json'
        / artifact.checksum / 'GEN.json'
    )
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
    (target_dir / 'GEN.json.part.meta').write_text(
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

    artifact = acquire_source('matthew-henry', url, tmp_path, opener=opener)
    assert artifact.path.read_bytes() == b'{"ok":true}'


def test_acquire_restarts_when_server_ignores_range(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    target_dir = tmp_path / 'matthew-henry'
    target_dir.mkdir()
    (target_dir / 'GEN.json.part').write_bytes(b'garbage')
    (target_dir / 'GEN.json.part.meta').write_text(
        json.dumps({'url': url, 'etag': '"v1"'}), encoding='utf-8',
    )
    body = b'{"fresh":true}'

    def opener(request, *, timeout):
        assert request.headers['Range'] == 'bytes=7-'
        assert request.headers['If-range'] == '"v1"'
        return Response(body, url=url, status=200, headers={
            'Content-Type': 'application/json', 'ETag': '"v2"',
        })

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
    (directory / 'GEN.json.part.meta').write_text(
        json.dumps({'url': url, 'etag': '"v1"'}), encoding='utf-8',
    )

    def opener(request, *, timeout):
        return Response(b'x', url=url, status=206, headers={
            'Content-Type': 'application/json',
            'Content-Range': f'bytes {5 * 1024 * 1024}-{5 * 1024 * 1024}/{5 * 1024 * 1024 + 1}',
            'ETag': '"v1"',
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
        return acquire.AcquiredArtifact(
            tmp_path / 'x', tmp_path / 'x.sha256', 'a' * 64, 2, url,
        )

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
    (directory / 'GEN.json.part.meta').write_text(
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

    artifact = acquire_source(
        'matthew-henry', url, tmp_path, opener=opener, sleeper=lambda _delay: None,
    )
    assert artifact.path.read_bytes() == b'{"ok":true}'


@pytest.mark.parametrize('failure_point', ['sidecar', 'directory_fsync'])
def test_finalization_failure_removes_both_final_artifacts(monkeypatch, tmp_path, failure_point):
    from app.commentary.ingest import acquire

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'

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
        acquire.acquire_source('matthew-henry', url, tmp_path, opener=opener)
    directory = tmp_path / 'matthew-henry'
    assert not (directory / 'GEN.json').exists()
    assert not (directory / 'GEN.json.sha256').exists()
    assert list(directory.glob('GEN.json*.part*')) == []


def test_partial_bytes_are_fsynced_before_retry(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
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

    artifact = acquire.acquire_source(
        'matthew-henry', url, tmp_path, opener=opener, sleeper=sleeper,
    )
    assert artifact.path.read_bytes() == b'{"ok":true}'


def test_changed_etag_on_partial_response_restarts_from_zero(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    directory = tmp_path / 'matthew-henry'
    directory.mkdir()
    (directory / 'GEN.json.part').write_bytes(b'{"old"')
    (directory / 'GEN.json.part.meta').write_text(
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

    artifact = acquire_source(
        'matthew-henry', url, tmp_path, opener=opener, sleeper=lambda _delay: None,
    )
    assert artifact.path.read_bytes() == b'{"fresh":true}'


def test_failed_reacquisition_preserves_the_known_good_generation(tmp_path):
    from app.commentary.ingest.acquire import acquire_source, read_acquired_artifact

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    first = b'{"generation":1}'
    acquire_source(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(first, url=url, headers={
            'Content-Type': 'application/json', 'ETag': '"v1"',
        }),
    )

    with pytest.raises(ValueError, match='valid JSON'):
        acquire_source(
            'matthew-henry', url, tmp_path,
            opener=lambda *_args, **_kwargs: Response(b'{bad', url=url, headers={
                'Content-Type': 'application/json', 'ETag': '"v2"',
            }),
        )

    raw, digest, acquired_url = read_acquired_artifact(
        tmp_path / 'matthew-henry', 'GEN.json', source_id='matthew-henry',
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

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    old = b'{"generation":"old"}'
    acquire_source(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(old, url=url),
    )

    def hook(step):
        if step == checkpoint:
            raise OSError(f'injected {step}')

    with pytest.raises(OSError, match='injected'):
        acquire_source(
            'matthew-henry', url, tmp_path,
            opener=lambda *_args, **_kwargs: Response(b'{"generation":"new"}', url=url),
            finalization_hook=hook,
        )
    assert read_acquired_artifact(
        tmp_path / 'matthew-henry', 'GEN.json', source_id='matthew-henry',
    )[0] == old


def test_unreferenced_incomplete_generation_does_not_replace_current(tmp_path):
    from app.commentary.ingest.acquire import acquire_source, read_acquired_artifact

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    trusted = b'{"trusted":true}'
    acquire_source(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(trusted, url=url),
    )
    stale = tmp_path / 'matthew-henry' / 'generations' / 'GEN.json' / ('f' * 64)
    stale.mkdir(parents=True)
    (stale / 'artifact.json').write_text('{"incomplete":true}', encoding='utf-8')

    assert read_acquired_artifact(
        tmp_path / 'matthew-henry', 'GEN.json', source_id='matthew-henry',
    )[0] == trusted


def test_output_directory_swap_cannot_redirect_authoritative_marker(tmp_path):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    output = tmp_path / 'output'
    attacker = tmp_path / 'attacker'
    attacker.mkdir()

    def swap(step):
        if step == 'before_marker_switch':
            (output / 'matthew-henry').rename(output / 'original-source')
            (output / 'matthew-henry').symlink_to(attacker, target_is_directory=True)

    with pytest.raises(ValueError, match='changed during finalization'):
        acquire_source(
            'matthew-henry', url, output,
            opener=lambda *_args, **_kwargs: Response(b'{"safe":true}', url=url),
            finalization_hook=swap,
        )

    assert list(attacker.iterdir()) == []
    assert not (output / 'original-source' / 'GEN.json.current.json').exists()


@pytest.mark.parametrize('swap_level', ['source', 'ancestor'])
def test_network_callback_swap_cannot_redirect_partial_files(tmp_path, swap_level):
    from app.commentary.ingest.acquire import acquire_source

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    output = tmp_path / 'output'
    attacker = tmp_path / 'attacker'
    attacker_source = attacker / 'matthew-henry'
    attacker_source.mkdir(parents=True)
    hostile_part = attacker_source / 'GEN.json.part'
    hostile_meta = attacker_source / 'GEN.json.part.meta'
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
        acquire_source('matthew-henry', url, output, opener=opener)

    assert hostile_part.read_bytes() == b'hostile-part'
    assert hostile_meta.read_bytes() == b'hostile-meta'


def test_fresh_generation_fsyncs_each_new_parent_before_marker(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    body = b'{"durable":true}'
    digest = sha256(body).hexdigest()
    events = []

    def track(descriptor):
        info = acquire.os.fstat(descriptor)
        candidates = {
            'output': tmp_path,
            'source': tmp_path / 'matthew-henry',
            'generations': tmp_path / 'matthew-henry' / 'generations',
            'artifact-root': tmp_path / 'matthew-henry' / 'generations' / 'GEN.json',
            'generation': (
                tmp_path / 'matthew-henry' / 'generations' / 'GEN.json' / digest
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
    acquire.acquire_source(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(body, url=url),
    )

    assert events == [
        'output', 'source', 'generations', 'artifact-root', 'generation', 'source',
    ]


def test_existing_generation_only_fsyncs_contents_and_marker_parent(monkeypatch, tmp_path):
    from app.commentary.ingest import acquire

    url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    body = b'{"durable":true}'
    acquire.acquire_source(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(body, url=url),
    )
    events = []
    source = tmp_path / 'matthew-henry'
    generation = source / 'generations' / 'GEN.json' / sha256(body).hexdigest()

    def track(descriptor):
        info = acquire.os.fstat(descriptor)
        for label, path in (('generation', generation), ('source', source)):
            current = path.stat()
            if (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino):
                events.append(label)
                return
        raise AssertionError('existing parent was unnecessarily fsynced')

    monkeypatch.setattr(acquire, '_fsync_directory', track)
    acquire.acquire_source(
        'matthew-henry', url, tmp_path,
        opener=lambda *_args, **_kwargs: Response(body, url=url),
    )

    assert events == ['generation', 'source']
