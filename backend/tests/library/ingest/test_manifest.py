import copy
from datetime import date

import pytest
from pydantic import ValidationError

from app.library.ingest.manifest import SourceManifest, WorkSourceManifest


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
    'adapter': 'usfm',
    'adapter_options': {'encoding': 'utf-8'},
}


def manifest_with(**changes):
    value = copy.deepcopy(VALID)
    value.update(changes)
    return value


def work_source(**changes):
    value = {
        'source_key': 'GEN',
        'source_label': 'World English Bible',
        'translator': None,
        'source_language': 'Hebrew',
        'source_tradition': 'Masoretic Text',
        'published_year': 2020,
        'license_spdx': 'CC0-1.0',
        'attribution': 'World English Bible, public domain',
        'provenance_url': 'https://example.org/web/genesis',
        'fallback': False,
        'modified': False,
        'modification_note': None,
        'verification_status': 'verified',
        'canon_scope': 'ethio81',
    }
    value.update(changes)
    return value


def composite_options(**changes):
    value = {
        'book_map': {'GEN': 'genesis', 'ENO': '1-enoch'},
        'work_sources': {
            'genesis': work_source(),
            '1-enoch': work_source(
                source_key='ENO',
                source_label='Provisional Enoch translation',
                provenance_url=None,
                verification_status='provisional',
                canon_scope='supplemental',
            ),
        },
        'supplemental_works': ['1-enoch'],
    }
    value.update(changes)
    return value


def composite_manifest(**changes):
    value = manifest_with(
        license_spdx='LicenseRef-Mixed',
        expected_works={
            'genesis': {'chapters': 50},
            '1-enoch': {'chapters': 108},
        },
        adapter='composite_english_bundle',
        adapter_options=composite_options(),
        source_verification='provisional',
    )
    value.update(changes)
    return value


def test_verified_work_source_requires_provenance_url():
    with pytest.raises(ValidationError, match='verified work source requires provenance_url'):
        WorkSourceManifest.model_validate(work_source(provenance_url=None))


def test_modified_work_source_requires_modification_note():
    with pytest.raises(ValidationError, match='modified work source requires modification_note'):
        WorkSourceManifest.model_validate(work_source(modified=True))


def test_unmodified_work_source_defaults_omitted_modification_note_to_none():
    value = work_source()
    value.pop('modification_note')

    source = WorkSourceManifest.model_validate(value)

    assert source.modification_note is None
    assert 'modification_note' not in WorkSourceManifest.model_json_schema()['required']


def test_work_source_rejects_extra_fields_and_coerced_booleans():
    with pytest.raises(ValidationError):
        WorkSourceManifest.model_validate(work_source(unexpected='value'))
    with pytest.raises(ValidationError):
        WorkSourceManifest.model_validate(work_source(fallback=1))


def test_composite_manifest_accepts_mixed_license_and_normalizes_mapping_keys():
    options = composite_options(book_map={' gen ': 'genesis', 'ENO': '1-enoch'})
    manifest = SourceManifest.model_validate(composite_manifest(adapter_options=options))

    assert manifest.license_spdx == 'LicenseRef-Mixed'
    assert manifest.adapter_options.book_map == {'gen': 'genesis', 'ENO': '1-enoch'}


def test_composite_adapter_rejects_duplicate_book_map_targets():
    options = composite_options(book_map={'GEN': 'genesis', 'GEN-alt': 'genesis'})

    with pytest.raises(ValidationError, match='multiple source books to one work'):
        SourceManifest.model_validate(composite_manifest(adapter_options=options))


@pytest.mark.parametrize(
    'work_sources',
    (
        {'genesis': work_source()},
        {
            'genesis': work_source(),
            '1-enoch': work_source(
                source_key='ENO', verification_status='provisional',
                provenance_url=None, canon_scope='supplemental',
            ),
            'jubilees': work_source(source_key='JUB'),
        },
    ),
)
def test_composite_work_sources_must_exactly_match_book_map_targets(work_sources):
    with pytest.raises(ValidationError, match='work_sources keys must exactly match book_map targets'):
        SourceManifest.model_validate(composite_manifest(
            adapter_options=composite_options(work_sources=work_sources),
        ))


def test_composite_work_source_keys_use_safe_normalized_work_ids():
    sources = composite_options()['work_sources']
    sources[' genesis '] = sources.pop('genesis')
    manifest = SourceManifest.model_validate(composite_manifest(
        adapter_options=composite_options(work_sources=sources),
    ))
    assert set(manifest.adapter_options.work_sources) == {'genesis', '1-enoch'}

    sources = composite_options()['work_sources']
    sources[' Genesis '] = work_source()
    with pytest.raises(ValidationError, match='duplicate normalized work IDs'):
        SourceManifest.model_validate(composite_manifest(
            adapter_options=composite_options(work_sources=sources),
        ))


