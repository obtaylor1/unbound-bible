import copy
from datetime import date

import pytest
from pydantic import ValidationError

from app.library.ingest.manifest import SourceManifest


VALID = {
    'edition_code': 'KJV',
    'name': 'King James Version',
    'reading_language': 'English',
    'source_language': 'Hebrew/Greek',
    'script': 'Latin',
    'translator': 'KJV translators',
    'publisher': 'Public domain',
    'published_year': 1769,
    'license_spdx': 'LicenseRef-Public-Domain',
    'attribution': 'King James Version, public domain',
    'provenance_url': 'https://ebible.org/find/show.php?id=eng-kjv',
    'source_tradition': 'Masoretic Text / Textus Receptus',
    'relationship': 'general_reading',
    'versification': 'KJV',
    'expected_works': {
        'genesis': {'chapters': 50, 'verse_counts': {'1': 31, '50': 26}},
    },
    'source_files': [{
        'path': 'kjv.txt',
        'sha256': 'a' * 64,
        'source_url': 'https://example.org/kjv.txt',
    }],
    'adapter': 'usfm-text',
    'adapter_options': {'encoding': 'utf-8'},
}


def manifest_with(**changes):
    value = copy.deepcopy(VALID)
    value.update(changes)
    return value


@pytest.mark.parametrize('key', ('license_spdx', 'attribution', 'provenance_url'))
def test_manifest_requires_nonblank_license_attribution_and_provenance(key):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(**{key: ' '}))


def test_manifest_rejects_unsupported_license_and_relationship():
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(license_spdx='All rights reserved'))
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(relationship='ethiopian'))


@pytest.mark.parametrize(
    'key',
    (
        'edition_code', 'name', 'reading_language', 'source_language', 'script',
        'source_tradition', 'versification', 'adapter',
    ),
)
def test_manifest_requires_nonblank_required_text_metadata(key):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(**{key: '  '}))


@pytest.mark.parametrize('key', ('translator', 'publisher'))
def test_manifest_allows_optional_people_only_as_explicit_null(key):
    assert SourceManifest.model_validate(manifest_with(**{key: None})).model_dump()[key] is None
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(**{key: ''}))


@pytest.mark.parametrize('year', (0, -1, 1400, 3000))
def test_manifest_rejects_unreasonable_published_year(year):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(published_year=year))


def test_manifest_allows_explicitly_unknown_published_year():
    assert SourceManifest.model_validate(
        manifest_with(published_year=None)
    ).published_year is None


@pytest.mark.parametrize('published_year', (True, '1769', 1769.0))
def test_manifest_rejects_coerced_published_year_values(published_year):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(published_year=published_year))


def test_manifest_rejects_future_published_year():
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(
            manifest_with(published_year=date.today().year + 1)
        )


def test_manifest_rejects_invalid_provenance_and_extra_fields():
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(provenance_url='not a URL'))
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(unexpected='value'))


@pytest.mark.parametrize(
    'expected_works',
    (
        {},
        {'': {'chapters': 1}},
        {'genesis': {'chapters': 0}},
        {'genesis': {'chapters': 1, 'verse_counts': {'0': 1}}},
        {'genesis': {'chapters': 1, 'verse_counts': {'2': 1}}},
        {'genesis': {'chapters': 1, 'verse_counts': {'1': 0}}},
        {'genesis': {'chapters': 1, 'unknown': True}},
    ),
)
def test_manifest_rejects_invalid_expected_work_coverage(expected_works):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(expected_works=expected_works))


def test_manifest_rejects_duplicate_normalized_work_ids():
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(expected_works={
            'Genesis': {'chapters': 50},
            ' genesis ': {'chapters': 50},
        }))


def test_manifest_rejects_absurd_scripture_coverage_bounds():
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(expected_works={
            'psalms': {'chapters': 201},
        }))
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(expected_works={
            'psalms': {'chapters': 151, 'verse_counts': {'119': 1001}},
        }))


def test_manifest_accepts_generous_ethiopian_scripture_coverage_bounds():
    manifest = SourceManifest.model_validate(manifest_with(expected_works={
        'psalms': {'chapters': 151, 'verse_counts': {'119': 176, '151': 7}},
    }))

    assert manifest.expected_works['psalms'].chapters == 151


@pytest.mark.parametrize(
    'coverage',
    (
        {'chapters': True},
        {'chapters': '50'},
        {'chapters': 50.0},
        {'chapters': 1, 'verse_counts': {1: 31}},
        {'chapters': 1, 'verse_counts': {'1': True}},
        {'chapters': 1, 'verse_counts': {'1': '31'}},
        {'chapters': 1, 'verse_counts': {'1': 31.0}},
    ),
)
def test_manifest_rejects_coverage_type_coercion(coverage):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(
            manifest_with(expected_works={'genesis': coverage})
        )


