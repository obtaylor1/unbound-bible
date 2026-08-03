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
        'genesis': {'chapters': 50, 'verse_counts': {1: 31, 50: 26}},
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
        {'genesis': {'chapters': 1, 'verse_counts': {0: 1}}},
        {'genesis': {'chapters': 1, 'verse_counts': {2: 1}}},
        {'genesis': {'chapters': 1, 'verse_counts': {1: 0}}},
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


@pytest.mark.parametrize('options', ({'api_key': 'secret'}, {'nested': {'token': 'secret'}}, {'PASSWORD': 'secret'}))
def test_manifest_rejects_secret_adapter_options(options):
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(manifest_with(adapter_options=options))


def test_manifest_defaults_adapter_options_and_round_trips_model_dump():
    value = manifest_with()
    value.pop('adapter_options')

    manifest = SourceManifest.model_validate(value)

    assert manifest.adapter_options == {}
    assert SourceManifest.model_validate(manifest.model_dump(mode='json')).model_dump(mode='json') == manifest.model_dump(mode='json')
