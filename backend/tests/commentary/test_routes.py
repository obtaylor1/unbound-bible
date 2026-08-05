from uuid import uuid4

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.application import create_application
from app.auth.dependencies import require_admin
from app.auth.models import User
from app.commentary.ingest.types import NormalizedCommentaryEntry
from app.commentary.ingest.publish import stage_bundle, validate_run
from app.commentary.models import (
    CommentaryEdition,
    CommentaryEntry,
    CommentaryImportRun,
    CommentaryPublication,
    CommentarySource,
    StagedCommentaryEntry,
)


def _register(client: TestClient, *, email: str, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 201
    return response.json()


def _mount_probe(application) -> None:
    router = APIRouter()

    @router.get("/admin-probe")
    def admin_probe(user: User = Depends(require_admin)) -> dict[str, bool]:
        return {"allowed": True}

    application.include_router(router)


def test_admin_probe_rejects_registered_member(test_settings):
    application = create_application(test_settings)
    _mount_probe(application)
    with TestClient(application) as client:
        tokens = _register(client, email="member@example.com", username="member")
        response = client.get(
            "/admin-probe", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Administrator access required"}


def test_admin_probe_allows_registered_administrator(test_settings):
    application = create_application(test_settings)
    _mount_probe(application)
    with TestClient(application) as client:
        tokens = _register(client, email="admin@example.com", username="admin")
        with application.state.session_factory() as session:
            user = session.query(User).filter_by(email="admin@example.com").one()
            user.role = "admin"
            session.commit()

        response = client.get(
            "/admin-probe", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

    assert response.status_code == 200
    assert response.json() == {"allowed": True}


@pytest.fixture
def commentary_application(test_settings):
    application = create_application(test_settings)
    yield application
    application.state.database_engine.dispose()


@pytest.fixture
def commentary_client(commentary_application):
    with TestClient(commentary_application) as client:
        yield client


def _source(source_id: str, title: str | None = None) -> CommentarySource:
    return CommentarySource(
        id=source_id,
        title=title or source_id.replace('-', ' ').title(),
        abbreviation=source_id[:3].upper(),
        author='Historic Author',
        publication_period='1700s',
        tradition='Protestant',
        language='eng',
        license_spdx='Public-Domain',
        license_url='https://example.test/license',
        attribution='Public domain commentary.',
        provenance_url=f'https://example.test/{source_id}',
    )


def _publish(
    application,
    source_id: str = 'matthew-henry',
    *,
    entries: tuple[dict, ...] | None = None,
    coverage: dict | None = None,
    version: int = 1,
) -> CommentaryPublication:
    entries = entries or ({
        'work_id': 'genesis', 'chapter': 1, 'verse_start': 1, 'verse_end': 3,
        'entry_type': 'verse_range', 'heading': 'Creation',
        'body': 'God is the author of creation.', 'source_locator': 'Genesis 1:1-3',
        'position': 0,
    },)
    coverage = coverage or {
        'books': 1, 'chapters': 1, 'entries': len(entries),
        'by_work': {'genesis': {'chapters': 1, 'entries': len(entries)}},
    }
    with application.state.session_factory() as session:
        source = _source(source_id)
        session.add(source)
        session.flush()
        edition = CommentaryEdition(
            source_id=source_id,
            dataset_version=f'{version}.0.0',
            source_checksum=('a' if version == 1 else 'b') * 64,
            status='published',
            record_count=len(entries),
            coverage=coverage,
        )
        session.add(edition)
        session.flush()
        for row in entries:
            normalized = NormalizedCommentaryEntry(**row)
            session.add(CommentaryEntry(
                edition_id=edition.id,
                row_checksum=normalized.row_checksum,
                **row,
            ))
        publication = CommentaryPublication(
            source_id=source_id, edition_id=edition.id, version=version, active=True,
        )
        session.add(publication)
        session.commit()
        publication_id = publication.id
    with application.state.session_factory() as session:
        return session.get(CommentaryPublication, publication_id)


def test_sources_lists_only_active_published_editions(commentary_client, commentary_application):
    _publish(commentary_application)
    with commentary_application.state.session_factory() as session:
        session.add(_source('staged-only'))
        session.commit()

    response = commentary_client.get('/api/v1/commentaries/sources')

    assert response.status_code == 200
    assert [item['id'] for item in response.json()['sources']] == ['matthew-henry']
    source = response.json()['sources'][0]
    assert source['edition_version'] == 1
    assert source['dataset_version'] == '1.0.0'
    assert source['coverage']['by_work']['genesis']['entries'] == 1
    assert source['license_spdx'] == 'Public-Domain'


def test_verse_query_returns_covering_range(commentary_client, commentary_application):
    _publish(commentary_application)

    response = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'matthew-henry', 'book': 'Genesis', 'chapter': 1, 'verse': 2,
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload['reference'] == {'book': 'Genesis', 'chapter': 1, 'verse': 2}
    assert payload['availability'] == 'available'
    assert payload['edition']['version'] == 1
    assert payload['entries'][0]['scope'] == {'chapter': 1, 'verse_start': 1, 'verse_end': 3}
    assert payload['entries'][0]['source']['id'] == 'matthew-henry'
    assert payload['entries'][0]['citation'] == 'Genesis 1:1-3 — Matthew Henry'


def test_book_alias_is_resolved_to_canonical_work(commentary_client, commentary_application):
    _publish(commentary_application)
    response = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'matthew-henry', 'book': '  GENESIS  ', 'chapter': 1, 'verse': 1,
    })
    assert response.status_code == 200
    assert response.json()['reference']['book'] == 'Genesis'


def test_chapter_query_orders_and_bounds_entries(commentary_client, commentary_application):
    rows = tuple({
        'work_id': 'genesis', 'chapter': 1, 'verse_start': number,
        'verse_end': number, 'entry_type': 'verse', 'heading': None,
        'body': f'Entry {number}', 'source_locator': f'Genesis 1:{number}',
        'position': 0,
    } for number in range(51, 0, -1))
    _publish(commentary_application, entries=rows)

    response = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'matthew-henry', 'book': 'Genesis', 'chapter': 1,
    })

    assert response.status_code == 200
    payload = response.json()
    assert len(payload['entries']) == 50
    assert [entry['scope']['verse_start'] for entry in payload['entries'][:3]] == [1, 2, 3]
    assert payload['truncated'] is True