@pytest.mark.parametrize(
    'source_files',
    (
        [],
        ['https://example.org/kjv.txt'],
        [{'path': '', 'sha256': 'a' * 64}],
        [{'path': 'kjv.txt', 'sha256': 'not-a-checksum'}],
        [{'path': 'kjv.txt', 'sha256': 'a' * 64, 'extra': 'field'}],
        [
            {'path': 'kjv.txt', 'sha256': 'a' * 64},
            {'path': 'kjv.txt', 'sha256': 'b' * 64},
        ],
    ),
)
def test_manifest_rejects_invalid_or_duplicate_source_files(source_files):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(source_files=source_files))


@pytest.mark.parametrize(
    'path',
    (
        '/etc/passwd',
        '.',
        '..',
        './kjv.txt',
        '../kjv.txt',
        'sources/../kjv.txt',
        'sources\\kjv.txt',
        'C:/secrets.txt',
        'C:secrets.txt',
        'z:folder/file.txt',
        'D:.',
        'sources//kjv.txt',
        'sources/',
        'sources/\x00kjv.txt',
        'sources/line\nbreak.txt',
    ),
)
def test_manifest_rejects_unsafe_source_paths(path):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(source_files=[{
            'path': path,
            'sha256': 'a' * 64,
        }]))


def test_manifest_accepts_nested_relative_posix_source_path():
    manifest = SourceManifest.model_validate(manifest_with(source_files=[{
        'path': 'sources/kjv/eng-kjv.usfm',
        'sha256': 'a' * 64,
    }]))

    assert manifest.source_files[0].path == 'sources/kjv/eng-kjv.usfm'


def test_manifest_rejects_casefolded_duplicate_source_paths():
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(source_files=[
            {'path': 'Sources/KJV.txt', 'sha256': 'a' * 64},
            {'path': 'sources/kjv.txt', 'sha256': 'b' * 64},
        ]))


def test_manifest_normalizes_checksum_to_lowercase():
    manifest = SourceManifest.model_validate(manifest_with(source_files=[{
        'path': 'kjv.txt', 'sha256': 'AB' * 32,
    }]))

    assert manifest.source_files[0].sha256 == 'ab' * 32


def test_manifest_rejects_invalid_source_file_url():
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(source_files=[{
            'path': 'kjv.txt',
            'sha256': 'a' * 64,
            'source_url': 'not a URL',
        }]))


@pytest.mark.parametrize('field', ('provenance_url', 'source_url'))
@pytest.mark.parametrize(
    'url',
    (
        'https://user@example.org/kjv.txt',
        'https://user:password@example.org/kjv.txt',
    ),
)
def test_manifest_urls_reject_embedded_credentials(field, url):
    value = manifest_with()
    if field == 'provenance_url':
        value[field] = url
    else:
        value['source_files'][0][field] = url

    with pytest.raises(ValidationError):
        SourceManifest.model_validate(value)


@pytest.mark.parametrize('field', ('provenance_url', 'source_url'))
@pytest.mark.parametrize(
    'query_name',
    ('token', 'key', 'signature', 'auth', 'credential', 'X-API-Key'),
)
def test_manifest_urls_reject_secret_query_parameters(field, query_name):
    url = f'https://example.org/kjv.txt?{query_name}=do-not-commit'
    value = manifest_with()
    if field == 'provenance_url':
        value[field] = url
    else:
        value['source_files'][0][field] = url

    with pytest.raises(ValidationError):
        SourceManifest.model_validate(value)


@pytest.mark.parametrize('field', ('provenance_url', 'source_url'))
@pytest.mark.parametrize(
    'query_name',
    (
        'clientsecret',
        'accesstoken',
        'refreshtoken',
        'privatekey',
        'secretkey',
        'xapikey',
        'apikey',
        'tokenvalue',
        'authorization',
        'bearer',
        'credentials',
        'passwd',
    ),
)
def test_manifest_urls_reject_compact_secret_query_parameters(field, query_name):
    url = f'https://example.org/kjv.txt?{query_name}=do-not-commit'
    value = manifest_with()
    if field == 'provenance_url':
        value[field] = url
    else:
        value['source_files'][0][field] = url

    with pytest.raises(ValidationError):
        SourceManifest.model_validate(value)


@pytest.mark.parametrize('field', ('provenance_url', 'source_url'))
def test_manifest_urls_allow_harmless_configuration_query_parameters(field):
    url = (
        'https://example.org/kjv.txt?auth_method=none&credentials_mode=omit'
        '&requires_authorization=false&max_tokens=1000'
    )
    value = manifest_with()
    if field == 'provenance_url':
        value[field] = url
    else:
        value['source_files'][0][field] = url

    manifest = SourceManifest.model_validate(value)
    assert manifest is not None


