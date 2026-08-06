# Ethiopian Orthodox Composite English Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Import the supplied 83-text English composite safely, expose 82 texts as Ethiopian-canon coverage plus supplemental Prayer of Manasseh, and show truthful per-book provenance throughout the reader and comparison experiences.

**Architecture:** Add a dedicated checksummed composite-ZIP adapter and per-work source metadata to the verified scripture pipeline. Publish under EOTC-COMPOSITE-EN, retain ETHIO81 as the canon selector, and leave GEEZ1980-RESEARCH untouched. Additive API metadata drives a shared disclosure model in both reading experiences.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, Typer, SQLite/PostgreSQL, React 19, Vitest, Testing Library, Playwright, axe-core.

---

## File map

New files:

- backend/alembic/versions/0009_composite_edition_sources.py
- backend/app/library/ingest/adapters/composite_english_bundle.py
- backend/tests/library/ingest/test_composite_english_bundle_adapter.py
- backend/data/scripture/eotc-composite-en/Ethiopian Orthodox Bible (Non-KJV Edition).zip
- backend/data/scripture/eotc-composite-en/build_manifest.py
- backend/data/scripture/eotc-composite-en/manifest.json
- backend/data/scripture/eotc-composite-en/README.md
- frontend/src/reader/TextSourceDisclosure.jsx
- frontend/src/reader/TextSourceDisclosure.test.jsx
- frontend/e2e/ethiopian-composite-english.spec.js

Modified files:

- backend/app/library/canon.py
- backend/app/library/models.py
- backend/app/library/ingest/manifest.py
- backend/app/library/ingest/cli.py
- backend/app/library/ingest/publish.py
- backend/app/library/router.py
- backend/tests/library/ingest/test_manifest.py
- backend/tests/library/ingest/test_cli.py
- backend/tests/library/ingest/test_publish.py
- backend/tests/library/ingest/test_schema.py
- backend/tests/library/test_ethiopian_canon.py
- backend/tests/library/test_library_catalog.py
- backend/tests/library/test_library_routes.py
- docs/scripture-sources.md
- frontend/src/reader/scriptureApi.js
- frontend/src/reader/scriptureApi.test.js
- frontend/src/reader/BookPicker.jsx
- frontend/src/reader/BookPicker.test.jsx
- frontend/src/reader/ScriptureReaderPage.jsx
- frontend/src/reader/ScriptureReaderPage.test.jsx
- frontend/src/reader/ReaderStatus.jsx
- frontend/src/reader/ReaderStatus.test.jsx
- frontend/src/reader/ScripturePane.jsx
- frontend/src/reader/ScripturePane.test.jsx
- frontend/src/reader/readerTokens.css
- frontend/src/components/TextualComparisonWorkspace.jsx
- frontend/src/components/TextualComparisonWorkspace.test.jsx
- frontend/src/components/textualComparison/comparisonModel.js
- frontend/src/components/textualComparison/comparisonModel.test.js
- frontend/src/components/textualComparison/TranslationComparisonCard.jsx
- frontend/src/components/TextualComparisonWorkspace.css

## Reviewed mapping

Task 4 uses this exact populated-record map:

    BOOK_MAP = {
        'GEN': 'genesis', 'EXO': 'exodus', 'LEV': 'leviticus', 'NUM': 'numbers',
        'DEU': 'deuteronomy', 'JOS': 'joshua', 'JDG': 'judges', 'RUT': 'ruth',
        '1SA': '1-samuel', '2SA': '2-samuel', '1KI': '1-kings', '2KI': '2-kings',
        '1CH': '1-chronicles', '2CH': '2-chronicles', 'JUB': 'jubilees',
        'ENO': '1-enoch', 'EZR': 'ezra', 'NEH': 'nehemiah', '2ES': 'second-ezra',
        '1ES': 'ezra-sutuel', 'TOB': 'tobit', 'JDT': 'judith', 'EST': 'esther',
        '1MQ': '1-meqabyan', '2MQ': '2-meqabyan', '3MQ': '3-meqabyan',
        'JOB': 'job', 'PSA': 'psalms', 'PRO': 'proverbs', 'ECC': 'ecclesiastes',
        'SNG': 'song-of-solomon', 'WIS': 'wisdom-of-solomon', 'SIR': 'sirach',
        'ISA': 'isaiah', 'JER': 'jeremiah', 'LAM': 'lamentations', 'BAR': 'baruch',
        'LJE': 'letter-of-jeremiah', 'EZK': 'ezekiel', 'DAN': 'daniel',
        'AZA': 'prayer-of-azariah', 'SUS': 'susanna', 'BEL': 'bel-and-the-dragon',
        'HOS': 'hosea', 'JOL': 'joel', 'AMO': 'amos', 'OBA': 'obadiah',
        'JON': 'jonah', 'MIC': 'micah', 'NAM': 'nahum', 'HAB': 'habakkuk',
        'ZEP': 'zephaniah', 'HAG': 'haggai', 'ZEC': 'zechariah', 'MAL': 'malachi',
        'MAN': 'prayer-of-manasseh', 'MAT': 'matthew', 'MRK': 'mark', 'LUK': 'luke',
        'JHN': 'john', 'ACT': 'acts', 'ROM': 'romans', '1CO': '1-corinthians',
        '2CO': '2-corinthians', 'GAL': 'galatians', 'EPH': 'ephesians',
        'PHP': 'philippians', 'COL': 'colossians', '1TH': '1-thessalonians',
        '2TH': '2-thessalonians', '1TI': '1-timothy', '2TI': '2-timothy',
        'TIT': 'titus', 'PHM': 'philemon', 'HEB': 'hebrews', 'JAS': 'james',
        '1PE': '1-peter', '2PE': '2-peter', '1JN': '1-john', '2JN': '2-john',
        '3JN': '3-john', 'JUD': 'jude', 'REV': 'revelation',
    }