def test_response_body_text_is_deterministically_bounded(commentary_client, commentary_application):
    rows = tuple({
        'work_id': 'genesis', 'chapter': 1, 'verse_start': number,
        'verse_end': number, 'entry_type': 'verse', 'heading': None,
        'body': 'x' * 60_000, 'source_locator': f'Genesis 1:{number}', 'position': 0,
    } for number in (1, 2))
    _publish(commentary_application, entries=rows)

    payload = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'matthew-henry', 'book': 'Genesis', 'chapter': 1,
    }).json()

    assert sum(len(entry['body']) for entry in payload['entries']) == 100_000
    assert len(payload['entries'][1]['body']) == 40_000
    assert payload['truncated'] is True


@pytest.mark.parametrize('book,code', [
    ('Not A Bible Book', 'work_not_found'),
])
def test_unknown_work_has_structured_error(commentary_client, commentary_application, book, code):
    _publish(commentary_application)
    response = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'matthew-henry', 'book': book, 'chapter': 1,
    })
    assert response.status_code == 404
    assert response.json()['detail']['code'] == code


def test_unknown_and_unpublished_sources_have_distinct_stable_errors(
    commentary_client, commentary_application,
):
    with commentary_application.state.session_factory() as session:
        session.add(_source('known-unpublished'))
        session.commit()
    params = {'book': 'Genesis', 'chapter': 1, 'verse': 1}

    unknown = commentary_client.get(
        '/api/v1/commentaries/entries', params={'source': 'unknown', **params},
    )
    unpublished = commentary_client.get(
        '/api/v1/commentaries/entries', params={'source': 'known-unpublished', **params},
    )

    assert unknown.status_code == unpublished.status_code == 404
    assert unknown.json()['detail']['code'] == 'source_not_found'
    assert unpublished.json()['detail']['code'] == 'source_not_published'


def test_unpublished_source_has_structured_error_and_never_returns_staged_text(
    commentary_client, commentary_application,
):
    with commentary_application.state.session_factory() as session:
        session.add(_source('staged-only'))
        session.flush()
        run = CommentaryImportRun(
            source_id='staged-only', source_checksum='c' * 64,
            metadata_snapshot={'expected_books': ['genesis']}, status='staged', staged_count=1,
        )
        session.add(run)
        session.flush()
        normalized = NormalizedCommentaryEntry(
            'genesis', 1, 1, 1, 'verse', None, 'SECRET STAGED TEXT', 'local', 0,
        )
        session.add(StagedCommentaryEntry(
            run_id=run.id, work_id='genesis', chapter=1, verse_start=1, verse_end=1,
            entry_type='verse', heading=None, body=normalized.body, source_locator='local',
            row_checksum=normalized.row_checksum, position=0,
        ))
        session.commit()

    response = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'staged-only', 'book': 'Genesis', 'chapter': 1, 'verse': 1,
    })
    assert response.status_code == 404
    assert response.json()['detail']['code'] == 'source_not_published'
    assert 'SECRET STAGED TEXT' not in response.text


