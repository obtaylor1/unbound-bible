"""The official Ethiopian Orthodox Tewahedo 81-book canon.

Canon entries are the counted books (46 Old Testament and 35 New Testament).
Some entries contain several separately navigable works; aliases only resolve a
name to a work identifier and never alter the official counted structure.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Work:
    id: str
    name: str
    testament: str
    collection: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonEntry:
    code: str
    name: str
    testament: str
    section: str
    order: int
    work_ids: tuple[str, ...]


def _entries(
    testament: str,
    section_rows: tuple[tuple[str, str, str, tuple[str, ...]], ...],
) -> tuple[CanonEntry, ...]:
    return tuple(
        CanonEntry(code, name, testament, section, index, work_ids)
        for index, (code, name, section, work_ids) in enumerate(section_rows, 1)
    )


OLD_TESTAMENT = _entries('OT', (
    ('genesis', 'Genesis', 'Law', ('genesis',)),
    ('exodus', 'Exodus', 'Law', ('exodus',)),
    ('leviticus', 'Leviticus', 'Law', ('leviticus',)),
    ('numbers', 'Numbers', 'Law', ('numbers',)),
    ('deuteronomy', 'Deuteronomy', 'Law', ('deuteronomy',)),
    ('joshua', 'Joshua', 'History', ('joshua',)),
    ('judges', 'Judges', 'History', ('judges',)),
    ('ruth', 'Ruth', 'History', ('ruth',)),
    ('samuel', 'I and II Samuel', 'History', ('1-samuel', '2-samuel')),
    ('kings', 'I and II Kings', 'History', ('1-kings', '2-kings')),
    ('1-chronicles', 'I Chronicles', 'History', ('1-chronicles',)),
    ('2-chronicles', 'II Chronicles', 'History', ('2-chronicles',)),
    ('jubilees', 'Jubilees', 'History', ('jubilees',)),
    ('1-enoch', 'Enoch', 'History', ('1-enoch',)),
    ('ezra-nehemiah', 'Ezra and Nehemiah', 'History', ('ezra', 'nehemiah')),
    ('second-ezra-sutuel', 'Second Ezra and Ezra Sutuel', 'History', ('second-ezra', 'ezra-sutuel')),
    ('tobit', 'Tobit', 'History', ('tobit',)),
    ('judith', 'Judith', 'History', ('judith',)),
    ('esther', 'Esther', 'History', ('esther', 'esther-greek-additions')),
    ('1-meqabyan', 'I Meqabyan', 'History', ('1-meqabyan',)),
    ('2-3-meqabyan', 'II and III Meqabyan', 'History', ('2-meqabyan', '3-meqabyan')),
    ('job', 'Job', 'Wisdom', ('job',)),
    ('psalms', 'Psalms', 'Wisdom', ('psalms', 'psalm-151')),
    ('proverbs', 'Proverbs', 'Wisdom', ('proverbs',)),
    ('tegsats', 'Tegsats (Reproof)', 'Wisdom', ('tegsats',)),
    ('metsihafe-tibeb', 'Metsihafe Tibeb', 'Wisdom', ('wisdom-of-solomon',)),
    ('ecclesiastes', 'Ecclesiastes', 'Wisdom', ('ecclesiastes',)),
    ('song-of-songs', 'Song of Songs', 'Wisdom', ('song-of-solomon',)),
    ('isaiah', 'Isaiah', 'Prophets', ('isaiah',)),
    ('jeremiah-corpus', 'Jeremiah', 'Prophets', ('jeremiah', 'lamentations', 'baruch', 'letter-of-jeremiah', 'paralipomena-jeremiah')),
    ('ezekiel', 'Ezekiel', 'Prophets', ('ezekiel',)),
    ('daniel-corpus', 'Daniel', 'Prophets', ('daniel', 'prayer-of-azariah', 'susanna', 'bel-and-the-dragon')),
    ('hosea', 'Hosea', 'Minor Prophets', ('hosea',)),
    ('amos', 'Amos', 'Minor Prophets', ('amos',)),
    ('micah', 'Micah', 'Minor Prophets', ('micah',)),
    ('joel', 'Joel', 'Minor Prophets', ('joel',)),
    ('obadiah', 'Obadiah', 'Minor Prophets', ('obadiah',)),
    ('jonah', 'Jonah', 'Minor Prophets', ('jonah',)),
    ('nahum', 'Nahum', 'Minor Prophets', ('nahum',)),
    ('habakkuk', 'Habakkuk', 'Minor Prophets', ('habakkuk',)),
    ('zephaniah', 'Zephaniah', 'Minor Prophets', ('zephaniah',)),
    ('haggai', 'Haggai', 'Minor Prophets', ('haggai',)),
    ('zechariah', 'Zechariah', 'Minor Prophets', ('zechariah',)),
    ('malachi', 'Malachi', 'Minor Prophets', ('malachi',)),
    ('sirach', 'Joshua son of Sirac', 'Wisdom', ('sirach',)),
    ('josippon', 'Josephas son of Bengorion', 'History', ('josippon',)),
))


NEW_TESTAMENT = _entries('NT', (
    ('matthew', 'Matthew', 'Gospels', ('matthew',)),
    ('mark', 'Mark', 'Gospels', ('mark',)),
    ('luke', 'Luke', 'Gospels', ('luke',)),
    ('john', 'John', 'Gospels', ('john',)),
    ('acts', 'Acts', 'History', ('acts',)),
    ('romans', 'Romans', 'Pauline Epistles', ('romans',)),
    ('1-corinthians', 'I Corinthians', 'Pauline Epistles', ('1-corinthians',)),
    ('2-corinthians', 'II Corinthians', 'Pauline Epistles', ('2-corinthians',)),
    ('galatians', 'Galatians', 'Pauline Epistles', ('galatians',)),
    ('ephesians', 'Ephesians', 'Pauline Epistles', ('ephesians',)),
    ('philippians', 'Philippians', 'Pauline Epistles', ('philippians',)),
    ('colossians', 'Colossians', 'Pauline Epistles', ('colossians',)),
    ('1-thessalonians', 'I Thessalonians', 'Pauline Epistles', ('1-thessalonians',)),
    ('2-thessalonians', 'II Thessalonians', 'Pauline Epistles', ('2-thessalonians',)),
    ('1-timothy', 'I Timothy', 'Pauline Epistles', ('1-timothy',)),
    ('2-timothy', 'II Timothy', 'Pauline Epistles', ('2-timothy',)),
    ('titus', 'Titus', 'Pauline Epistles', ('titus',)),
    ('philemon', 'Philemon', 'Pauline Epistles', ('philemon',)),
    ('hebrews', 'Hebrews', 'Pauline Epistles', ('hebrews',)),
    ('1-peter', 'I Peter', 'General Epistles', ('1-peter',)),
    ('2-peter', 'II Peter', 'General Epistles', ('2-peter',)),
    ('1-john', 'I John', 'General Epistles', ('1-john',)),
    ('2-john', 'II John', 'General Epistles', ('2-john',)),
    ('3-john', 'III John', 'General Epistles', ('3-john',)),
    ('james', 'James', 'General Epistles', ('james',)),
    ('jude', 'Jude', 'General Epistles', ('jude',)),
    ('revelation', 'Revelation', 'Apocalypse', ('revelation',)),
    ('sirate-tsion', 'Sirate Tsion', 'Church Orders', ('sirate-tsion',)),
    ('tizaz', 'Tizaz', 'Church Orders', ('tizaz',)),
    ('gitsew', 'Gitsew', 'Church Orders', ('gitsew',)),
    ('abtilis', 'Abtilis', 'Church Orders', ('abtilis',)),
    ('dominos-1', 'I Book of Dominos', 'Church Orders', ('metsihafe-kidan-1',)),
    ('dominos-2', 'II Book of Dominos', 'Church Orders', ('metsihafe-kidan-2',)),
    ('qalementos', 'Book of Clement', 'Church Orders', ('qalementos',)),
    ('didascalia', 'Didascalia', 'Church Orders', ('didesqelya',)),
))


ETHIOPIAN_CANON = OLD_TESTAMENT + NEW_TESTAMENT


def validate_canon(canon: tuple[CanonEntry, ...] = ETHIOPIAN_CANON) -> None:
    """Raise ``ValueError`` when the official counted structure is invalid."""
    entries_by_testament = {
        testament: tuple(entry for entry in canon if entry.testament == testament)
        for testament in ('OT', 'NT')
    }
    expected_counts = {'OT': 46, 'NT': 35}

    if len(canon) != 81:
        raise ValueError('The Ethiopian canon must contain 81 counted entries.')
    expected_sequence = ('OT',) * 46 + ('NT',) * 35
    if tuple(entry.testament for entry in canon) != expected_sequence:
        raise ValueError('The canon must place all OT entries before all NT entries.')
    for testament, expected_count in expected_counts.items():
        entries = entries_by_testament[testament]
        if len(entries) != expected_count:
            raise ValueError(f'The Ethiopian {testament} must contain {expected_count} entries.')
        if tuple(entry.order for entry in entries) != tuple(range(1, expected_count + 1)):
            raise ValueError(f'The Ethiopian {testament} order must be consecutive.')
    if len({entry.code for entry in canon}) != len(canon):
        raise ValueError('Canon entry codes must be unique.')
    if any(not entry.work_ids for entry in canon):
        raise ValueError('Every canon entry must include at least one work.')
    work_owner: dict[str, str] = {}
    for entry in canon:
        for work_id in entry.work_ids:
            existing_owner = work_owner.setdefault(work_id, entry.code)
            if existing_owner != entry.code:
                raise ValueError('Every work must belong to exactly one counted entry.')


validate_canon()


_DISPLAY_NAMES = {
    'genesis': 'Genesis', 'exodus': 'Exodus', 'leviticus': 'Leviticus', 'numbers': 'Numbers',
    'deuteronomy': 'Deuteronomy', 'joshua': 'Joshua', 'judges': 'Judges', 'ruth': 'Ruth',
    '1-samuel': '1 Samuel', '2-samuel': '2 Samuel', '1-kings': '1 Kings', '2-kings': '2 Kings',
    '1-chronicles': '1 Chronicles', '2-chronicles': '2 Chronicles', 'jubilees': 'Jubilees',
    '1-enoch': '1 Enoch', 'ezra': 'Ezra', 'nehemiah': 'Nehemiah', 'second-ezra': '2 Esdras',
    'ezra-sutuel': '1 Esdras', 'tobit': 'Tobit', 'judith': 'Judith', 'esther': 'Esther',
    'esther-greek-additions': 'Esther (Greek Additions)', '1-meqabyan': '1 Meqabyan',
    '2-meqabyan': '2 Meqabyan', '3-meqabyan': '3 Meqabyan', 'job': 'Job', 'psalms': 'Psalms',
    'psalm-151': 'Psalm 151', 'proverbs': 'Proverbs', 'tegsats': 'Tegsats',
    'wisdom-of-solomon': 'Wisdom of Solomon', 'ecclesiastes': 'Ecclesiastes',
    'song-of-solomon': 'Song of Solomon', 'isaiah': 'Isaiah', 'jeremiah': 'Jeremiah',
    'lamentations': 'Lamentations', 'baruch': 'Baruch', 'letter-of-jeremiah': 'Letter of Jeremiah',
    'paralipomena-jeremiah': 'Paralipomena of Jeremiah', 'ezekiel': 'Ezekiel', 'daniel': 'Daniel',
    'prayer-of-azariah': 'Prayer of Azariah', 'susanna': 'Susanna',
    'bel-and-the-dragon': 'Bel and the Dragon', 'hosea': 'Hosea', 'amos': 'Amos', 'micah': 'Micah',
    'joel': 'Joel', 'obadiah': 'Obadiah', 'jonah': 'Jonah', 'nahum': 'Nahum',
    'habakkuk': 'Habakkuk', 'zephaniah': 'Zephaniah', 'haggai': 'Haggai', 'zechariah': 'Zechariah',
    'malachi': 'Malachi', 'sirach': 'Sirach', 'josippon': 'Josippon', 'matthew': 'Matthew',
    'mark': 'Mark', 'luke': 'Luke', 'john': 'John', 'acts': 'Acts', 'romans': 'Romans',
    '1-corinthians': '1 Corinthians', '2-corinthians': '2 Corinthians', 'galatians': 'Galatians',
    'ephesians': 'Ephesians', 'philippians': 'Philippians', 'colossians': 'Colossians',
    '1-thessalonians': '1 Thessalonians', '2-thessalonians': '2 Thessalonians',
    '1-timothy': '1 Timothy', '2-timothy': '2 Timothy', 'titus': 'Titus', 'philemon': 'Philemon',
    'hebrews': 'Hebrews', '1-peter': '1 Peter', '2-peter': '2 Peter', '1-john': '1 John',
    '2-john': '2 John', '3-john': '3 John', 'james': 'James', 'jude': 'Jude',
    'revelation': 'Revelation', 'sirate-tsion': 'Sirate Tsion', 'tizaz': 'Tizaz',
    'gitsew': 'Gitsiw', 'abtilis': 'Abtilis', 'metsihafe-kidan-1': 'Metsihafe Kidan I',
    'metsihafe-kidan-2': 'Metsihafe Kidan II', 'qalementos': 'Qalëmentos',
    'didesqelya': 'Didesqelya',
}

_WORK_ALIASES = {
    '1-enoch': ('Enoch',),
    '1-meqabyan': ('Meqabyan 1', 'I Meqabyan'),
    '2-meqabyan': ('Meqabyan 2', 'II Meqabyan'),
    '3-meqabyan': ('Meqabyan 3', 'III Meqabyan'),
    'second-ezra': ('Second Ezra',),
    'ezra-sutuel': ('Ezra Sutuel',),
    'tegsats': ('Tegsats (Reproof)', 'Reproof'),
    'wisdom-of-solomon': ('Metsihafe Tibeb',),
    'song-of-solomon': ('Song of Songs', 'Canticles'),
    'sirach': ('Joshua son of Sirac', 'Joshua son of Sirach'),
    'josippon': ('Josephas son of Bengorion', 'Josephus son of Bengorion', 'Book of Josephus'),
    'gitsew': ('Gitsew',),
    'metsihafe-kidan-1': (
        'I Book of Dominos', '1st Book of Dominos', 'Book of Dominos I', 'Book of the Covenant I',
    ),
    'metsihafe-kidan-2': (
        'II Book of Dominos', '2nd Book of Dominos', 'Book of Dominos II', 'Book of the Covenant II',
    ),
    'qalementos': ('Book of Clement', 'Book of Qäləmentos', 'Clement 2'),
    'didesqelya': ('Didascalia', 'Didaskalia'),
}

_ROMAN_NUMERALS = {'1': 'I', '2': 'II', '3': 'III'}


def _numbered_aliases(work_id: str, name: str) -> tuple[str, ...]:
    number, _, title = work_id.partition('-')
    if number not in _ROMAN_NUMERALS:
        return ()
    return (f'{_ROMAN_NUMERALS[number]} {title.replace("-", " ").title()}',)


def _canonical_work_ids() -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        work_id
        for entry in ETHIOPIAN_CANON
        for work_id in entry.work_ids
    ))


WORKS = tuple(
    Work(
        id=work_id,
        name=_DISPLAY_NAMES[work_id],
        testament=next(entry.testament for entry in ETHIOPIAN_CANON if work_id in entry.work_ids),
        collection=next(entry.section for entry in ETHIOPIAN_CANON if work_id in entry.work_ids),
        aliases=_WORK_ALIASES.get(work_id, ()) + _numbered_aliases(work_id, _DISPLAY_NAMES[work_id]),
    )
    for work_id in _canonical_work_ids()
)
_WORKS_BY_ID = {work.id: work for work in WORKS}


# The ordered Protestant canon is the common standard-canon baseline.  The
# Catholic canon preserves that order and inserts its seven additional works at
# their canonical reading positions.
PROTESTANT_WORK_IDS = (
    'genesis', 'exodus', 'leviticus', 'numbers', 'deuteronomy',
    'joshua', 'judges', 'ruth', '1-samuel', '2-samuel', '1-kings', '2-kings',
    '1-chronicles', '2-chronicles', 'ezra', 'nehemiah', 'esther', 'job', 'psalms',
    'proverbs', 'ecclesiastes', 'song-of-solomon', 'isaiah', 'jeremiah',
    'lamentations', 'ezekiel', 'daniel', 'hosea', 'joel', 'amos', 'obadiah',
    'jonah', 'micah', 'nahum', 'habakkuk', 'zephaniah', 'haggai', 'zechariah',
    'malachi', 'matthew', 'mark', 'luke', 'john', 'acts', 'romans',
    '1-corinthians', '2-corinthians', 'galatians', 'ephesians', 'philippians',
    'colossians', '1-thessalonians', '2-thessalonians', '1-timothy', '2-timothy',
    'titus', 'philemon', 'hebrews', 'james', '1-peter', '2-peter', '1-john',
    '2-john', '3-john', 'jude', 'revelation',
)


def _insert_after(
    work_ids: tuple[str, ...],
    anchor: str,
    additions: tuple[str, ...],
) -> tuple[str, ...]:
    position = work_ids.index(anchor) + 1
    return work_ids[:position] + additions + work_ids[position:]


def _insert_before(
    work_ids: tuple[str, ...],
    anchor: str,
    additions: tuple[str, ...],
) -> tuple[str, ...]:
    position = work_ids.index(anchor)
    return work_ids[:position] + additions + work_ids[position:]


CATHOLIC_WORK_IDS = _insert_before(
    PROTESTANT_WORK_IDS, 'esther', ('tobit', 'judith')
)
CATHOLIC_WORK_IDS = _insert_after(
    CATHOLIC_WORK_IDS, 'esther', ('1-maccabees', '2-maccabees')
)
CATHOLIC_WORK_IDS = _insert_after(
    CATHOLIC_WORK_IDS, 'song-of-solomon', ('wisdom-of-solomon', 'sirach')
)
CATHOLIC_WORK_IDS = _insert_after(CATHOLIC_WORK_IDS, 'lamentations', ('baruch',))


# These are legitimate library works for the Catholic catalog, but they are not
# Ethiopian canon navigation works and must never be added to ``WORKS``.
SUPPLEMENTAL_LIBRARY_WORKS = (
    Work('1-maccabees', '1 Maccabees', 'OT', 'History', ('I Maccabees',)),
    Work('2-maccabees', '2 Maccabees', 'OT', 'History', ('II Maccabees',)),
)


def _validate_standard_canons() -> None:
    if len(PROTESTANT_WORK_IDS) != 66 or len(set(PROTESTANT_WORK_IDS)) != 66:
        raise ValueError('The Protestant canon must contain 66 unique works.')
    if len(CATHOLIC_WORK_IDS) != 73 or len(set(CATHOLIC_WORK_IDS)) != 73:
        raise ValueError('The Catholic canon must contain 73 unique works.')
    available_work_ids = {
        work.id for work in (*WORKS, *SUPPLEMENTAL_LIBRARY_WORKS)
    }
    missing = set(CATHOLIC_WORK_IDS) - available_work_ids
    if missing:
        raise ValueError(f'Standard canon works lack library metadata: {sorted(missing)}')


_validate_standard_canons()


def _normalized_alias(value: str) -> str:
    return ' '.join(value.split()).casefold()


def _build_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}

    for work in (*WORKS, *SUPPLEMENTAL_LIBRARY_WORKS):
        for name in (work.name, *work.aliases):
            key = _normalized_alias(name)
            existing = aliases.setdefault(key, work.id)
            if existing != work.id:
                raise ValueError(f'Alias {name!r} targets both {existing!r} and {work.id!r}.')

    # These historic/current UI spellings remain distinct lookup targets even
    # though Greek Maccabees and Prayer of Manasseh are not counted EOTC entries.
    aliases.update({
        '3 maccabees': '3-maccabees',
        'iii maccabees': '3-maccabees',
        '4 maccabees': '4-maccabees',
        'iv maccabees': '4-maccabees',
        'prayer of manasseh': 'prayer-of-manasseh',
        'antiquities': 'antiquities',
        'genesis targum': 'genesis-targum',
    })
    return aliases


ALIASES = _build_aliases()


def alias_target(name: str) -> str | None:
    """Resolve a case-insensitive, whitespace-tolerant alias, or return ``None``."""
    if not isinstance(name, str):
        return None
    return ALIASES.get(_normalized_alias(name))


def navigation_works() -> tuple[Work, ...]:
    """Return each canonical work once, in official first-occurrence order."""
    return tuple(_WORKS_BY_ID[work_id] for work_id in _canonical_work_ids())
