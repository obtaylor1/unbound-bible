from datetime import UTC, datetime

from fastapi.testclient import TestClient
import pytest

from app.application import create_application
from app.library.models import EditionWorkSource, TextEdition


EDITION_CODE = 'EOTC-COMPOSITE-EN'


def _add_source(application, **changes) -> None:
    values = {
        'edition_code': EDITION_CODE,
        'work_id': 'genesis',
        'source_key': 'world-messianic-bible',
        'source_label': 'World Messianic Bible',
        'translator': 'World Messianic Bible contributors',
        'source_language': 'Hebrew',
        'source_tradition': 'Hebrew Masoretic tradition',
        'published_year': 2020,
        'license_spdx': 'LicenseRef-Public-Domain',
        'attribution': 'Public-domain source text.',
        'provenance_url': 'https://ebible.org/engwmb/',
        'fallback': False,
        'modified': True,
        'modification_note': 'Normalized whitespace.',
        'verification_status': 'verified_exact',
        'canon_scope': 'ethio81',
        'source_edition': '2026-08 release',
        'source_revision': 'engwmb-2026-08',
        'rights_url': 'https://ebible.org/engwmb/copyright.htm',
        'rights_jurisdiction': 'Public domain in the United States',
        'artifact_filename': '/Users/admin/private/source.zip',
        'artifact_retrieved_at': datetime(2026, 8, 17, 12, tzinfo=UTC),
        'artifact_size': 1234,
        'artifact_sha256': 'a' * 64,
        'parser_version': 'wmb-v1',
        'transformations': [
            {'description': 'Safe note', 'local_path': '/Users/admin/private/source.zip'},
        ],
        'comparison_exact': 1533,
        'comparison_formatting': 0,
        'comparison_missing': 0,
        'comparison_extra': 0,
        'comparison_wording': 0,
        'comparison_report_sha256': 'b' * 64,
        'reviewer': 'Source Review Team',
        'reviewed_at': datetime(2026, 8, 17, 13, tzinfo=UTC),
        'review_note': 'Private report: /Users/admin/private/report.json',
    }
    values.update(changes)
    with application.state.session_factory() as session:
        session.add(TextEdition(
            edition_code=EDITION_CODE,
            name='Ethiopian Orthodox Composite English',
            reading_language='English',
            source_language='Multiple',
            script='Latin',
            relationship='exact_ethiopian',
            expected_coverage={'works': ['genesis']},
            verification_status='provisional',
        ))
        session.flush()
        session.add(EditionWorkSource(**values))
        session.commit()


def test_public_source_detail_uses_plain_language_and_is_strictly_bounded(test_settings):
    application = create_application(test_settings)
    _add_source(application)

    response = TestClient(application).get(
        f'/api/v1/library/editions/{EDITION_CODE}/works/genesis/source'
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        'edition_code': EDITION_CODE,
        'work_id': 'genesis',
        'source_key': 'world-messianic-bible',
        'source_label': 'World Messianic Bible',
        'translator': 'World Messianic Bible contributors',
        'source_language': 'Hebrew',
        'source_tradition': 'Hebrew Masoretic tradition',
        'published_year': 2020,
        'license': 'LicenseRef-Public-Domain',
        'attribution': 'Public-domain source text.',
        'provenance_url': 'https://ebible.org/engwmb/',
        'rights_url': 'https://ebible.org/engwmb/copyright.htm',
        'rights_jurisdiction': 'Public domain in the United States',
        'source_edition': '2026-08 release',
        'source_revision': 'engwmb-2026-08',
        'fallback': False,
        'modified': True,
        'modification_note': 'Normalized whitespace.',
        'transformations': ['Safe note'],
        'canon_scope': 'ethio81',
        'verification': {
            'status': 'verified_exact',
            'label': 'Source verified',
            'verified_at': '2026-08-17T13:00:00Z',
        },
    }
    serialized = response.text
    for forbidden in (
        'artifact_filename', 'artifact_size', 'artifact_sha256', 'parser_version',
        'comparison_', 'reviewer', 'review_note', '/Users/',
    ):
        assert forbidden not in serialized


def test_public_source_detail_redacts_unsafe_urls_and_handles_partial_evidence(test_settings):
    application = create_application(test_settings)
    _add_source(
        application,
        verification_status='in_progress',
        provenance_url='file:///Users/admin/private/source.txt',
        rights_url='https://example.org/rights?access_token=secret',
        reviewed_at=None,
        reviewer=None,
        artifact_sha256=None,
        comparison_report_sha256=None,
    )

    body = TestClient(application).get(
        f'/api/v1/library/editions/{EDITION_CODE}/works/genesis/source'
    ).json()

    assert body['provenance_url'] is None
    assert body['rights_url'] is None
    assert body['verification'] == {
        'status': 'in_progress',
        'label': 'Source verification in progress',
        'verified_at': None,
    }
    assert body['transformations'] == ['Safe note']
    assert 'secret' not in str(body)
    assert '/Users/' not in str(body)


