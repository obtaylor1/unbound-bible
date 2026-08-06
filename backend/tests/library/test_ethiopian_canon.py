from dataclasses import replace

import pytest

from app.library.canon import (
    ETHIOPIAN_CANON,
    SUPPLEMENTAL_LIBRARY_WORKS,
    WORKS,
    alias_target,
    navigation_works,
    validate_canon,
)


def test_official_ethiopian_canon_has_46_old_and_35_new_entries():
    old = [entry for entry in ETHIOPIAN_CANON if entry.testament == 'OT']
    new = [entry for entry in ETHIOPIAN_CANON if entry.testament == 'NT']

    assert len(ETHIOPIAN_CANON) == 81
    assert len(old) == 46
    assert len(new) == 35
    assert [entry.order for entry in old] == list(range(1, 47))
    assert [entry.order for entry in new] == list(range(1, 36))


def test_canon_validation_rejects_new_testament_entry_before_old_testament_ends():
    interleaved = (
        ETHIOPIAN_CANON[:45]
        + (ETHIOPIAN_CANON[46], ETHIOPIAN_CANON[45])
        + ETHIOPIAN_CANON[47:]
    )

    with pytest.raises(ValueError, match='all OT entries before all NT entries'):
        validate_canon(interleaved)


def test_canon_validation_rejects_work_owned_by_multiple_counted_entries():
    duplicate_owner = replace(ETHIOPIAN_CANON[1], work_ids=('genesis',))
    canon = (ETHIOPIAN_CANON[0], duplicate_owner, *ETHIOPIAN_CANON[2:])

    with pytest.raises(ValueError, match='exactly one counted entry'):
        validate_canon(canon)


def test_composite_entries_count_once_but_keep_navigable_works():
    samuel = next(entry for entry in ETHIOPIAN_CANON if entry.code == 'samuel')

    assert samuel.work_ids == ('1-samuel', '2-samuel')
    assert {'1-samuel', '2-samuel'} <= {work.id for work in navigation_works()}


def test_navigation_works_are_deduplicated_in_official_first_occurrence_order():
    work_ids = [work.id for work in navigation_works()]

    assert work_ids == [work.id for work in navigation_works()]
    assert work_ids == list(dict.fromkeys(work_ids))
    assert work_ids[:10] == [
        'genesis',
        'exodus',
        'leviticus',
        'numbers',
        'deuteronomy',
        'joshua',
        'judges',
        'ruth',
        '1-samuel',
        '2-samuel',
    ]


def test_ethiopian_names_resolve_without_conflating_meqabyan_and_maccabees():
    assert alias_target('Meqabyan 1') == '1-meqabyan'
    assert alias_target('1 Maccabees') == '1-maccabees'
    assert alias_target('Meqabyan 1') != alias_target('1 Maccabees')


def test_existing_ingest_report_names_resolve_to_canonical_works():
    assert alias_target('Book of Josephus') == 'josippon'
    assert alias_target('1st Book of Dominos') == 'metsihafe-kidan-1'
    assert alias_target('2nd Book of Dominos') == 'metsihafe-kidan-2'


def test_alias_lookup_normalizes_case_and_whitespace_and_returns_none_when_unknown():
    assert alias_target('  meQABYan   1  ') == '1-meqabyan'
    assert alias_target('Unknown Canonical Work') is None


def test_legacy_frontend_only_titles_keep_stable_lookup_targets():
    assert alias_target('Antiquities') == 'antiquities'
    assert alias_target('Genesis Targum') == 'genesis-targum'


def test_prayer_of_manasseh_is_supplemental_without_changing_ethiopian_canon_works():
    supplemental = {work.id: work for work in SUPPLEMENTAL_LIBRARY_WORKS}

    assert supplemental['prayer-of-manasseh'].name == 'Prayer of Manasseh'
    assert supplemental['prayer-of-manasseh'].aliases == ('Prayer of Manasses',)
    assert 'prayer-of-manasseh' not in {work.id for work in WORKS}
    assert all(
        'prayer-of-manasseh' not in entry.work_ids
        for entry in ETHIOPIAN_CANON
    )