Only MAN has canon_scope supplemental. These 13 established Ethiopian works have no archive text:

    UNAVAILABLE_CANON_WORKS = (
        'esther-greek-additions', 'psalm-151', 'tegsats',
        'paralipomena-jeremiah', 'josippon', 'sirate-tsion', 'tizaz',
        'gitsew', 'abtilis', 'metsihafe-kidan-1', 'metsihafe-kidan-2',
        'qalementos', 'didesqelya',
    )

---

### Task 1: Add supplemental work and per-work source storage

**Files:** backend/app/library/canon.py, backend/app/library/models.py, backend/alembic/versions/0009_composite_edition_sources.py, backend/tests/library/test_ethiopian_canon.py, backend/tests/library/ingest/test_schema.py

- [ ] **Step 1: Write failing tests**

    def test_prayer_of_manasseh_is_supplemental_only():
        from app.library.canon import SUPPLEMENTAL_LIBRARY_WORKS, WORKS
        assert 'prayer-of-manasseh' in {w.id for w in SUPPLEMENTAL_LIBRARY_WORKS}
        assert 'prayer-of-manasseh' not in {w.id for w in WORKS}

    def test_edition_work_source_contract():
        from app.library.models import EditionWorkSource
        assert {'edition_code', 'work_id', 'source_key'} <= {
            c.name for c in EditionWorkSource.__table__.columns
        }

- [ ] **Step 2: Verify failure**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/test_ethiopian_canon.py backend/tests/library/ingest/test_schema.py -q

- [ ] **Step 3: Register supplemental Prayer of Manasseh**

Add this only to SUPPLEMENTAL_LIBRARY_WORKS:

    Work(
        'prayer-of-manasseh', 'Prayer of Manasseh', 'OT', 'Prayer',
        ('Prayer of Manasses',),
    )

- [ ] **Step 4: Add EditionWorkSource**

It has a unique edition_code/work_id pair; foreign keys to text_editions and library_works; source_key, source_label, translator, source_language, source_tradition, published_year, license_spdx, attribution, provenance_url, fallback, modified, modification_note, verification_status, and canon_scope. Constrain verification_status to provisional or verified and canon_scope to ethio81 or supplemental. Extend TextEdition verification_status to include provisional.

    class EditionWorkSource(Base):
        __tablename__ = 'edition_work_sources'
        __table_args__ = (
            UniqueConstraint(
                'edition_code', 'work_id',
                name='uq_edition_work_sources_edition_work',
            ),
            CheckConstraint(
                "verification_status IN ('provisional', 'verified')",
                name='ck_edition_work_sources_verification_status',
            ),
            CheckConstraint(
                "canon_scope IN ('ethio81', 'supplemental')",
                name='ck_edition_work_sources_canon_scope',
            ),
            Index('ix_edition_work_sources_work_id', 'work_id'),
        )

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        edition_code: Mapped[str] = mapped_column(
            ForeignKey('text_editions.edition_code', ondelete='CASCADE')
        )
        work_id: Mapped[str] = mapped_column(
            ForeignKey('library_works.id', ondelete='CASCADE')
        )
        source_key: Mapped[str] = mapped_column(String(100))
        source_label: Mapped[str] = mapped_column(String(200))
        translator: Mapped[str | None] = mapped_column(String(200), nullable=True)
        source_language: Mapped[str] = mapped_column(String(100))
        source_tradition: Mapped[str] = mapped_column(String(200))
        published_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
        license_spdx: Mapped[str] = mapped_column(String(100))
        attribution: Mapped[str] = mapped_column(Text)
        provenance_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
        fallback: Mapped[bool] = mapped_column(default=False)
        modified: Mapped[bool] = mapped_column(default=False)
        modification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
        verification_status: Mapped[str] = mapped_column(String(16))
        canon_scope: Mapped[str] = mapped_column(String(16))

- [ ] **Step 5: Create migration 0009**

Use Alembic batch mode to replace the text edition status check. Create the source table and indexes. Insert prayer-of-manasseh only when absent. Downgrade drops the table, restores the prior check, and removes only the unreferenced supplemental work.

- [ ] **Step 6: Run and commit**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/test_ethiopian_canon.py backend/tests/library/ingest/test_schema.py -q
    git add backend/app/library/canon.py backend/app/library/models.py backend/alembic/versions/0009_composite_edition_sources.py backend/tests/library/test_ethiopian_canon.py backend/tests/library/ingest/test_schema.py
    git commit -m "feat: add per-work scripture source metadata"

---

### Task 2: Define the provisional mixed-source manifest

**Files:** backend/app/library/ingest/manifest.py, backend/tests/library/ingest/test_manifest.py