def test_no_entry_and_incomplete_coverage_are_distinguished(commentary_client, commentary_application):
    _publish(commentary_application, coverage={
        'books': 1, 'chapters': 1, 'entries': 1,
        'by_work': {'genesis': {'chapters': 1, 'entries': 1}},
    })
    no_entry = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'matthew-henry', 'book': 'Genesis', 'chapter': 1, 'verse': 20,
    })
    incomplete = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'matthew-henry', 'book': 'Exodus', 'chapter': 1, 'verse': 1,
    })
    assert no_entry.json()['availability'] == 'no_entry'
    assert incomplete.json()['availability'] == 'coverage_incomplete'


def test_chapter_query_marks_verse_only_material_as_wider_range(commentary_client, commentary_application):
    _publish(commentary_application)
    response = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'matthew-henry', 'book': 'Genesis', 'chapter': 1,
    })
    assert response.json()['availability'] == 'wider_range'


def test_public_responses_support_conditional_get_without_private_variation(
    commentary_client, commentary_application,
):
    _publish(commentary_application)
    first = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'matthew-henry', 'book': 'Genesis', 'chapter': 1, 'verse': 1,
    })
    assert first.headers['etag'].startswith('"')
    assert first.headers['last-modified'].endswith('GMT')
    assert first.headers['cache-control'] == 'public, max-age=60, must-revalidate'
    assert 'authorization' not in first.headers.get('vary', '').lower()

    cached = commentary_client.get(
        str(first.request.url), headers={'If-None-Match': first.headers['etag']},
    )
    assert cached.status_code == 304
    assert cached.content == b''


def test_nonmatching_etag_takes_precedence_over_if_modified_since(
    commentary_client, commentary_application,
):
    _publish(commentary_application)
    first = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'matthew-henry', 'book': 'Genesis', 'chapter': 1, 'verse': 1,
    })

    response = commentary_client.get(
        str(first.request.url),
        headers={
            'If-None-Match': '"another-representation"',
            'If-Modified-Since': first.headers['last-modified'],
        },
    )

    assert response.status_code == 200


def test_compare_accepts_one_or_two_distinct_published_sources(commentary_client, commentary_application):
    _publish(commentary_application, 'matthew-henry')
    _publish(commentary_application, 'john-gill')
    response = commentary_client.get('/api/v1/commentaries/compare', params=[
        ('sources', 'matthew-henry'), ('sources', 'john-gill'),
        ('book', 'Genesis'), ('chapter', '1'), ('verse', '2'),
    ])
    assert response.status_code == 200
    assert [item['source']['id'] for item in response.json()['results']] == [
        'matthew-henry', 'john-gill',
    ]

    single = commentary_client.get('/api/v1/commentaries/compare', params=[
        ('sources', 'john-gill'), ('book', 'Genesis'), ('chapter', '1'), ('verse', '2'),
    ])
    assert single.status_code == 200
    assert [item['source']['id'] for item in single.json()['results']] == ['john-gill']


@pytest.mark.parametrize('sources', [
    ['matthew-henry', 'matthew-henry'],
    ['matthew-henry', 'john-gill', 'adam-clarke'],
])
def test_compare_rejects_duplicate_or_more_than_two_sources(
    commentary_client, commentary_application, sources,
):
    response = commentary_client.get('/api/v1/commentaries/compare', params=[
        *((('sources', source) for source in sources)),
        ('book', 'Genesis'), ('chapter', '1'), ('verse', '1'),
    ])
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'invalid_sources'


def _override_admin(application):
    application.dependency_overrides[require_admin] = lambda: User(
        id=uuid4(), email='admin@example.test', email_normalized='admin@example.test',
        username='admin', password_hash='unused', role='admin', is_active=True,
    )


