from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.application import create_application
from app.auth.models import User
from app.library.models import EditionWorkSource, LibraryWork, TextEdition


EDITION_CODE = 'EOTC-COMPOSITE-EN'
MANIFEST_PATH = (
    Path(__file__).parents[2] / 'data/scripture/eotc-composite-en/manifest.json'
)
STATUSES = (
    'in_progress', 'verified_exact', 'verified_formatting',
    'verified_rebuilt', 'review_required',
)


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post('/api/v1/auth/register', json={
        'email': email,
        'username': email.split('@')[0],
        'password': 'correct-horse-battery-staple',
    })
    assert response.status_code == 201
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _seed_complete_edition(application) -> tuple[Counter, Counter]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    source_documents = manifest['adapter_options']['work_sources']
    family_totals = Counter()
    status_totals = Counter()
    with application.state.session_factory() as session:
        session.add(TextEdition(
            edition_code=EDITION_CODE,
            name='Ethiopian Orthodox Composite English',
            reading_language='English',
            source_language='Multiple',
            script='Latin',
            relationship='exact_ethiopian',
            expected_coverage={'works': sorted(source_documents)},
            verification_status='provisional',
        ))
        session.flush()
        for index, (work_id, document) in enumerate(reversed(source_documents.items())):
            status = STATUSES[index % len(STATUSES)]
            family_totals[document['source_key']] += 1
            status_totals[status] += 1
            verified = status.startswith('verified_')
            values = dict(document)
            for timestamp_field in ('artifact_retrieved_at', 'reviewed_at'):
                timestamp = values.get(timestamp_field)
                if isinstance(timestamp, str):
                    values[timestamp_field] = datetime.fromisoformat(
                        timestamp.replace('Z', '+00:00')
                    )
            values.update({
                'edition_code': EDITION_CODE,
                'work_id': work_id,
                'verification_status': status,
                'provenance_url': (
                    'file:///Users/admin/private/source.txt'
                    if work_id == 'genesis' else document['provenance_url']
                ),
                'rights_url': (
                    'https://example.org/rights?token=private'
                    if work_id == 'exodus' else document['rights_url']
                ),
                'artifact_filename': f'/Users/admin/private/{work_id}.txt',
                'artifact_sha256': (f'{index:064x}'[-64:] if index % 2 == 0 else None),
                'comparison_exact': index,
                'comparison_formatting': index + 1,
                'comparison_missing': index + 2,
                'comparison_extra': index + 3,
                'comparison_wording': index + 4,
                'comparison_report_sha256': (
                    f'{index + 100:064x}'[-64:] if index % 3 == 0 else None
                ),
                'reviewer': 'Source Review Team' if verified else None,
                'reviewed_at': datetime(2026, 8, 17, 13, tzinfo=UTC) if verified else None,
                'review_note': f'Private report /Users/admin/{work_id}.json',
                'transformations': [
                    {'description': 'Normalized', 'path': f'/Users/admin/{work_id}.txt'},
                ],
            })
            session.add(EditionWorkSource(**values))
        session.commit()
    return family_totals, status_totals