def test_public_source_detail_sanitizes_and_bounds_all_text_disclosures(test_settings):
    application = create_application(test_settings)
    long_description = 'A' * 400
    _add_source(
        application,
        source_label='Generated from /Users/admin/source.txt',
        translator=r'C:\Users\admin\translator.txt',
        source_language='file:///private/source-language.txt',
        source_tradition='%252FUsers%252Fadmin%252Ftradition.txt',
        license_spdx='password=do-not-disclose',
        attribution='Loaded from ~/private/attribution.txt',
        modification_note='Generated from /custom/private/report.json',
        rights_jurisdiction=r'%USERPROFILE%\private\rights.txt',
        source_edition='https://example.org/not-a-description',
        source_revision='authorization: Bearer do-not-disclose',
        transformations=[
            'Trimmed whitespace.',
            'Generated from /Users/admin/private/source.txt',
            'Removed source note markers.',
            'https://example.org/private-report',
            'password=do-not-disclose',
            'Contains a hidden control\u202echaracter.',
            'Contains a line\nbreak.',
            'token=do-not-disclose',
            long_description,
            'Step four.', 'Step five.', 'Step six.', 'Step seven.',
            'Step eight.', 'Step nine.', 'Step ten.',
        ],
    )

    response = TestClient(application).get(
        f'/api/v1/library/editions/{EDITION_CODE}/works/genesis/source'
    )

    assert response.status_code == 200
    body = response.json()
    assert body['source_label'] == 'Not disclosed'
    assert body['translator'] is None
    assert body['source_language'] == 'Not disclosed'
    assert body['source_tradition'] == 'Not disclosed'
    assert body['license'] == 'Not disclosed'
    assert body['attribution'] == 'Not disclosed'
    assert body['modification_note'] is None
    assert body['rights_jurisdiction'] is None
    assert body['source_edition'] is None
    assert body['source_revision'] is None
    assert body['transformations'] == [
        'Trimmed whitespace.',
        'Removed source note markers.',
        f'{long_description[:299]}…',
        'Step four.', 'Step five.', 'Step six.', 'Step seven.', 'Step eight.',
    ]
    assert len(body['transformations']) == 8
    assert all(len(description) <= 300 for description in body['transformations'])
    serialized = response.text.casefold()
    for forbidden in (
        '/users/', 'c:\\users\\', 'file://', '/private/', '~/private',
        '/custom/private/', '%252fusers', '%userprofile%', 'password=',
        'bearer do-not-disclose', 'https://example.org/not-a-description',
    ):
        assert forbidden not in serialized