@pytest.mark.parametrize('field', ('provenance_url', 'source_url'))
@pytest.mark.parametrize(
    'fragment',
    ('access_token=do-not-commit', 'section=full&token=do-not-commit'),
)
def test_manifest_urls_reject_secret_query_style_fragments(field, fragment):
    url = f'https://example.org/kjv.txt#{fragment}'
    value = manifest_with()
    if field == 'provenance_url':
        value[field] = url
    else:
        value['source_files'][0][field] = url

    with pytest.raises(ValidationError):
        SourceManifest.model_validate(value)


@pytest.mark.parametrize('field', ('provenance_url', 'source_url'))
def test_manifest_urls_allow_normal_anchor_fragments(field):
    url = 'https://example.org/kjv.txt#section-2'
    value = manifest_with()
    if field == 'provenance_url':
        value[field] = url
    else:
        value['source_files'][0][field] = url

    manifest = SourceManifest.model_validate(value)
    assert manifest is not None


SENSITIVE_PARAMETER_NAMES = (
    'accesskey',
    'bearertoken',
    'clientpassword',
    'sessiontoken',
    'basicauth',
    'authorizationheader',
    'encryption_key',
    'signing-key',
    'userPassword',
    'db_password',
    'auth_header',
    'signature',
    'cookie',
    'sessioncookie',
)


SAFE_CONFIGURATION_PARAMETERS = (
    ('auth_type', 'none'),
    ('authorization_scheme', 'none'),
    ('credential_source', 'environment'),
    ('auth_method', 'none'),
    ('credentials_mode', 'omit'),
    ('authorization_required', False),
    ('cookie_enabled', False),
    ('encryption_key_source', 'environment'),
    ('max_tokens', 1000),
)


UNSAFE_CONFIGURATION_PARAMETERS = (
    ('auth_type', 'basic'),
    ('authorization_scheme', 'bearer-value'),
    ('credential_source', 'actual-credential'),
    ('auth_method', 'password'),
    ('credentials_mode', 'embedded'),
    ('authorization_required', 'actual-authorization'),
    ('cookie_enabled', 'session-cookie-value'),
    ('encryption_key_source', 'hardcoded-key'),
)


@pytest.mark.parametrize('field', ('provenance_url', 'source_url'))
@pytest.mark.parametrize('surface', ('query', 'fragment'))
@pytest.mark.parametrize('parameter_name', SENSITIVE_PARAMETER_NAMES)
def test_manifest_url_surfaces_reject_generalized_secret_names(
    field, surface, parameter_name
):
    separator = '?' if surface == 'query' else '#'
    url = f'https://example.org/kjv.txt{separator}{parameter_name}=do-not-commit'
    value = manifest_with()
    if field == 'provenance_url':
        value[field] = url
    else:
        value['source_files'][0][field] = url

    with pytest.raises(ValidationError):
        SourceManifest.model_validate(value)


@pytest.mark.parametrize('field', ('provenance_url', 'source_url'))
@pytest.mark.parametrize('surface', ('query', 'fragment'))
@pytest.mark.parametrize(('name', 'parameter_value'), SAFE_CONFIGURATION_PARAMETERS)
def test_manifest_url_surfaces_allow_safe_configuration_values(
    field, surface, name, parameter_value
):
    serialized_value = str(parameter_value).lower()
    separator = '?' if surface == 'query' else '#'
    url = f'https://example.org/kjv.txt{separator}{name}={serialized_value}'
    value = manifest_with()
    if field == 'provenance_url':
        value[field] = url
    else:
        value['source_files'][0][field] = url

    assert SourceManifest.model_validate(value) is not None


@pytest.mark.parametrize('field', ('provenance_url', 'source_url'))
@pytest.mark.parametrize('surface', ('query', 'fragment'))
@pytest.mark.parametrize(('name', 'parameter_value'), UNSAFE_CONFIGURATION_PARAMETERS)
def test_manifest_url_surfaces_reject_unsafe_configuration_values(
    field, surface, name, parameter_value
):
    separator = '?' if surface == 'query' else '#'
    url = f'https://example.org/kjv.txt{separator}{name}={parameter_value}'
    value = manifest_with()
    if field == 'provenance_url':
        value[field] = url
    else:
        value['source_files'][0][field] = url

    with pytest.raises(ValidationError):
        SourceManifest.model_validate(value)


@pytest.mark.parametrize('adapter', ('usfm text', 'usfm/text', '.usfm', 'adapter!'))
def test_manifest_rejects_invalid_adapter_identifiers(adapter):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(adapter=adapter))