- [ ] **Step 1: Write failing validation tests**

    def test_verified_work_source_requires_url():
        payload = work_source_payload()
        payload.update(verification_status='verified', provenance_url=None)
        with pytest.raises(ValidationError, match='requires provenance_url'):
            WorkSourceManifest.model_validate(payload)

    def test_work_sources_equal_book_targets(composite_payload):
        composite_payload['adapter_options']['work_sources'] = {}
        with pytest.raises(ValidationError, match='exactly match'):
            SourceManifest.model_validate(composite_payload)

- [ ] **Step 2: Verify failure**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/ingest/test_manifest.py -q

- [ ] **Step 3: Add strict types**

Add LicenseRef-Mixed, adapter composite_english_bundle, source_verification defaulting to verified, WorkSourceManifest, and CompositeEnglishBundleAdapterOptions. Work sources contain every persisted source field from Task 1. Verified records require a provenance URL. Modified records require a modification note. book_map targets are unique; work_sources exactly equal those targets; supplemental works are mapped; and source scope agrees with the supplemental list.

    class WorkSourceManifest(BaseModel):
        model_config = ConfigDict(extra='forbid', strict=True)

        source_key: SourceBookCode
        source_label: EditionName
        translator: Contributor | None
        source_language: LanguageOrScript
        source_tradition: SourceTradition
        published_year: PublishedYear | None
        license_spdx: _LICENSES
        attribution: Attribution
        provenance_url: HttpUrl | None
        fallback: StrictBool = False
        modified: StrictBool = False
        modification_note: Attribution | None = None
        verification_status: Literal['provisional', 'verified']
        canon_scope: Literal['ethio81', 'supplemental']

    class CompositeEnglishBundleAdapterOptions(BaseModel):
        model_config = ConfigDict(extra='forbid', strict=True)

        book_map: dict[SourceBookCode, WorkId]
        work_sources: dict[WorkId, WorkSourceManifest]
        supplemental_works: list[WorkId] = Field(default_factory=list)

        @model_validator(mode='after')
        def mapping_is_complete(self):
            if len(set(self.book_map.values())) != len(self.book_map):
                raise ValueError('book_map targets must be unique.')
            if set(self.work_sources) != set(self.book_map.values()):
                raise ValueError('work_sources must exactly match book_map targets.')
            if not set(self.supplemental_works) <= set(self.book_map.values()):
                raise ValueError('supplemental_works must be mapped.')
            return self

- [ ] **Step 4: Run and commit**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/ingest/test_manifest.py -q
    git add backend/app/library/ingest/manifest.py backend/tests/library/ingest/test_manifest.py
    git commit -m "feat: define composite scripture manifest"

---

### Task 3: Implement the bounded ZIP adapter

**Files:** backend/app/library/ingest/adapters/composite_english_bundle.py, backend/app/library/ingest/adapters/__init__.py, backend/tests/library/ingest/test_composite_english_bundle_adapter.py

- [ ] **Step 1: Write a failing valid-bundle test**

    def test_parses_flat_chapter_bundle(tmp_path, composite_manifest):
        archive_path = tmp_path / 'composite.zip'
        with ZipFile(archive_path, 'w') as archive:
            archive.writestr('data/index.json', json.dumps({'books': [{
                'id': 'GEN', 'name': 'Genesis', 'file': 'data/gen.json',
                'src': 'wmb', 'chapters': 1,
            }]}))
            archive.writestr('data/gen.json', json.dumps([{
                'c': 1,
                'v': [{'n': 1, 't': 'In the beginning, God created.'}],
            }]))
        rows = parse_composite_english_bundle(
            composite_manifest(archive_path, {'GEN': 'genesis'}), tmp_path
        )
        assert [(r.work_id, r.chapter, r.verse) for r in rows] == [
            ('genesis', 1, 1)
        ]

Also test traversal, backslashes, absolute members, encryption, symlinks, member and size limits, duplicate IDs, duplicate targets, unexpected populated books, unexpected placeholders, missing files, source mismatch, invalid chapter/verse, duplicates, and empty text.

- [ ] **Step 2: Verify failure**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/ingest/test_composite_english_bundle_adapter.py -q

- [ ] **Step 3: Implement safe parsing**

Reuse the strict member safety pattern from weahadu_bundle.py with limits of 1,024 members and 128 MiB uncompressed. Verify SHA-256. Never extract or execute. Require populated index IDs to equal book_map keys. Validate the index source family against work source_key. Read chapter JSON in memory, require positive unique positions and normalized nonempty text, and call:

    normalize_verse(
        source_book, chapter, verse, text,
        f'{source.path}!/{member}#{chapter}:{verse}',
    )

Reject any normalized work that differs from the explicit target. Return map order, then chapter and verse order.

- [ ] **Step 4: Run and commit**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/ingest/test_composite_english_bundle_adapter.py -q
    git add backend/app/library/ingest/adapters/composite_english_bundle.py backend/app/library/ingest/adapters/__init__.py backend/tests/library/ingest/test_composite_english_bundle_adapter.py
    git commit -m "feat: parse composite English scripture bundle"

---

### Task 3A: Declare exact upstream verse-number omissions

**Files:** backend/app/library/ingest/manifest.py, backend/app/library/ingest/adapters/composite_english_bundle.py, backend/tests/library/ingest/test_manifest.py, backend/tests/library/ingest/test_composite_english_bundle_adapter.py

