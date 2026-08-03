# Ethiopian Bible Phase 1: Canon Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the official Ethiopian Orthodox 46 Old Testament plus 35 New Testament structure the tested source of truth for membership, grouping, navigation, and coverage status.

**Architecture:** Define the canon in one backend module as 81 counted entries with separately navigable works, seed normalized library tables, and serve catalog results independently from installed scripture text. Keep the existing `biblical_texts` table unchanged in this phase and derive coverage by translation code.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic, Pytest, SQLite/PostgreSQL

---

## File Map

- Create `backend/app/library/canon.py`: immutable official canon definition, aliases, and validation.
- Create `backend/app/library/models.py`: work, alias, canon-entry, entry-work, edition, and coverage models.
- Create `backend/alembic/versions/0007_ethiopian_library_foundation.py`: normalized library schema.
- Create `backend/app/library/seed.py`: idempotent Ethiopian canon seed service.
- Modify `backend/app/application.py`: register the new library models and seed the test database.
- Modify `backend/app/library/router.py`: query authoritative catalog and expose edition coverage.
- Create `backend/tests/library/test_ethiopian_canon.py`: official count, grouping, aliases, and invariants.
- Create `backend/tests/library/test_library_catalog.py`: catalog API behavior independent from installed text.

### Task 1: Encode and Validate the Official Canon

**Files:**
- Create: `backend/app/library/canon.py`
- Create: `backend/tests/library/test_ethiopian_canon.py`

- [ ] **Step 1: Write the failing canon invariants**

```python
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


def test_ethiopian_names_resolve_without_conflating_meqabyan_and_maccabees():
    assert alias_target('Meqabyan 1') == '1-meqabyan'
    assert alias_target('1 Maccabees') == '1-maccabees'
    assert alias_target('Meqabyan 1') != alias_target('1 Maccabees')
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `uv run pytest backend/tests/library/test_ethiopian_canon.py -q`

Expected: collection fails with `ModuleNotFoundError: app.library.canon`.

- [ ] **Step 3: Create the canon types and complete entry data**

Create `backend/app/library/canon.py` with frozen `Work` and `CanonEntry` dataclasses. Populate `ETHIOPIAN_CANON` from the official EOTC 46-plus-35 list. Use the following counted entries and work mappings exactly:

```python
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


def _entries(testament: str, section_rows: tuple[tuple[str, str, str, tuple[str, ...]], ...]):
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
```

Define `WORKS` by flattening the work IDs into `Work` objects with current database names, and define explicit aliases for every current spelling used in `frontend/src/data/bibleCanons.js` and `server/data/ingest_ertale_canon.py`. Implement case-insensitive `alias_target()` and deterministic `navigation_works()`.

- [ ] **Step 4: Run the canon tests and verify GREEN**

Run: `uv run pytest backend/tests/library/test_ethiopian_canon.py -q`

Expected: `3 passed`.

- [ ] **Step 5: Commit the canon definition**

```bash
git add backend/app/library/canon.py backend/tests/library/test_ethiopian_canon.py
git commit -m "feat: define official Ethiopian canon"
```

### Task 2: Add Normalized Library Tables

**Files:**
- Create: `backend/app/library/models.py`
- Create: `backend/alembic/versions/0007_ethiopian_library_foundation.py`
- Modify: `backend/app/application.py`
- Test: `backend/tests/library/test_library_catalog.py`

- [ ] **Step 1: Write a failing schema test**

```python
from sqlalchemy import inspect
from app.application import create_application


def test_library_foundation_tables_are_registered(test_settings):
    app = create_application(test_settings)
    names = set(inspect(app.state.database_engine).get_table_names())
    assert {'library_works', 'library_work_aliases', 'canon_entries', 'canon_entry_works', 'text_editions', 'edition_coverage'} <= names
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/test_library_catalog.py -q`

Expected: FAIL because the six tables are absent.

- [ ] **Step 3: Define focused SQLAlchemy models**

Create models using `app.database.Base`. Use string work IDs, unique `(canon_code, testament, canonical_order)` entries, unique aliases, unique edition codes, and unique `(edition_code, work_id)` coverage rows. `TextEdition` must contain `name`, `reading_language`, `source_language`, `script`, `translator`, `publisher`, `published_year`, `license_spdx`, `attribution`, `provenance_url`, `source_tradition`, `relationship`, `versification`, `verification_status`, and `source_checksum`. `EditionCoverage` must contain `status`, `chapter_count`, `verse_count`, and `note`.

Use these constrained status values in application validation: edition `queued|staged|verified|withdrawn`, relationship `exact_ethiopian|related_recension|general_reading`, and coverage `verified_english|verified_original|related_recension|translation_needed`.

- [ ] **Step 4: Add migration `0007_ethiopian_library_foundation`**

Create the same six tables and indexes in Alembic. Set `down_revision = '0006_platform_integrity'`. Downgrade drops child tables before parent tables.

- [ ] **Step 5: Register the models**

Add `from app.library import models as library_models  # noqa: F401` beside the other model registrations in `backend/app/application.py` and `backend/alembic/env.py`.

- [ ] **Step 6: Verify GREEN and migration reversibility**

Run:

```bash
uv run pytest backend/tests/library/test_library_catalog.py -q
DATABASE_URL=sqlite:////tmp/unbound-canon-plan.db uv run alembic -c backend/alembic.ini upgrade head
DATABASE_URL=sqlite:////tmp/unbound-canon-plan.db uv run alembic -c backend/alembic.ini downgrade 0006_platform_integrity
```