@pytest.mark.parametrize(
    'secret_key',
    (
        'secret',
        'secret_key',
        'CLIENT SECRET',
        'X-API-Key',
        'api-key',
        'apikey',
        'token',
        'token_value',
        'access-token',
        'password',
        'passwd',
        'Authorization',
        'authorization_header',
        'auth',
        'basic_auth',
        'credential',
        'credentials',
        'private key',
        'access-key',
        'bearer',
    ),
)
def test_manifest_rejects_obvious_secret_adapter_options(secret_key):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(
            manifest_with(adapter_options={secret_key: 'do-not-commit'})
        )


@pytest.mark.parametrize(
    'secret_key',
    (
        'clientsecret',
        'accesstoken',
        'refreshtoken',
        'privatekey',
        'secretkey',
        'xapikey',
        'tokenvalue',
    ),
)
def test_manifest_rejects_compact_secret_adapter_options(secret_key):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(
            manifest_with(adapter_options={secret_key: 'do-not-commit'})
        )


@pytest.mark.parametrize('secret_key', SENSITIVE_PARAMETER_NAMES)
def test_manifest_rejects_generalized_secret_adapter_options(secret_key):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(
            manifest_with(adapter_options={secret_key: 'do-not-commit'})
        )


@pytest.mark.parametrize(('name', 'value'), SAFE_CONFIGURATION_PARAMETERS)
def test_manifest_allows_safe_declarative_adapter_options(name, value):
    manifest = SourceManifest.model_validate(
        manifest_with(adapter_options={name: value})
    )

    assert manifest.adapter_options[name] == value


@pytest.mark.parametrize(('name', 'value'), UNSAFE_CONFIGURATION_PARAMETERS)
def test_manifest_rejects_unsafe_declarative_adapter_options(name, value):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(
            manifest_with(adapter_options={name: value})
        )


def test_manifest_rejects_secret_options_nested_in_dicts_and_lists():
    options = {'formats': [{'settings': {'Client-Secret': 'do-not-commit'}}]}

    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(adapter_options=options))


def test_manifest_allows_harmless_token_and_authorization_configuration():
    options = {
        'auth_method': 'none',
        'credentials_mode': 'omit',
        'requires_authorization': False,
        'max_tokens': 1000,
    }

    manifest = SourceManifest.model_validate(manifest_with(adapter_options=options))

    assert manifest.adapter_options == options


@pytest.mark.parametrize('options', (None, [], 'encoding=utf-8'))
def test_manifest_rejects_non_dictionary_adapter_options(options):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(adapter_options=options))


@pytest.mark.parametrize(
    'non_json_value',
    ({'utf-8'}, ('utf-8',), object(), float('nan'), float('inf')),
)
def test_manifest_rejects_non_json_adapter_option_values(non_json_value):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(
            manifest_with(adapter_options={'encoding': non_json_value})
        )


def test_manifest_defaults_adapter_options_and_round_trips_model_dump():
    value = manifest_with()
    value.pop('adapter_options')

    manifest = SourceManifest.model_validate(value)

    assert manifest.adapter_options == {}
    assert SourceManifest.model_validate(manifest.model_dump(mode='json')).model_dump(mode='json') == manifest.model_dump(mode='json')


def test_manifest_enforces_edition_code_database_length_boundary():
    assert len(SourceManifest.model_validate(
        manifest_with(edition_code='e' * 100)
    ).edition_code) == 100

    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(edition_code='e' * 101))


@pytest.mark.parametrize(
    ('field', 'value'),
    (
        ('name', 'n' * 201),
        ('reading_language', 'l' * 65),
        ('source_language', 'l' * 65),
        ('script', 's' * 65),
        ('translator', 't' * 201),
        ('publisher', 'p' * 201),
        ('source_tradition', 't' * 201),
        ('versification', 'v' * 101),
        ('adapter', 'a' * 101),
    ),
)
def test_manifest_rejects_metadata_over_database_or_conservative_bounds(field, value):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(**{field: value}))


def test_manifest_rejects_work_ids_over_database_length():
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(expected_works={
            'w' * 101: {'chapters': 1},
        }))


def test_manifest_rejects_source_paths_over_conservative_length():
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(source_files=[{
            'path': 'p' * 513,
            'sha256': 'a' * 64,
        }]))


def test_manifest_enforces_serialized_url_length_boundary():
    prefix = 'https://example.org/'
    exact_url = prefix + ('a' * (2048 - len(prefix)))
    overlong_url = exact_url + 'a'

    manifest = SourceManifest.model_validate(manifest_with(provenance_url=exact_url))
    assert len(str(manifest.provenance_url)) == 2048

    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(provenance_url=overlong_url))