- [ ] **Step 1: Write failing manifest and adapter tests**

    def test_known_missing_verses_must_target_mapped_works(composite_payload):
        composite_payload['adapter_options']['known_missing_verses'] = {
            'not-mapped': {'1': [9]},
        }
        with pytest.raises(ValidationError, match='mapped work'):
            SourceManifest.model_validate(composite_payload)

    def test_adapter_accepts_only_exact_declared_gaps(tmp_path):
        path = tmp_path / 'bundle.zip'
        book = [{'c': 1, 'v': [
            {'n': 1, 't': 'One'}, {'n': 2, 't': 'Two'},
            {'n': 4, 't': 'Four'},
        ]}]
        archive = _write_bundle(path, books={'data/gen.json': book})
        manifest = _manifest(
            path.name, archive,
            expected_works={'genesis': {
                'chapters': 1, 'verse_counts': {'1': 3},
            }},
        )
        manifest.adapter_options.known_missing_verses = {
            'genesis': {'1': [3]},
        }
        rows = parse_composite_english_bundle(manifest, tmp_path)
        assert [row.verse for row in rows] == [1, 2, 4]

    @pytest.mark.parametrize('declared', ({}, {'genesis': {'1': [2]}}))
    def test_adapter_rejects_undeclared_or_present_missing_verse(
        tmp_path, declared,
    ):
        path = tmp_path / 'bundle.zip'
        book = [{'c': 1, 'v': [
            {'n': 1, 't': 'One'}, {'n': 2, 't': 'Two'},
            {'n': 4, 't': 'Four'},
        ]}]
        archive = _write_bundle(path, books={'data/gen.json': book})
        manifest = _manifest(path.name, archive)
        manifest.adapter_options.known_missing_verses = declared
        with pytest.raises(ValueError, match='missing verse'):
            parse_composite_english_bundle(manifest, tmp_path)

- [ ] **Step 2: Run tests and verify red**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/ingest/test_manifest.py backend/tests/library/ingest/test_composite_english_bundle_adapter.py -q

- [ ] **Step 3: Add a strict omission declaration**

Add a positive strict verse-number type and this field to `CompositeEnglishBundleAdapterOptions`:

    known_missing_verses: dict[
        WorkId, dict[ChapterKey, list[MissingVerseNumber]]
    ] = Field(default_factory=dict)

Normalize work IDs and require every key to be a mapped target. Require each list to be nonempty, sorted, and unique. The adapter receives the declaration for each work and chapter. It accepts a non-contiguous chapter only when `actual_numbers | declared_missing` is exactly `1..max(actual_numbers | declared_missing)` and `actual_numbers` is disjoint from `declared_missing`. Empty chapters, duplicate verse positions, undeclared gaps, out-of-range chapters, and declared-but-present verses remain errors. The omission declaration affects validation only and never creates placeholder text.

- [ ] **Step 4: Run and commit**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/ingest/test_manifest.py backend/tests/library/ingest/test_composite_english_bundle_adapter.py -q
    git add backend/app/library/ingest/manifest.py backend/app/library/ingest/adapters/composite_english_bundle.py backend/tests/library/ingest/test_manifest.py backend/tests/library/ingest/test_composite_english_bundle_adapter.py
    git commit -m "feat: declare source verse omissions"

---

### Task 4: Freeze and correct the source artifacts

**Files:** all backend/data/scripture/eotc-composite-en files and real-archive adapter test

- [ ] **Step 1: Freeze and verify three build inputs**

    shasum -a 256 backend/data/scripture/eotc-composite-en/{Ethiopian\ Orthodox\ Bible\ \(Non-KJV\ Edition\).zip,eng-webbe_vpl.zip,project-gutenberg-77935.txt}

Expected SHA-256 values:

    0f4bdff8e24ee7e67afbd939d68a8dc40c0f1cf27026066dbb9f92ce34b183a2  supplied ZIP
    dc16460ed5e890e7b169cd3caeaa7e4adb4f7a6b5031bff85e4503389cd03b11  eBible VPL
    10d325355a810badf67bbbd1fe6bda77dc6e294eae78c2f6c69290188af45b14  Project Gutenberg plain text

- [ ] **Step 2: Write a failing corrected-bundle acceptance test**

The test runs `build_bundle.py` in a temporary output directory and validates both deterministic output and the strict adapter. Assert:

    assert raw_report['raw_record_count'] == 44_114
    assert raw_report['exact_duplicate_excess'] == 5_252
    assert raw_report['conflicting_duplicate_excess'] == 17
    assert raw_report['raw_unique_positions'] == 38_845
    assert report['known_missing_verses'] == {
        '2-corinthians': {'13': [14]},
        '2-meqabyan': {'16': [9], '21': [9]},
        'acts': {'19': [41], '20': [17]},
        'luke': {'18': [35]},
        'mark': {'4': [10], '8': [19], '9': [31], '11': [19]},
        'matthew': {'26': [30, 45]},
    }
    assert len(rows) == report['corrected_verse_count']
    assert len({(r.work_id, r.chapter, r.verse) for r in rows}) == len(rows)
    assert len({r.work_id for r in rows}) == 83

Also assert all 108 Enoch chapters are nonempty, Enoch 80:1 exists, the six WEB works match the official VPL chapter/verse positions, a second build is byte-identical, and no build input is modified.

- [ ] **Step 3: Build a deterministic corrected bundle**