Expected: tests pass; upgrade and downgrade complete without errors.

- [ ] **Step 7: Commit the schema**

```bash
git add backend/app/library/models.py backend/app/application.py backend/alembic/env.py backend/alembic/versions/0007_ethiopian_library_foundation.py backend/tests/library/test_library_catalog.py
git commit -m "feat: add scripture library metadata schema"
```

### Task 3: Seed the Canon Idempotently

**Files:**
- Create: `backend/app/library/seed.py`
- Modify: `backend/app/application.py`
- Modify: `backend/tests/library/test_library_catalog.py`

- [ ] **Step 1: Add failing idempotency and count tests**

```python
from sqlalchemy.orm import Session
from app.library.models import CanonEntryModel, LibraryWork
from app.library.seed import seed_ethiopian_canon


def test_seed_is_idempotent_and_preserves_official_count(test_settings):
    app = create_application(test_settings)
    with Session(app.state.database_engine) as session:
        seed_ethiopian_canon(session)
        seed_ethiopian_canon(session)
        assert session.query(CanonEntryModel).filter_by(canon_code='ETHIO81').count() == 81
        assert session.query(LibraryWork).filter_by(id='genesis').one().name == 'Genesis'
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/test_library_catalog.py -q -k seed`

Expected: import fails because `seed.py` is absent.

- [ ] **Step 3: Implement `seed_ethiopian_canon(session)` and its explicit CLI**

Upsert works and aliases first, then 81 entries, then entry-work join rows. Delete only stale `ETHIO81` join rows and entries; never delete published texts. Commit once at the end and rollback on exceptions.

Add an `argparse` entry point accepting required `--database-url`, build an engine and session from that URL, run the seed, and print the counted OT, NT, entry, and navigation-work totals. Exit nonzero unless the result is exactly 46, 35, and 81.

- [ ] **Step 4: Seed test environments at startup**

After `Base.metadata.create_all(engine)` in `create_application`, open a session from the configured factory and call the seed function only when `settings.environment == 'test'`. Production uses the explicit seed command introduced in Phase 2.

- [ ] **Step 5: Verify GREEN**

Run: `uv run pytest backend/tests/library/test_library_catalog.py -q`

Expected: all catalog schema and seed tests pass.

- [ ] **Step 6: Commit the seed**

```bash
git add backend/app/library/seed.py backend/app/application.py backend/tests/library/test_library_catalog.py
git commit -m "feat: seed Ethiopian canon catalog"
```

### Task 4: Serve Canon Membership Independently from Text Coverage

**Files:**
- Modify: `backend/app/library/router.py`
- Modify: `backend/tests/library/test_library_routes.py`

- [ ] **Step 1: Replace the legacy membership expectation with a failing authoritative-catalog test**

```python
def test_ethiopian_catalog_includes_genesis_without_installed_genesis_text(test_settings):
    app = create_application(test_settings)
    with TestClient(app) as client:
        payload = client.get('/api/v1/books?canon=ETHIO81').json()
        genesis = next(book for book in payload['books'] if book['id'] == 'genesis')
        assert payload['canon_count'] == 81
        assert genesis['name'] == 'Genesis'
        assert genesis['canon_included'] is True
        assert genesis['coverage'] == []
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/test_library_routes.py -q -k ethiopian_catalog`

Expected: FAIL because `/api/v1/books` still derives books from `biblical_texts`.

- [ ] **Step 3: Replace set-based canon inference**

Query `canon_entries`, `canon_entry_works`, `library_works`, and `edition_coverage`. Return navigation works with `id`, `name`, `testament`, `collection`, `entry_name`, `entry_order`, `canon_included`, and a `coverage` list. Return `canon_count: 81` separately from `navigation_count`.

Keep PROT66 and CATH73 behavior working by moving their existing membership sets behind the same response shape until they receive normalized seed data.

- [ ] **Step 4: Add a focused work-detail endpoint**

Add `GET /api/v1/library/works/{work_id}` returning aliases, canon entry, and edition coverage. Return 404 for unknown work IDs.

- [ ] **Step 5: Run route and application suites**

Run: `uv run pytest backend/tests/library backend/tests/test_application.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the authoritative catalog API**

```bash
git add backend/app/library/router.py backend/tests/library/test_library_routes.py
git commit -m "fix: separate canon membership from text coverage"
```

### Task 5: Phase 1 Quality Gate

**Files:** Verify only.

- [ ] **Step 1: Run all backend tests**

Run: `uv run pytest backend/tests -q`

Expected: zero failures.

- [ ] **Step 2: Verify migration head and canon invariants in a clean SQLite database**

Run:

```bash
DATABASE_URL=sqlite:////tmp/unbound-canon-final.db uv run alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend uv run python -m app.library.seed --database-url sqlite:////tmp/unbound-canon-final.db
```

Expected: the seed reports 81 counted entries, 46 OT, 35 NT, and no validation errors.

- [ ] **Step 3: Commit any verification-only corrections**

If corrections were required, stage only Phase 1 files and commit with `fix: validate Ethiopian canon foundation`. If no files changed, do not create an empty commit.

## Phase 1 Exit Criteria

- Canon membership no longer depends on which texts happen to be installed.
- The official count is 46 OT plus 35 NT.
- Composite entries count once while their constituent works remain navigable.
- Genesis appears in ETHIO81 with an empty coverage list when no edition is installed.
- No scripture text or reader UI behavior has been changed yet.
