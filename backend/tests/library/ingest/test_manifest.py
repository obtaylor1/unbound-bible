import copy

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


@pytest.mark.parametrize('adapter', ('usfm text', 'usfm/text', '.usfm', 'adapter!'))
def test_manifest_rejects_invalid_adapter_identifiers(adapter):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(adapter=adapter))


@pytest.mark.parametrize(
    'secret_key',
    (
        'secret',
        'CLIENT SECRET',
        'api-key',
        'apikey',
        'token',
        'access-token',
        'password',
        'passwd',
        'Authorization',
        'auth',
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


def test_manifest_rejects_secret_options_nested_in_dicts_and_lists():
    options = {'formats': [{'settings': {'Client-Secret': 'do-not-commit'}}]}

    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(adapter_options=options))


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