Create `build_bundle.py`. It verifies all three input checksums before reading. It copies unchanged archive book data except the six `web_apocrypha` works and `ENO`:

    WEB_BOOKS = {'1ES', '2ES', 'TOB', 'JDT', 'WIS', 'SIR'}
    KNOWN_MISSING_VERSES = {
        '2-corinthians': {'13': [14]},
        '2-meqabyan': {'16': [9], '21': [9]},
        'acts': {'19': [41], '20': [17]},
        'luke': {'18': [35]},
        'mark': {'4': [10], '8': [19], '9': [31], '11': [19]},
        'matthew': {'26': [30, 45]},
    }

For WEB works, parse `eng-webbe_vpl.txt` lines with a full-line expression equivalent to `^(BOOK) ([1-9][0-9]*):([1-9][0-9]*) (TEXT)$`; reject duplicates, gaps, empty text, unexpected books, and chapter-count mismatches. For Enoch, parse only the `The Book of Enoch` section of Project Gutenberg's official plain-text artifact, recognize Roman-numeral chapter headings I through CVIII and numbered verse/subverse markers such as `6.`, `6 a.`, and `5 b.`. Join fragments carrying the same integer verse number in document order, discard Project Gutenberg boilerplate, presentation-only page numbers, and footnote blocks, preserve textual brackets and critical symbols, and reject missing/empty chapters, duplicate output positions, or a non-contiguous 1..N verse set. Do not use the damaged archive Enoch text in output. For Murdock, omit only the ten exactly reviewed blank alignment records, declare those positions, and replace U+000F line separators with spaces; reject every other empty/control-bearing source text.

Write `corrected-bundle.zip` with sorted member names, UTF-8 canonical JSON, and fixed ZIP timestamps/permissions so repeated builds are byte-identical. Write `data-quality-report.json` containing every input/output checksum, raw findings, exact corrected count, replacement counts, the two declared omissions, and generator version. Never overwrite an input artifact.

- [ ] **Step 4: Build the manifest generator**

Use the complete BOOK_MAP above and:

    SOURCE_KEYS = {
        'wmb': 'world-messianic-bible',
        'peshitta': 'murdock-peshitta-1852',
        'web_apocrypha': 'world-english-bible-apocrypha',
        'kjv_apocrypha': 'kjv-1611-fallback',
        'meqabyan': 'wikisource-meqabyan-geez',
        'extra': 'rh-charles-ethiopic',
    }

All source records remain provisional. Mark archive-derived WMB and Murdock records modified because revision proof is absent and the archive documents name standardization. The six WEB records use the official eBible public-domain source URL and are unmodified apart from structural conversion. Mark KJV fallback true. Attribute each Meqabyan work to Wikisource contributors under CC-BY-SA-4.0 using permanent revision URLs ending in oldids 16044809, 16044810, and 16044811; disclose that 2 Meqabyan 16:9 and 21:9 are absent upstream. Enoch uses Project Gutenberg ebook 77935 and is modified with a note that subverse/layout fragments were deterministically joined; Jubilees remains archive-derived with exact upstream revision unavailable.

The output uses edition EOTC-COMPOSITE-EN, English reading language, Mixed source language, Latin script, LicenseRef-Mixed, provisional source verification, general_reading relationship, composite adapter, prayer-of-manasseh as the sole supplemental work, and `known_missing_verses` exactly equal to the two 2 Meqabyan positions plus ten reviewed blank Murdock alignment positions. Its sole ingest `source_files` entry is `corrected-bundle.zip` with the checksum generated in the committed quality report.

- [ ] **Step 5: Generate and validate**

    /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python backend/data/scripture/eotc-composite-en/build_bundle.py
    /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python backend/data/scripture/eotc-composite-en/build_manifest.py
    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -c "from pathlib import Path; from app.library.ingest.manifest import SourceManifest; p=Path('backend/data/scripture/eotc-composite-en/manifest.json'); m=SourceManifest.model_validate_json(p.read_text()); print(m.edition_code, len(m.expected_works), sum(v.chapters for v in m.expected_works.values()))"

Expected: EOTC-COMPOSITE-EN, 83 works, 1,520 chapters, 38,938 publishable rows. The adapter row count must equal `corrected_verse_count` in `data-quality-report.json`, with no duplicate position and no omission other than the two declared 2 Meqabyan labels and ten blank Murdock alignment labels.

- [ ] **Step 6: Add real-data assertions**

    assert len(rows) == quality_report['corrected_verse_count']
    assert len({row.work_id for row in rows}) == 83
    assert manifest.adapter_options.supplemental_works == [
        'prayer-of-manasseh'
    ]
    assert sum(
        source.canon_scope == 'ethio81'
        for source in manifest.adapter_options.work_sources.values()
    ) == 82

- [ ] **Step 7: Document and commit**

README records all four checksums (three inputs plus corrected output), distinguishes 44,114 raw records from 38,938 publishable rows, records 82+1 scope, 13 unavailable works, distinct Enoch and Jubilees provenance records under the broad R. H. Charles source-family key, six KJV fallbacks, CC BY-SA duties and permanent revisions, the two upstream Meqabyan omissions, ten blank Murdock alignment labels, U+000F normalization, all modifications, provisional status, and exact operator commands. It must state that this is not an official or complete uniform Ethiopian Orthodox translation.

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/ingest/test_composite_english_bundle_adapter.py -q
    git add backend/data/scripture/eotc-composite-en backend/tests/library/ingest/test_composite_english_bundle_adapter.py
    git commit -m "data: register Ethiopian composite English source"