def _inject_unsafe_admin_disclosures(application) -> None:
    unsafe = {
        'genesis': {
            'source_label': 'Loaded from /Users/admin/private/source.txt',
            'reviewer': 'reviewer file:///private/reviewer.txt',
        },
        'exodus': {
            'source_edition': r'C:\Users\admin\private\edition.txt',
        },
        'leviticus': {
            'source_revision': '%252Fcustom%252Fprivate%252Frevision.txt',
        },
        'numbers': {
            'license_spdx': 'access_token=do-not-disclose',
        },
        'deuteronomy': {
            'provenance_url': 'https://example.org/%252FUsers%252Fadmin%252Fsource.txt',
            'rights_url': r'https://example.org/?file=C%253A%255CUsers%255Cadmin%255Crights.txt',
        },
        'joshua': {
            'provenance_url': 'https://2130706433/source',
            'reviewer': f"github_pat_{'A' * 30}",
        },
        'judges': {
            'rights_url': 'https://0x7f000001/rights',
            'source_edition': '/data',
        },
        'ruth': {
            'reviewer': 'Reviewed at /@private',
            'provenance_url': 'https://example.org/source?path=%252F123',
            'rights_url': 'https://example.org/rights?path=%252F%2540private',
        },
        '1-samuel': {
            'reviewer': 'jwt_token=do-not-disclose',
            'source_edition': 'client%255Fsecret%253Ddo-not-disclose',
        },
        '2-samuel': {
            'reviewer': 'clientAPIKey=do-not-disclose',
            'source_edition': 'signingkey=do-not-disclose',
            'source_revision': 'client%2541PIKey%253Ddo-not-disclose',
        },
        '1-kings': {
            'reviewer': 'clientKey=do-not-disclose',
            'source_edition': 'encryption-key=do-not-disclose',
            'source_revision': 'consumer%255Fkey%253Ddo-not-disclose',
        },
    }
    with application.state.session_factory() as session:
        for work_id, changes in unsafe.items():
            source = session.scalar(select(EditionWorkSource).where(
                EditionWorkSource.edition_code == EDITION_CODE,
                EditionWorkSource.work_id == work_id,
            ))
            for field, value in changes.items():
                setattr(source, field, value)
        session.get(LibraryWork, 'genesis').title = 'Genesis from ~/private/catalog.txt'
        session.commit()


def test_admin_inventory_requires_authentication_and_admin_role(test_settings):
    application = create_application(test_settings)
    client = TestClient(application)
    member_headers = _register(client, 'member@example.com')

    anonymous = client.get('/api/v1/library/admin/scripture-verification')
    member = client.get(
        '/api/v1/library/admin/scripture-verification', headers=member_headers,
    )

    assert anonymous.status_code == 401
    assert member.status_code == 403
    assert member.json()['detail'] == 'Administrator access required'