def test_composite_supplemental_works_must_be_mapped_targets():
    with pytest.raises(ValidationError, match='supplemental_works must be a subset'):
        SourceManifest.model_validate(composite_manifest(
            adapter_options=composite_options(supplemental_works=['jubilees']),
        ))


@pytest.mark.parametrize(
    ('supplemental_works', 'work_sources'),
    (
        (['1-enoch'], {
            'genesis': work_source(),
            '1-enoch': work_source(
                source_key='ENO', provenance_url=None,
                verification_status='provisional', canon_scope='ethio81',
            ),
        }),
        ([], {
            'genesis': work_source(),
            '1-enoch': work_source(
                source_key='ENO', provenance_url=None,
                verification_status='provisional', canon_scope='supplemental',
            ),
        }),
    ),
)
def test_composite_work_source_canon_scope_agrees_with_supplemental_membership(
    supplemental_works, work_sources
):
    with pytest.raises(ValidationError, match='canon_scope'):
        SourceManifest.model_validate(composite_manifest(adapter_options=composite_options(
            supplemental_works=supplemental_works,
            work_sources=work_sources,
        )))


def test_verified_source_manifest_rejects_provisional_work_source():
    value = composite_manifest(source_verification='verified')

    with pytest.raises(ValidationError, match='verified source_verification requires all work sources'):
        SourceManifest.model_validate(value)


def test_provisional_source_manifest_accepts_provisional_work_source():
    manifest = SourceManifest.model_validate(composite_manifest())
    assert manifest.source_verification == 'provisional'


def test_existing_manifest_defaults_source_verification_to_verified():
    manifest = SourceManifest.model_validate(manifest_with())
    assert manifest.source_verification == 'verified'


def test_composite_schema_correlates_adapter_with_strict_options():
    jsonschema = pytest.importorskip('jsonschema')
    schema = SourceManifest.model_json_schema()
    correlations = {
        branch['if']['properties']['adapter']['const']:
            branch['then']['properties']['adapter_options']
        for branch in schema['allOf']
    }
    composite_schema = correlations['composite_english_bundle']
    assert composite_schema['additionalProperties'] is False
    assert set(composite_schema['required']) == {'book_map', 'work_sources'}
    assert (
        composite_schema['properties']['work_sources']['additionalProperties']
        ['additionalProperties']
        is False
    )

    validator = jsonschema.Draft202012Validator(schema)
    assert not list(validator.iter_errors(composite_manifest()))
    invalid = composite_manifest()
    invalid['adapter_options']['unknown'] = True
    assert list(validator.iter_errors(invalid))


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
def test_manifest_urls_allow_normal_anchor_fragments(field):
    url = 'https://example.org/kjv.txt#section-2'
    value = manifest_with()
    if field == 'provenance_url':
        value[field] = url
    else:
        value['source_files'][0][field] = url

    manifest = SourceManifest.model_validate(value)
    assert manifest is not None


URL_SECRET_PARAMETER_NAMES = (
    'sig', 'key', 'auth', 'authorization', 'bearer', 'token', 'access_token',
    'secret', 'password', 'passwd', 'credential', 'credentials', 'signature',
    'apitoken', 'oauthclientsecret', 'jwtsecret', 'databasepassword',
    'accesskey', 'bearertoken', 'clientpassword', 'sessiontoken', 'basicauth',
    'authorizationheader', 'X-API-Key', 'private_key', 'signing_key',
    'encryption_key', 'session_key', 'token_value', 'tokenvalue',
    'password_value', 'client_secret_value', 'signature_value',
    'credential_value', 'api_key_value', 'privatekeyvalue', 'sessioncookie',
    'session_cookie',
)
URL_SAFE_PARAMETERS = (
    ('book_key', 'genesis'),
    ('chapter_key', 'chapter'),
    ('sort_key', 'canonical'),
    ('signature_algorithm', 'sha256'),
    ('auth_type', 'none'),
    ('authorization_scheme', 'none'),
    ('credential_source', 'environment'),
)