---

### Task 5: Publish work sources atomically

**Files:** backend/app/library/ingest/cli.py, backend/app/library/ingest/publish.py, backend/tests/library/ingest/test_cli.py, backend/tests/library/ingest/test_publish.py

- [ ] **Step 1: Write failing tests**

    def test_composite_adapter_is_installed():
        assert set(cli.ADAPTERS) == {
            'weahadu_bundle', 'composite_english_bundle'
        }

    def test_publish_promotes_provisional_source(ingest_session):
        run = make_composite_ingest_run(ingest_session)
        result = publish_run(ingest_session, run.id)
        source = ingest_session.scalar(select(EditionWorkSource).where(
            EditionWorkSource.edition_code == result.edition_code,
            EditionWorkSource.work_id == 'genesis',
        ))
        assert source.verification_status == 'provisional'

Add replacement, rollback, injected failure, and GEEZ1980-RESEARCH isolation tests.

- [ ] **Step 2: Verify failure**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/ingest/test_cli.py backend/tests/library/ingest/test_publish.py -q

- [ ] **Step 3: Register adapter and publish source snapshot**

Add composite parser to ADAPTERS. Implement _replace_work_sources: delete only candidate edition rows, insert every source from the run manifest, and set edition status from source_verification. Call before verse replacement in the same transaction. Rollback rebuilds sources from the restored run manifest. Idempotency compares source snapshots.

    def _replace_work_sources(session, edition, manifest):
        session.execute(delete(EditionWorkSource).where(
            EditionWorkSource.edition_code == edition.edition_code
        ))
        options = manifest.adapter_options
        for work_id, source in sorted(options.work_sources.items()):
            session.add(EditionWorkSource(
                edition_code=edition.edition_code,
                work_id=work_id,
                **source.model_dump(mode='python'),
            ))
        edition.verification_status = manifest.source_verification

- [ ] **Step 4: Run and commit**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/ingest/test_cli.py backend/tests/library/ingest/test_publish.py -q
    git add backend/app/library/ingest/cli.py backend/app/library/ingest/publish.py backend/tests/library/ingest/test_cli.py backend/tests/library/ingest/test_publish.py
    git commit -m "feat: publish composite work sources atomically"

---

### Task 6: Expose source metadata and recommendations

**Files:** backend/app/library/router.py, backend/tests/library/test_library_catalog.py, backend/tests/library/test_library_routes.py

- [ ] **Step 1: Write failing route tests**

    def test_ethio_catalog_recommends_composite(client):
        books = {
            b['id']: b
            for b in client.get('/api/v1/books?canon=ETHIO81').json()['books']
        }
        assert books['genesis']['recommended_edition'] == 'EOTC-COMPOSITE-EN'
        assert books['tegsats']['recommended_edition'] is None
        assert books['tegsats']['unavailable_reason'] == (
            'English text not yet available'
        )
        assert 'prayer-of-manasseh' not in books

    def test_reader_row_has_source(client):
        row = client.get(
            '/api/biblical-texts/chapter-content?book=Genesis&chapter=1'
        ).json()['content'][0]
        assert row['work_source']['source_key'] == 'world-messianic-bible'

- [ ] **Step 2: Verify failure**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/test_library_catalog.py backend/tests/library/test_library_routes.py -q

- [ ] **Step 3: Add payload and recommendation logic**

Resolve each reader row to a work with alias_target, preload by edition/work, and return every persisted source field as work_source. For ETHIO81 recommend the composite when covered, then verified English, provisional English, then verified original language. With no English coverage return null plus the explicit reason. Do not add supplemental works to Ethiopian navigation.

    def _work_source_payload(source):
        if source is None:
            return None
        return {
            'source_key': source.source_key,
            'source_label': source.source_label,
            'source_language': source.source_language,
            'source_tradition': source.source_tradition,
            'published_year': source.published_year,
            'license': source.license_spdx,
            'attribution': source.attribution,
            'provenance_url': source.provenance_url,
            'fallback': source.fallback,
            'modified': source.modified,
            'modification_note': source.modification_note,
            'verification_status': source.verification_status,
            'canon_scope': source.canon_scope,
        }

- [ ] **Step 4: Run and commit**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests/library/test_library_catalog.py backend/tests/library/test_library_routes.py -q
    git add backend/app/library/router.py backend/tests/library/test_library_catalog.py backend/tests/library/test_library_routes.py
    git commit -m "feat: expose composite source coverage"

---

### Task 7: Select recommended reader text

**Files:** frontend reader API, picker, page, and their tests

- [ ] **Step 1: Write failing tests**

    expect((await getBookCatalog('ETHIO81'))[0]).toMatchObject({
      id: 'genesis',
      recommendedEdition: 'EOTC-COMPOSITE-EN',
      unavailableReason: null,
    })

    expect(onChoose).toHaveBeenCalledWith({
      book: 'Genesis',
      chapter: 1,
      translation: 'EOTC-COMPOSITE-EN',
    })

- [ ] **Step 2: Verify failure**

    npm --prefix frontend test -- --run src/reader/scriptureApi.test.js src/reader/BookPicker.test.jsx src/reader/ScriptureReaderPage.test.jsx

- [ ] **Step 3: Preserve metadata and route it**