def test_admin_inventory_is_sorted_complete_bounded_and_safe(test_settings):
    application = create_application(test_settings)
    expected_family_totals, expected_status_totals = _seed_complete_edition(application)
    _inject_unsafe_admin_disclosures(application)
    client = TestClient(application)
    headers = _register(client, 'admin@example.com')
    with application.state.session_factory() as session:
        admin = session.scalar(select(User).where(User.email == 'admin@example.com'))
        admin.role = 'administrator'
        session.commit()

    response = client.get(
        '/api/v1/library/admin/scripture-verification', headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body['edition_code'] == EDITION_CODE
    assert body['total_works'] == len(body['works']) == 83
    assert [row['work_id'] for row in body['works']] == sorted(
        row['work_id'] for row in body['works']
    )
    assert {row['work_id'] for row in body['works']} == set(
        json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        ['adapter_options']['work_sources']
    )
    assert body['family_totals'] == [
        {'source_key': key, 'count': count}
        for key, count in sorted(expected_family_totals.items())
    ]
    assert body['status_totals'] == [
        {
            'status': status,
            'label': {
                'in_progress': 'Source verification in progress',
                'verified_exact': 'Source verified',
                'verified_formatting': 'Verified with documented formatting changes',
                'verified_rebuilt': 'Rebuilt from verified source',
                'review_required': 'Source review required',
            }[status],
            'count': expected_status_totals[status],
        }
        for status in STATUSES
    ]
    genesis = next(row for row in body['works'] if row['work_id'] == 'genesis')
    exodus = next(row for row in body['works'] if row['work_id'] == 'exodus')
    assert genesis['provenance_url'] is None
    assert exodus['rights_url'] is None
    assert set(genesis) == {
        'work_id', 'work_name', 'source_key', 'source_label', 'source_edition',
        'source_revision', 'provenance_url', 'rights_url', 'license', 'fallback',
        'canon_scope', 'artifact_sha256', 'comparison_report_sha256', 'comparison',
        'reviewer', 'reviewed_at', 'verification',
    }
    assert set(genesis['comparison']) == {
        'exact', 'formatting', 'missing', 'extra', 'wording',
    }
    assert set(genesis['verification']) == {'status', 'label', 'verified_at'}
    verified = next(
        row for row in body['works']
        if row['verification']['status'].startswith('verified_')
    )
    assert verified['reviewer'] == 'Source Review Team'
    assert verified['reviewed_at'] == '2026-08-17T13:00:00Z'
    assert verified['verification']['verified_at'] == '2026-08-17T13:00:00Z'
    assert any(row['artifact_sha256'] is not None for row in body['works'])
    assert any(row['comparison_report_sha256'] is not None for row in body['works'])
    assert all(
        checksum is None or len(checksum) == 64
        for row in body['works']
        for checksum in (row['artifact_sha256'], row['comparison_report_sha256'])
    )
    assert any(row['comparison']['exact'] > 0 for row in body['works'])
    serialized = response.text
    for forbidden in (
        'artifact_filename', 'artifact_retrieved_at', 'artifact_size',
        'parser_version', 'transformations', 'review_note', '/Users/',
        'token=private', 'c:\\users\\', 'file://', '/private/', '~/private',
        '%252fcustom', 'access_token=do-not-disclose',
        '2130706433', '0x7f000001', 'github_pat_', '/data',
        '/@private', '%252f123', '%2540private',
        'jwt_token', 'client%255fsecret', 'do-not-disclose',
        'clientapikey', 'signingkey', 'client%2541pikey',
        'clientkey', 'encryption-key', 'consumer%255fkey',
    ):
        assert forbidden.casefold() not in serialized.casefold()
    assert genesis['work_name'] == 'Not disclosed'
    assert genesis['source_label'] == 'Not disclosed'
    assert genesis['reviewer'] is None
    assert next(row for row in body['works'] if row['work_id'] == 'exodus')[
        'source_edition'
    ] is None
    assert next(row for row in body['works'] if row['work_id'] == 'leviticus')[
        'source_revision'
    ] is None
    assert next(row for row in body['works'] if row['work_id'] == 'numbers')[
        'license'
    ] == 'Not disclosed'
    deuteronomy = next(row for row in body['works'] if row['work_id'] == 'deuteronomy')
    assert deuteronomy['provenance_url'] is None
    assert deuteronomy['rights_url'] is None
    joshua = next(row for row in body['works'] if row['work_id'] == 'joshua')
    judges = next(row for row in body['works'] if row['work_id'] == 'judges')
    assert joshua['provenance_url'] is None
    assert joshua['reviewer'] is None
    assert judges['rights_url'] is None
    assert judges['source_edition'] is None
    ruth = next(row for row in body['works'] if row['work_id'] == 'ruth')
    assert ruth['reviewer'] is None
    assert ruth['provenance_url'] is None
    assert ruth['rights_url'] is None
    first_samuel = next(row for row in body['works'] if row['work_id'] == '1-samuel')
    assert first_samuel['reviewer'] is None
    assert first_samuel['source_edition'] is None
    second_samuel = next(row for row in body['works'] if row['work_id'] == '2-samuel')
    assert second_samuel['reviewer'] is None
    assert second_samuel['source_edition'] is None
    assert second_samuel['source_revision'] is None
    first_kings = next(row for row in body['works'] if row['work_id'] == '1-kings')
    assert first_kings['reviewer'] is None
    assert first_kings['source_edition'] is None
    assert first_kings['source_revision'] is None


def test_admin_inventory_handles_missing_edition_and_partial_evidence(test_settings):
    application = create_application(test_settings)
    client = TestClient(application)
    headers = _register(client, 'admin@example.com')
    with application.state.session_factory() as session:
        admin = session.scalar(select(User).where(User.email == 'admin@example.com'))
        admin.role = 'administrator'
        session.commit()

    missing = client.get(
        '/api/v1/library/admin/scripture-verification', headers=headers,
    )

    assert missing.status_code == 200
    assert missing.json() == {
        'edition_code': EDITION_CODE,
        'total_works': 0,
        'family_totals': [],
        'status_totals': [
            {'status': status, 'label': label, 'count': 0}
            for status, label in (
                ('in_progress', 'Source verification in progress'),
                ('verified_exact', 'Source verified'),
                ('verified_formatting', 'Verified with documented formatting changes'),
                ('verified_rebuilt', 'Rebuilt from verified source'),
                ('review_required', 'Source review required'),
            )
        ],
        'works': [],
    }