@pytest.mark.parametrize('field', ('provenance_url', 'source_url'))
@pytest.mark.parametrize('surface', ('query', 'fragment'))
def test_manifest_url_policy_rejects_secret_names(field, surface):
    separator = '?' if surface == 'query' else '#'
    for parameter_name in URL_SECRET_PARAMETER_NAMES:
        url = f'https://example.org/kjv.txt{separator}{parameter_name}=value'
        value = manifest_with()
        if field == 'provenance_url':
            value[field] = url
        else:
            value['source_files'][0][field] = url
        with pytest.raises(ValidationError):
            SourceManifest.model_validate(value)


@pytest.mark.parametrize('field', ('provenance_url', 'source_url'))
@pytest.mark.parametrize('surface', ('query', 'fragment'))
def test_manifest_url_policy_allows_ordinary_names(field, surface):
    separator = '?' if surface == 'query' else '#'
    query = '&'.join(f'{name}={value}' for name, value in URL_SAFE_PARAMETERS)
    url = f'https://example.org/kjv.txt{separator}{query}'
    value = manifest_with()
    if field == 'provenance_url':
        value[field] = url
    else:
        value['source_files'][0][field] = url

    assert SourceManifest.model_validate(value) is not None


@pytest.mark.parametrize(
    ('adapter', 'expected'),
    (
        ('usfm', {'encoding': 'utf-8', 'book_map': {}, 'strip_notes': False}),
        ('ertale', {'encoding': 'utf-8', 'book_map': {}}),
        ('wikisource', {'encoding': 'utf-8', 'page_map': {}}),
    ),
)
def test_manifest_defaults_typed_options_for_each_adapter(adapter, expected):
    value = manifest_with(adapter=adapter)
    value.pop('adapter_options')

    manifest = SourceManifest.model_validate(value)

    assert manifest.model_dump(mode='json')['adapter_options'] == expected


def test_manifest_schema_does_not_require_adapter_options():
    assert 'adapter_options' not in SourceManifest.model_json_schema()['required']


def test_manifest_schema_correlates_adapters_with_option_definitions():
    schema = SourceManifest.model_json_schema()
    expected_definitions = {
        'usfm': 'UsfmAdapterOptions',
        'ertale': 'ErtaleAdapterOptions',
        'wikisource': 'WikisourceAdapterOptions',
        'weahadu_bundle': 'WeahaduBundleAdapterOptions',
    }

    correlations = {
        branch['if']['properties']['adapter']['const']:
            branch['then']['properties']['adapter_options']
        for branch in schema['allOf']
    }

    assert {
        adapter: correlation
        for adapter, correlation in correlations.items()
        if adapter != 'composite_english_bundle'
    } == {
        adapter: schema['$defs'][definition]
        for adapter, definition in expected_definitions.items()
    }
    assert correlations['composite_english_bundle']['additionalProperties'] is False


def test_manifest_schema_validator_enforces_adapter_option_correlation():
    jsonschema = pytest.importorskip('jsonschema')
    validator = jsonschema.Draft202012Validator(SourceManifest.model_json_schema())
    matching_options = {
        'usfm': {'strip_notes': True},
        'ertale': {'book_map': {'GEN': 'genesis'}},
        'wikisource': {'page_map': {'Genesis 1': 'genesis'}},
    }

    for adapter, adapter_options in matching_options.items():
        matching = manifest_with(adapter=adapter, adapter_options=adapter_options)
        assert not list(validator.iter_errors(matching))

        omitted = manifest_with(adapter=adapter)
        omitted.pop('adapter_options')
        assert not list(validator.iter_errors(omitted))

    mismatched = manifest_with(
        adapter='usfm',
        adapter_options={'page_map': {'Genesis 1': 'genesis'}},
    )
    assert list(validator.iter_errors(mismatched))


@pytest.mark.parametrize(
    ('adapter', 'options', 'mapping_name'),
    (
        ('usfm', {
            'encoding': 'utf-8-sig',
            'book_map': {'GEN': 'genesis'},
            'strip_notes': True,
        }, 'book_map'),
        ('ertale', {
            'encoding': 'utf-8',
            'book_map': {'1-Enoch': '1-enoch'},
        }, 'book_map'),
        ('wikisource', {
            'encoding': 'utf-8',
            'page_map': {'Bible/Genesis 1': 'genesis'},
        }, 'page_map'),
    ),
)
def test_manifest_accepts_adapter_specific_options(adapter, options, mapping_name):
    manifest = SourceManifest.model_validate(
        manifest_with(adapter=adapter, adapter_options=options)
    )

    assert manifest.model_dump(mode='json')['adapter_options'][mapping_name]