def test_public_source_detail_rejects_standalone_secrets_and_rooted_paths(
    test_settings,
):
    application = create_application(test_settings)
    github_token = f"ghp_{'A' * 36}"
    stripe_secret = f"sk_live_{'B' * 24}"
    aws_access_key = f"AKIA{'C' * 16}"
    jwt_secret = f"eyJ{'a' * 12}.{'b' * 20}.{'c' * 24}"
    safe_prose = (
        'The secret things belong to God; the token of the covenant remained. '
        'Hebrew/Aramaic source and chapter/verse markers were retained.'
    )
    _add_source(
        application,
        source_label=stripe_secret,
        translator=github_token,
        attribution=safe_prose,
        modification_note=f'Compared with {aws_access_key}',
        rights_jurisdiction=jwt_secret,
        source_edition='/srv',
        source_revision='/workspace/review.json',
        transformations=[
            safe_prose,
            f'Removed credential {github_token}',
            f'Removed credential {stripe_secret}',
            f'Removed credential {aws_access_key}',
            f'Removed credential {jwt_secret}',
            '/data', '/mnt', '/app', '/workspace', '/custom-root',
            'FI/RF apparatus markers were removed.',
        ],
    )

    response = TestClient(application).get(
        f'/api/v1/library/editions/{EDITION_CODE}/works/genesis/source'
    )

    assert response.status_code == 200
    body = response.json()
    assert body['source_label'] == 'Not disclosed'
    assert body['translator'] is None
    assert body['attribution'] == safe_prose
    assert body['modification_note'] is None
    assert body['rights_jurisdiction'] is None
    assert body['source_edition'] is None
    assert body['source_revision'] is None
    assert body['transformations'] == [
        safe_prose,
        'FI/RF apparatus markers were removed.',
    ]
    serialized = response.text
    for forbidden in (
        github_token, stripe_secret, aws_access_key, jwt_secret,
        '/data', '/mnt', '/app', '/workspace', '/custom-root',
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize('token', [
    f"github_pat_{'A' * 30}",
    f"sk_test_{'B' * 24}",
    f"rk_live_{'C' * 24}",
    f"ASIA{'D' * 16}",
    f"sk-{'E' * 30}",
    f"AIza{'F' * 35}",
    'xoxb-' + '123456789012-123456789012-abcdefghijklmnopqrstuvwx',
])
def test_text_disclosure_sanitizer_rejects_well_known_standalone_secrets(token):
    from app.library.router import _bounded_text

    assert _bounded_text(f'Review value {token}', 300) is None


@pytest.mark.parametrize('path', [
    '/123', '/1secret', '/@private', '%252F123', '%252F%2540private',
])
def test_text_disclosure_sanitizer_rejects_all_rooted_path_tokens(path):
    from app.library.router import _bounded_text

    assert _bounded_text(f'Review value {path}', 300) is None


def test_text_disclosure_sanitizer_preserves_slashes_in_ordinary_prose():
    from app.library.router import _bounded_text

    prose = 'Psalm 23/1; Hebrew/Aramaic source; chapter/verse markers; FI/RF notes.'
    assert _bounded_text(prose, 300) == prose


@pytest.mark.parametrize('assignment', [
    'client_secret=do-not-disclose',
    'DB_PASSWORD:do-not-disclose',
    'jwt_token = do-not-disclose',
    'clientSecret=do-not-disclose',
    'db-password: do-not-disclose',
    'service_api_key=do-not-disclose',
    'backup-access-key:do-not-disclose',
    'signingPrivateKey=do-not-disclose',
    'source_credential_id=do-not-disclose',
    'client%255Fsecret%253Ddo-not-disclose',
])
def test_text_disclosure_sanitizer_rejects_prefixed_credential_assignments(
    assignment,
):
    from app.library.router import _bounded_text

    assert _bounded_text(f'Review field {assignment}', 300) is None


def test_text_disclosure_sanitizer_preserves_safe_credential_words_without_assignment():
    from app.library.router import _bounded_text

    prose = 'The secret things belong to God, and the token of the covenant remained.'
    assert _bounded_text(prose, 300) == prose


@pytest.mark.parametrize('assignment', [
    'apikey=do-not-disclose',
    'privatekey:do-not-disclose',
    'signingkey = do-not-disclose',
    'accesskey=do-not-disclose',
    'clientAPIKey=do-not-disclose',
    'clientapikey=do-not-disclose',
    'servicePrivateKey=do-not-disclose',
    'backupSigningKey=do-not-disclose',
    'client%2541PIKey%253Ddo-not-disclose',
])
def test_text_disclosure_sanitizer_rejects_collapsed_credential_assignments(
    assignment,
):
    from app.library.router import _bounded_text

    assert _bounded_text(f'Review field {assignment}', 300) is None


@pytest.mark.parametrize('assignment', [
    'clientKey=do-not-disclose',
    'consumer_key:do-not-disclose',
    'encryption-key = do-not-disclose',
    'clientkey=do-not-disclose',
    'consumerKey=do-not-disclose',
    'encryptionkey=do-not-disclose',
    'publicKey=do-not-disclose',
    'consumer%255Fkey%253Ddo-not-disclose',
])
def test_text_disclosure_sanitizer_rejects_prefixed_key_credentials(assignment):
    from app.library.router import _bounded_text

    assert _bounded_text(f'Review field {assignment}', 300) is None


def test_text_disclosure_sanitizer_preserves_ordinary_key_assignment_prose():
    from app.library.router import _bounded_text

    prose = 'The study index uses key=chapter-one beside the Genesis reading.'
    assert _bounded_text(prose, 300) == prose


def test_public_source_detail_rejects_digit_and_punctuation_rooted_paths(
    test_settings,
):
    application = create_application(test_settings)
    _add_source(
        application,
        source_revision='Compared at /1secret',
        provenance_url='https://example.org/source?path=%252F123',
        rights_url='https://example.org/rights?path=%252F%2540private',
        transformations=['Psalm 23/1 is retained.', '/@private'],
    )

    body = TestClient(application).get(
        f'/api/v1/library/editions/{EDITION_CODE}/works/genesis/source'
    ).json()

    assert body['source_revision'] is None
    assert body['provenance_url'] is None
    assert body['rights_url'] is None
    assert body['transformations'] == ['Psalm 23/1 is retained.']


def test_public_source_detail_rejects_prefixed_credential_assignments(test_settings):
    application = create_application(test_settings)
    safe_prose = 'The secret things belong to God; the token of the covenant remained.'
    _add_source(
        application,
        attribution=safe_prose,
        source_revision='clientSecret=do-not-disclose',
        modification_note='client%255Fsecret%253Ddo-not-disclose',
        transformations=[safe_prose, 'DB_PASSWORD=do-not-disclose'],
    )

    body = TestClient(application).get(
        f'/api/v1/library/editions/{EDITION_CODE}/works/genesis/source'
    ).json()

    assert body['attribution'] == safe_prose
    assert body['source_revision'] is None
    assert body['modification_note'] is None
    assert body['transformations'] == [safe_prose]
    assert 'do-not-disclose' not in str(body)


def test_public_source_detail_rejects_collapsed_credential_assignments(test_settings):
    application = create_application(test_settings)
    safe_prose = 'A private reading room used a key-shaped bookmark.'
    _add_source(
        application,
        attribution=safe_prose,
        source_revision='clientAPIKey=do-not-disclose',
        modification_note='client%2541PIKey%253Ddo-not-disclose',
        transformations=[safe_prose, 'apikey=do-not-disclose'],
    )

    body = TestClient(application).get(
        f'/api/v1/library/editions/{EDITION_CODE}/works/genesis/source'
    ).json()

    assert body['attribution'] == safe_prose
    assert body['source_revision'] is None
    assert body['modification_note'] is None
    assert body['transformations'] == [safe_prose]
    assert 'do-not-disclose' not in str(body)


def test_public_source_detail_rejects_prefixed_key_credentials(test_settings):
    application = create_application(test_settings)
    safe_prose = 'The study index uses key=chapter-one beside the Genesis reading.'
    _add_source(
        application,
        attribution=safe_prose,
        source_revision='clientKey=do-not-disclose',
        modification_note='consumer%255Fkey%253Ddo-not-disclose',
        transformations=[safe_prose, 'encryption-key=do-not-disclose'],
    )

    body = TestClient(application).get(
        f'/api/v1/library/editions/{EDITION_CODE}/works/genesis/source'
    ).json()

    assert body['attribution'] == safe_prose
    assert body['source_revision'] is None
    assert body['modification_note'] is None
    assert body['transformations'] == [safe_prose]
    assert 'do-not-disclose' not in str(body)


@pytest.mark.parametrize('host', [
    '2130706433',
    '0x7f000001',
    '127.1',
    '0177.0.0.1',
    '0x7f.0x0.0x0.0x1',
    '999.999.999.999',
])
def test_public_source_detail_rejects_browser_numeric_loopback_hosts(
    test_settings, host,
):
    application = create_application(test_settings)
    _add_source(
        application,
        provenance_url=f'https://{host}/source',
        rights_url=f'https://{host}/rights',
        transformations=[],
    )

    body = TestClient(application).get(
        f'/api/v1/library/editions/{EDITION_CODE}/works/genesis/source'
    ).json()

    assert body['provenance_url'] is None
    assert body['rights_url'] is None


@pytest.mark.parametrize('provenance_url,rights_url', [
    (
        'https://example.org/%252FUsers%252Fadmin%252Fsource.txt',
        r'https://example.org/download?file=C%253A%255CUsers%255Cadmin%255Crights.txt',
    ),
    (
        'https://example.org/download?file=%252Fcustom%252Fprivate%252Fsource.txt',
        'https://example.org/%257E%252Fprivate%252Frights.txt',
    ),
])
def test_public_source_detail_rejects_encoded_paths_inside_urls(
    test_settings, provenance_url, rights_url,
):
    application = create_application(test_settings)
    _add_source(
        application,
        provenance_url=provenance_url,
        rights_url=rights_url,
        transformations=[],
    )

    body = TestClient(application).get(
        f'/api/v1/library/editions/{EDITION_CODE}/works/genesis/source'
    ).json()

    assert body['provenance_url'] is None
    assert body['rights_url'] is None
    assert body['transformations'] == []
    assert 'private' not in str(body['provenance_url'])


def test_public_source_detail_returns_stable_not_found_for_unknown_ids(test_settings):
    application = create_application(test_settings)
    _add_source(application)
    client = TestClient(application)

    missing_work = client.get(
        f'/api/v1/library/editions/{EDITION_CODE}/works/not-a-work/source'
    )
    missing_edition = client.get(
        '/api/v1/library/editions/NOT-AN-EDITION/works/genesis/source'
    )

    assert missing_work.status_code == missing_edition.status_code == 404
    assert missing_work.json() == missing_edition.json() == {
        'detail': 'Edition work source not found'
    }


def test_verification_labels_are_complete_and_exact():
    from app.library.schemas import VERIFICATION_LABELS

    assert VERIFICATION_LABELS == {
        'in_progress': 'Source verification in progress',
        'verified_exact': 'Source verified',
        'verified_formatting': 'Verified with documented formatting changes',
        'verified_rebuilt': 'Rebuilt from verified source',
        'review_required': 'Source review required',
    }