def _stage_verified(application, source_id: str, body: str, *, create_source: bool = True):
    with application.state.session_factory() as session:
        if create_source:
            session.add(_source(source_id))
            session.flush()
        row = NormalizedCommentaryEntry(
            'genesis', 1, 1, 1, 'verse', None, body, 'Genesis 1:1', 0,
        )
        run = stage_bundle(
            session,
            source_id=source_id,
            source_checksum=row.row_checksum,
            metadata_snapshot={'expected_books': ['genesis']},
            rows=[row],
        )
        validate_run(session, run.id)
        assert run.status == 'verified'
        session.commit()
        return run.id


def test_admin_import_requires_authentication(commentary_client):
    response = commentary_client.get(f'/api/v1/commentaries/admin/imports/{uuid4()}')
    assert response.status_code == 401


def test_admin_import_status_and_confirmation_errors_are_structured(
    commentary_client, commentary_application,
):
    _override_admin(commentary_application)
    with commentary_application.state.session_factory() as session:
        session.add(_source('admin-source'))
        session.flush()
        run = CommentaryImportRun(
            source_id='admin-source', source_checksum='d' * 64,
            metadata_snapshot={'expected_books': ['genesis']}, status='staged', staged_count=0,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    status_response = commentary_client.get(f'/api/v1/commentaries/admin/imports/{run_id}')
    denied = commentary_client.post(
        f'/api/v1/commentaries/admin/imports/{run_id}/publish', json={'confirm': False},
    )
    missing_confirmation = commentary_client.post(
        f'/api/v1/commentaries/admin/imports/{run_id}/publish', json={},
    )
    missing_body = commentary_client.post(
        f'/api/v1/commentaries/admin/imports/{run_id}/publish',
    )
    assert status_response.status_code == 200
    assert status_response.json()['status'] == 'staged'
    assert denied.status_code == 400
    assert denied.json()['detail']['code'] == 'confirmation_required'
    assert missing_confirmation.status_code == 400
    assert missing_confirmation.json()['detail']['code'] == 'confirmation_required'
    assert missing_body.status_code == 400
    assert missing_body.json()['detail']['code'] == 'confirmation_required'


def test_admin_unknown_import_and_publication_errors_are_stable(
    commentary_client, commentary_application,
):
    _override_admin(commentary_application)
    missing_run = commentary_client.get(f'/api/v1/commentaries/admin/imports/{uuid4()}')
    missing_publication = commentary_client.post(
        '/api/v1/commentaries/admin/publications/999999/rollback', json={'confirm': True},
    )
    assert missing_run.status_code == 404
    assert missing_run.json()['detail']['code'] == 'import_not_found'
    assert missing_publication.status_code == 404
    assert missing_publication.json()['detail']['code'] == 'publication_not_found'


def test_admin_can_publish_verified_run_at_request_transaction_boundary(
    commentary_client, commentary_application,
):
    _override_admin(commentary_application)
    run_id = _stage_verified(
        commentary_application, 'admin-publish', 'Published through the administrator API.',
    )

    response = commentary_client.post(
        f'/api/v1/commentaries/admin/imports/{run_id}/publish', json={'confirm': True},
    )

    assert response.status_code == 200
    assert response.json()['version'] == 1
    public = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'admin-publish', 'book': 'Genesis', 'chapter': 1, 'verse': 1,
    })
    assert public.status_code == 200
    assert public.json()['entries'][0]['body'] == 'Published through the administrator API.'


def test_admin_rollback_creates_new_active_version_for_previous_immutable_edition(
    commentary_client, commentary_application,
):
    _override_admin(commentary_application)
    first_run = _stage_verified(commentary_application, 'admin-rollback', 'First edition.')
    first = commentary_client.post(
        f'/api/v1/commentaries/admin/imports/{first_run}/publish', json={'confirm': True},
    )
    second_run = _stage_verified(
        commentary_application, 'admin-rollback', 'Second edition.', create_source=False,
    )
    second = commentary_client.post(
        f'/api/v1/commentaries/admin/imports/{second_run}/publish', json={'confirm': True},
    )
    assert first.status_code == second.status_code == 200

    restored = commentary_client.post(
        f"/api/v1/commentaries/admin/publications/{second.json()['publication_id']}/rollback",
        json={'confirm': True},
    )

    assert restored.status_code == 200
    assert restored.json()['version'] == 3
    public = commentary_client.get('/api/v1/commentaries/entries', params={
        'source': 'admin-rollback', 'book': 'Genesis', 'chapter': 1, 'verse': 1,
    })
    assert public.json()['entries'][0]['body'] == 'First edition.'