@pytest.mark.parametrize(
    ('adapter', 'adapter_options'),
    (
        ('ertale', {'strip_notes': True}),
        ('usfm', {'page_map': {'Genesis 1': 'genesis'}}),
        ('wikisource', {'book_map': {'GEN': 'genesis'}}),
    ),
)
def test_manifest_rejects_options_belonging_to_another_adapter(
    adapter, adapter_options
):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(
            manifest_with(adapter=adapter, adapter_options=adapter_options)
        )


@pytest.mark.parametrize('adapter', ('usfm-text', 'custom', '', 'USFM', ['usfm']))
def test_manifest_rejects_unapproved_adapters(adapter):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(adapter=adapter))


@pytest.mark.parametrize(
    'adapter_options',
    (
        {'unknown': True},
        {'max_tokens': 1_000},
        {'nested': {'setting': True}},
        {'api_key': 'do-not-commit'},
        {'password': 'do-not-commit'},
        {'encoding': 'latin-1'},
        {'encoding': object()},
        {'book_map': {'GEN': {'nested': 'value'}}},
    ),
)
def test_manifest_rejects_unimplemented_or_invalid_usfm_options(adapter_options):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(
            manifest_with(adapter='usfm', adapter_options=adapter_options)
        )


@pytest.mark.parametrize('adapter_options', (None, [], 'encoding=utf-8'))
def test_manifest_rejects_non_dictionary_adapter_options(adapter_options):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(
            manifest_with(adapter='usfm', adapter_options=adapter_options)
        )


@pytest.mark.parametrize(
    ('adapter', 'mapping_name', 'mapping'),
    (
        ('usfm', 'book_map', {'../GEN': 'genesis'}),
        ('ertale', 'book_map', {'': 'genesis'}),
        ('wikisource', 'page_map', {'': 'genesis'}),
        ('usfm', 'book_map', {'GEN': ''}),
        ('wikisource', 'page_map', {'Genesis': 'w' * 101}),
    ),
)
def test_manifest_rejects_invalid_adapter_mappings(adapter, mapping_name, mapping):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(
            adapter=adapter,
            adapter_options={mapping_name: mapping},
        ))


@pytest.mark.parametrize(
    ('adapter', 'mapping_name', 'mapping'),
    (
        ('usfm', 'book_map', {'GEN': 'genesis', ' gen ': 'exodus'}),
        ('ertale', 'book_map', {'1-Enoch': '1-enoch', ' 1-Enoch ': 'enoch'}),
        ('wikisource', 'page_map', {'Genesis 1': 'genesis', ' Genesis 1 ': 'exodus'}),
        ('wikisource', 'page_map', {'Café': 'genesis', 'Café': 'exodus'}),
    ),
)
def test_manifest_rejects_normalized_adapter_mapping_key_collisions(
    adapter, mapping_name, mapping
):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(
            adapter=adapter,
            adapter_options={mapping_name: mapping},
        ))


def test_manifest_adapter_option_errors_include_public_field_location():
    with pytest.raises(ValidationError) as exc_info:
        SourceManifest.model_validate(manifest_with(adapter_options={
            'book_map': {'GEN': 'genesis', ' GEN ': 'exodus'},
        }))

    assert exc_info.value.errors()[0]['loc'][:2] == ('adapter_options', 'book_map')


@pytest.mark.parametrize(
    ('adapter', 'mapping_name', 'mapping'),
    (
        ('usfm', 'book_map', {' GEN ': 'genesis', 'EXO': 'exodus'}),
        ('ertale', 'book_map', {' 1-Enoch ': '1-enoch', 'Jubilees': 'jubilees'}),
        ('wikisource', 'page_map', {' Genesis 1 ': 'genesis', 'Genesis 2': 'genesis'}),
    ),
)
def test_manifest_normalizes_and_preserves_distinct_adapter_mapping_keys(
    adapter, mapping_name, mapping
):
    manifest = SourceManifest.model_validate(manifest_with(
        adapter=adapter,
        adapter_options={mapping_name: mapping},
    ))

    assert manifest.model_dump(mode='json')['adapter_options'][mapping_name] == {
        key.strip(): value for key, value in mapping.items()
    }


def test_manifest_typed_adapter_options_round_trip_as_dictionary():
    manifest = SourceManifest.model_validate(manifest_with(adapter_options={
        'encoding': 'utf-8-sig',
        'book_map': {'GEN': 'genesis'},
        'strip_notes': True,
    }))
    dumped = manifest.model_dump(mode='json')

    assert isinstance(dumped['adapter_options'], dict)
    assert SourceManifest.model_validate(dumped).model_dump(mode='json') == dumped


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