getBookCatalog retains id, taxonomy, coverage, recommendedEdition, and unavailableReason. BookPicker retains the selected object and returns its recommendation. ScriptureReaderPage applies a non-null recommendation when choosing a book and prefers it over an arbitrary first chapter row.

    return [{
      id: String(book?.id ?? name),
      name,
      testament: normalizedTaxonomy(book?.testament, 'testament'),
      collection: normalizedTaxonomy(book?.collection, 'collection'),
      recommendedEdition: typeof book?.recommended_edition === 'string'
        ? book.recommended_edition : null,
      unavailableReason: typeof book?.unavailable_reason === 'string'
        ? book.unavailable_reason : null,
      coverage: Array.isArray(book?.coverage) ? [...book.coverage] : [],
    }]

- [ ] **Step 4: Run and commit**

    npm --prefix frontend test -- --run src/reader/scriptureApi.test.js src/reader/BookPicker.test.jsx src/reader/ScriptureReaderPage.test.jsx
    git add frontend/src/reader/scriptureApi.js frontend/src/reader/scriptureApi.test.js frontend/src/reader/BookPicker.jsx frontend/src/reader/BookPicker.test.jsx frontend/src/reader/ScriptureReaderPage.jsx frontend/src/reader/ScriptureReaderPage.test.jsx
    git commit -m "feat: recommend composite English reading text"

---

### Task 8: Add accessible source disclosure

**Files:** TextSourceDisclosure files; reader pane, status, page, tests, and readerTokens.css

- [ ] **Step 1: Write failing tests**

    expect(screen.getByText('KJV fallback')).toBeVisible()
    expect(screen.getByText('Provisional source record')).toBeVisible()
    await user.click(screen.getByText('About this text'))
    expect(screen.getByText('Greek and Hebrew')).toBeVisible()

    expect(screen.getByRole('heading', {
      name: 'English text not yet available for Tegsats',
    })).toBeVisible()

- [ ] **Step 2: Verify failure**

    npm --prefix frontend test -- --run src/reader/TextSourceDisclosure.test.jsx src/reader/ScripturePane.test.jsx src/reader/ReaderStatus.test.jsx src/reader/ScriptureReaderPage.test.jsx

- [ ] **Step 3: Normalize and render**

normalizeWorkSource converts API snake case once. TextSourceDisclosure shows source label and literal fallback/provisional badges. Native details/summary exposes language, tradition, date, license, attribution, modification note, and optional provenance link. ScripturePane receives the first selected row source. Missing composite coverage uses translation-unavailable and never creates an empty verse.

    export function normalizeWorkSource(value) {
      if (!value || typeof value !== 'object') return null
      return {
        sourceKey: value.source_key ?? null,
        sourceLabel: value.source_label ?? 'Source details unavailable',
        sourceLanguage: value.source_language ?? null,
        sourceTradition: value.source_tradition ?? null,
        publishedYear: value.published_year ?? null,
        license: value.license ?? null,
        attribution: value.attribution ?? null,
        provenanceUrl: value.provenance_url ?? null,
        fallback: value.fallback === true,
        modified: value.modified === true,
        modificationNote: value.modification_note ?? null,
        verificationStatus: value.verification_status ?? null,
        canonScope: value.canon_scope ?? null,
      }
    }

- [ ] **Step 4: Style accessibility**

Use text plus color, 44px summary target, focus-visible outline, 320px wrapping, 4.5:1 contrast in light/dark, and stable 200% zoom.

- [ ] **Step 5: Run and commit**

    npm --prefix frontend test -- --run src/reader/TextSourceDisclosure.test.jsx src/reader/ScripturePane.test.jsx src/reader/ReaderStatus.test.jsx src/reader/ScriptureReaderPage.test.jsx
    git add frontend/src/reader/TextSourceDisclosure.jsx frontend/src/reader/TextSourceDisclosure.test.jsx frontend/src/reader/ScripturePane.jsx frontend/src/reader/ScripturePane.test.jsx frontend/src/reader/ReaderStatus.jsx frontend/src/reader/ReaderStatus.test.jsx frontend/src/reader/ScriptureReaderPage.jsx frontend/src/reader/ScriptureReaderPage.test.jsx frontend/src/reader/scriptureApi.js frontend/src/reader/readerTokens.css
    git commit -m "feat: disclose composite text sources in reader"

---

### Task 9: Make Compare Scripture source-aware

**Files:** comparison workspace, model, card, tests, and CSS

- [ ] **Step 1: Write failing tests**

    expect(sourceFromRow(compositeRow)).toMatchObject({
      key: 'eotc-composite-en',
      fallback: true,
      sourceLabel: 'KJV 1611 fallback',
    })

    expect(summarizeComparison(['In the beginning', null])).toMatchObject({
      availableCount: 1,
      differenceCount: 0,
    })

- [ ] **Step 2: Verify failure**

    npm --prefix frontend test -- --run src/components/textualComparison/comparisonModel.test.js src/components/TextualComparisonWorkspace.test.jsx

- [ ] **Step 3: Implement dynamic sources**

