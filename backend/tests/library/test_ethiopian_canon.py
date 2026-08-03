from app.library.canon import ETHIOPIAN_CANON, alias_target, navigation_works


def test_official_ethiopian_canon_has_46_old_and_35_new_entries():
    old = [entry for entry in ETHIOPIAN_CANON if entry.testament == 'OT']
    new = [entry for entry in ETHIOPIAN_CANON if entry.testament == 'NT']

    assert len(ETHIOPIAN_CANON) == 81
    assert len(old) == 46
    assert len(new) == 35
    assert [entry.order for entry in old] == list(range(1, 47))
    assert [entry.order for entry in new] == list(range(1, 36))


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


def test_alias_lookup_normalizes_case_and_whitespace_and_returns_none_when_unknown():
    assert alias_target('  meQABYan   1  ') == '1-meqabyan'
    assert alias_target('Unknown Canonical Work') is None


def test_legacy_frontend_only_titles_keep_stable_lookup_targets():
    assert alias_target('Antiquities') == 'antiquities'
    assert alias_target('Genesis Targum') == 'genesis-targum'