sourceFromRow returns code, name, language, tradition, current work source label, fallback, provisional, attribution, and provenance. Build installed choices from unique chapter rows. Prefer the composite as base when present. Render literal source badges. Exclude unavailable text from differences. Retain canon=ETHIO81 while changing sources. Prayer of Manasseh appears only when requested from broader library context.

    export function sourceFromRow(row) {
      const code = String(
        row?.edition?.code ?? row?.translation ?? ''
      ).trim().toUpperCase()
      if (!code) return null
      const metadata = row?.work_source ?? {}
      return {
        key: code.toLocaleLowerCase(),
        code,
        name: row?.edition?.name || code,
        language: row?.edition?.language || 'Unknown language',
        tradition: metadata.source_tradition
          || row?.edition?.source_tradition
          || 'Source details pending',
        sourceLabel: metadata.source_label || null,
        fallback: metadata.fallback === true,
        provisional: metadata.verification_status === 'provisional',
        attribution: metadata.attribution || null,
        provenanceUrl: metadata.provenance_url || null,
      }
    }

- [ ] **Step 4: Run and commit**

    npm --prefix frontend test -- --run src/components/textualComparison/comparisonModel.test.js src/components/TextualComparisonWorkspace.test.jsx
    git add frontend/src/components/TextualComparisonWorkspace.jsx frontend/src/components/TextualComparisonWorkspace.test.jsx frontend/src/components/textualComparison/comparisonModel.js frontend/src/components/textualComparison/comparisonModel.test.js frontend/src/components/textualComparison/TranslationComparisonCard.jsx frontend/src/components/TextualComparisonWorkspace.css
    git commit -m "feat: show composite sources in scripture comparison"

---

### Task 10: Document and verify end-to-end

**Files:** docs/scripture-sources.md, frontend/e2e/ethiopian-composite-english.spec.js

- [ ] **Step 1: Document the edition**

Record provisional mixed-source status, 82+1 scope, 13 unavailable works, six KJV fallbacks, Meqabyan CC BY-SA attribution, checksum, and exact operator commands.

- [ ] **Step 2: Add Playwright flows**

Cover composite Genesis source disclosure, Baruch fallback, Meqabyan attribution, Tegsats unavailable, comparison exclusion, keyboard details, axe, light/dark, 200% zoom, and 320px mobile.

- [ ] **Step 3: Run and commit**

    npm --prefix frontend run lint
    npm --prefix frontend run build
    npm --prefix frontend run test:e2e -- ethiopian-composite-english.spec.js
    git add docs/scripture-sources.md frontend/e2e/ethiopian-composite-english.spec.js
    git commit -m "test: verify composite English reader flows"

---

### Task 11: Import and run full verification

- [ ] **Step 1: Create a disposable migrated database**

    export COMPOSITE_TEST_DB="sqlite:////private/tmp/unbound-composite-english.db"
    rm -f /private/tmp/unbound-composite-english.db
    DATABASE_URL="$COMPOSITE_TEST_DB" PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m alembic -c backend/alembic.ini upgrade head

- [ ] **Step 2: Seed and stage**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m app.library.ingest.cli seed-canon --database-url "$COMPOSITE_TEST_DB"
    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m app.library.ingest.cli stage --manifest backend/data/scripture/eotc-composite-en/manifest.json --database-url "$COMPOSITE_TEST_DB"

Save the emitted run ID as COMPOSITE_RUN_ID.

- [ ] **Step 3: Validate and publish**

    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m app.library.ingest.cli validate --run-id "$COMPOSITE_RUN_ID" --database-url "$COMPOSITE_TEST_DB"
    PYTHONPATH=backend /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m app.library.ingest.cli publish --run-id "$COMPOSITE_RUN_ID" --confirm --database-url "$COMPOSITE_TEST_DB"

Expected: 38,938 corrected rows, zero errors, 83 source records, 82 Ethiopian scope, one supplemental, provisional status, and exactly twelve declared absent labels (two Meqabyan, ten Murdock alignment positions).

- [ ] **Step 4: Run all verification**

    /Users/obietaylor/.gemini/antigravity/scratch/unbound-bible/venv/bin/python -m pytest backend/tests -q
    npm --prefix frontend test -- --run
    npm --prefix frontend run lint
    npm --prefix frontend run build
    npm --prefix frontend run test:e2e

- [ ] **Step 5: Manual source audit**

Audit Genesis 1:1, Matthew 1:1, 1 Meqabyan 1:1, 1 Enoch 1:1, Baruch 1:1, Prayer of Manasseh 1:1, and Tegsats. Record archive locator, database checksum, displayed source label, license, and scope.

- [ ] **Step 6: Confirm cleanliness**

    git diff --check
    git status --short

Expected: no uncommitted changes.

## Completion criteria

- ZIP checksum is 0f4bdff8e24ee7e67afbd939d68a8dc40c0f1cf27026066dbb9f92ce34b183a2.
- The supplied artifact audit remains exactly 44,114 raw records; only the duplicate-free corrected row count in `data-quality-report.json` publishes across 1,520 chapters.
- The corrected bundle has no duplicate positions, no empty chapters, and no undeclared verse-number gaps.
- Exactly 82 sources have Ethiopian scope and Prayer of Manasseh alone is supplemental.
- All 13 uncovered Ethiopian works remain visible and accurately unavailable.
- Six KJV-derived books have literal fallback labels.
- Meqabyan attribution and CC BY-SA details appear in both UIs.
- GEEZ1980-RESEARCH remains unchanged.
- Both UIs use API source metadata rather than edition-code inference.
- Backend, frontend, lint, build, desktop, mobile, and accessibility verification pass.
