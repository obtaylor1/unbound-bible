# Scripture source registry

Scripture text is published only through the verified ingestion pipeline. Source archives and application databases are not committed to this repository.

## Ge'ez Bible (1980 EC) — Research Use

- Edition code: `GEEZ1980-RESEARCH`
- Reading and source language: Ge'ez
- Script: Ethiopic
- Relationship: exact Ethiopian source text
- Provenance: [EOTCOpenSource/80-weahadu](https://github.com/EOTCOpenSource/80-weahadu), with Ran HaCohen's Ethiopic Bible identified by the supplied bundle as a supplementary source
- Source archive SHA-256: `7b66e154d0ad5f6f22d166831d3bea966541913c58bad45d8b5ece6ac5553d5c`
- License and use limitation: `CC-BY-NC-ND-4.0` applies to the identified repository material; the Bible text is identified as copyright Ethiopian Bible Society. This edition is enabled for local research and prototyping only. Redistribution and commercial use require permission from the applicable rights holders.

### Reviewed coverage

Only Genesis is currently approved for publication:

- 50 chapters
- 1,533 verse positions
- 31 verses in Genesis 1
- no empty text, duplicate positions, invalid positions, or coverage gaps
- one reviewed repeated-text warning: Genesis 39:15 and 39:18 are identical in this source

The remaining archive books are not approved merely because they are present. Their empty rows, duplicate positions, invalid positions, canon mapping, edition identity, and rights must be reviewed independently before their work IDs are added to a manifest allowlist.

### Reproducible local import

The `weahadu_bundle` adapter reads a single checksummed ZIP without extracting or executing it. Its manifest must sit beside the frozen archive and must explicitly map each approved source book to one canonical work. The standard operator sequence is:

```text
python -m app.library.ingest.cli seed-canon --database-url <migrated-database-url>
python -m app.library.ingest.cli stage --manifest <reviewed-manifest> --database-url <migrated-database-url>
python -m app.library.ingest.cli validate --run-id <run-id> --database-url <migrated-database-url>
python -m app.library.ingest.cli publish --run-id <run-id> --confirm --database-url <migrated-database-url>
```

The reader displays the human edition name and the persisted provenance metadata. It does not relabel the edition as a synthetic `ETHIO81` translation; `ETHIO81` remains the canon selector.

## Ethiopian Orthodox Bible — Composite English Edition

- Edition code: `EOTC-COMPOSITE-EN`
- Reading language: English
- Relationship: provisional mixed-source general-reading compilation
- Canon relationship: 82 covered `ETHIO81` works plus Prayer of Manasseh as one supplemental `LIBRARY` work
- Reviewed output: 38,938 rows across 1,520 chapters

This edition is **not** an official Ethiopian Orthodox edition, a uniform translation, or a complete English translation of the traditional canon. It combines separately attributed public-domain and openly licensed readings so users can read available English text while seeing the literal source for each work. `GEEZ1980-RESEARCH` remains a separate Ge'ez research edition and is unchanged by this compilation.

### Coverage and known unavailable works

The edition covers exactly 82 works represented in the `ETHIO81` catalog. Prayer of Manasseh is the eighty-third populated work, but it is supplemental and must only be exposed through the `LIBRARY` catalog. The following 13 `ETHIO81` works have no publishable English text in this edition and must remain visibly unavailable; the app must not invent verses or silently substitute another work:

- Esther Greek Additions (`esther-greek-additions`)
- Psalm 151 (`psalm-151`)
- Tegsats (`tegsats`)
- Paralipomena of Jeremiah (`paralipomena-jeremiah`)
- Josippon (`josippon`)
- Sirate Tsion (`sirate-tsion`)
- Tizaz (`tizaz`)
- Gitsew (`gitsew`)
- Abtilis (`abtilis`)
- Metsihafe Kidan I (`metsihafe-kidan-1`)
- Metsihafe Kidan II (`metsihafe-kidan-2`)
- Qalementos (`qalementos`)
- Didesqelya (`didesqelya`)

The manifest declares exactly 48 absent source or alignment labels without placeholders or renumbering:

- **36 WEB British Edition Sirach labels.** Twenty-four explicit blank VPL rows: 1:5, 1:7, 1:21, 3:19, 10:21, 11:15, 13:14, 16:15, 17:5, 17:9, 17:16, 17:18, 17:21, 18:3, 19:18, 19:21, 20:3, 20:32, 22:9, 23:28, 24:18, 24:24, 25:12, and 26:19. Twelve labels absent from the VPL: 11:16, 16:16, 19:19, 22:10, and 26:20–27.
- **2 Wikisource Meqabyan labels:** 2 Meqabyan 16:9 and 21:9.
- **10 Murdock alignment labels:** Matthew 26:30 and 26:45; Mark 4:10, 8:19, 9:31, and 11:19; Luke 18:35; Acts 19:41 and 20:17; and 2 Corinthians 13:14.

### Per-work source families and reuse

Every reader response carries per-work provenance. Do not describe the collection as a single translation.

| Works | Literal source family | Status and reuse responsibility |
|---|---|---|
| 39 Old Testament works | World Messianic Bible (WMB), user-archive revision | Public-domain archive text; upstream revision is unverified. Source chapter identifiers were normalized to numeric order and app work names were standardized; scripture prose and source verse labels were not changed. Retain the provisional label and attribution. |
| 27 New Testament works | James Murdock's 1852 English Peshitta | Public domain; translated from Syriac Aramaic. Source chapter identifiers and app work names were standardized, `FI`/`RF` apparatus was removed, ten blank positions were declared, and four U+000F separators were normalized; scripture words outside source apparatus and source verse labels were not changed. Retain the provisional archive-revision label. |
| 1 Esdras, 2 Esdras, Tobit, Judith, Wisdom, and Sirach | [Official eBible World English Bible British Edition with Deuterocanon (WEBBE)](https://ebible.org/details.php?id=eng-webbe) | Public domain. The official VPL's 24 explicit blank Sirach rows and 12 additional absent numeric labels were omitted and declared; every nonblank scripture row retains its official chapter and verse identity. Preserve the official source link and provisional verification status. |
| Baruch, Letter of Jeremiah, Prayer of Azariah, Susanna, Bel and the Dragon, and Prayer of Manasseh | KJV 1611 archive fallback | Public-domain archive text, recorded as unmodified. Always show a literal **KJV fallback** label. These are not distinct Ethiopian Orthodox translations. |
| 1–3 Meqabyan | Wikisource translations from Ge'ez | CC BY-SA 4.0. Source extraction and JSON formatting were applied without changing scripture prose; 2 Meqabyan also records its two absent labels. Reuse must credit contributors, identify changes, link the license, and preserve ShareAlike terms. Use permanent revisions [1 Meqabyan oldid 16044809](https://en.wikisource.org/w/index.php?title=Translation:1_Meqabyan&oldid=16044809), [2 Meqabyan oldid 16044810](https://en.wikisource.org/w/index.php?title=Translation:2_Meqabyan&oldid=16044810), and [3 Meqabyan oldid 16044811](https://en.wikisource.org/w/index.php?title=Translation:3_Meqabyan&oldid=16044811). |
| 1 Enoch | [R. H. Charles, Project Gutenberg ebook 77935](https://www.gutenberg.org/ebooks/77935) | Public domain in the USA. The Ethiopic (`E`) main reading, excluded alternates, joined fragments, normalized whitespace, and structural numbering are disclosed below and in the per-work source record. |
| Jubilees | R. H. Charles-related archive text | Public-domain archive text with unavailable exact upstream provenance. Source chapter identifiers were normalized to numeric order and the app work identifier was standardized; scripture prose was not changed. Retain the provisional warning. |

Source and license claims remain the responsibility of anyone redistributing the texts. In particular, downstream Meqabyan reuse must satisfy CC BY-SA 4.0, and operators must not erase per-work attribution, fallback, verification, canon-placement, modification, or provenance fields.

### Deterministic corrections and frozen artifacts

The build preserves source wording while making only disclosed structural and presentation corrections. Murdock `FI` emphasis delimiters and `RF` translator-note blocks are removed; its ten blank alignment positions are declared; and four U+000F separator characters across three verse texts are normalized to ordinary spaces. For Enoch, the displayed reading follows Charles's Ethiopic (`E`) main recension and excludes separately marked Greek alternate-recension blocks. Wrapped and lettered fragments are joined deterministically. Chapters 3, 4, 35, and 44 have no source verse numbering, so they use structural verse 1 solely as the app container. No blanket name substitution or prose rewrite is performed.

| Artifact | SHA-256 |
|---|---|
| Original `Ethiopian Orthodox Bible (Non-KJV Edition).zip` | `0f4bdff8e24ee7e67afbd939d68a8dc40c0f1cf27026066dbb9f92ce34b183a2` |
| Official `eng-webbe_vpl.zip` | `dc16460ed5e890e7b169cd3caeaa7e4adb4f7a6b5031bff85e4503389cd03b11` |
| Project Gutenberg `project-gutenberg-77935.txt` | `10d325355a810badf67bbbd1fe6bda77dc6e294eae78c2f6c69290188af45b14` |
| Generated `corrected-bundle.zip` | `4383d4af7c6768fdd093ff37fecb61dcaf657673dcea184ad27bb1ee1eaecf63` |
| Generated `data-quality-report.json` | `4abb0c1af30388949c936c94ed9b9155935d743c2fef5c45bb35f4259baa6e01` |
| Generated `manifest.json` | `da05b54e112dc5b834732bd14e981f85348d18a36671783b2d30b352a5dafe15` |

### Reproducible build and validation

Run from the repository root with the project's virtual environment. These checks do not publish data:

```bash
./venv/bin/python backend/data/scripture/eotc-composite-en/build_bundle.py --check
./venv/bin/python backend/data/scripture/eotc-composite-en/build_manifest.py --check
shasum -a 256 \
  "backend/data/scripture/eotc-composite-en/Ethiopian Orthodox Bible (Non-KJV Edition).zip" \
  backend/data/scripture/eotc-composite-en/eng-webbe_vpl.zip \
  backend/data/scripture/eotc-composite-en/project-gutenberg-77935.txt \
  backend/data/scripture/eotc-composite-en/corrected-bundle.zip \
  backend/data/scripture/eotc-composite-en/data-quality-report.json \
  backend/data/scripture/eotc-composite-en/manifest.json
PYTHONPATH=backend ./venv/bin/python -c 'from pathlib import Path; from app.library.ingest.manifest import SourceManifest; SourceManifest.model_validate_json(Path("backend/data/scripture/eotc-composite-en/manifest.json").read_text(encoding="utf-8"))'
PYTHONPATH=backend ./venv/bin/python -m pytest backend/tests/library/ingest/test_composite_english_bundle_adapter.py::test_reviewed_corrected_ethiopian_composite_bundle_is_reproducible_and_truthful -q
```

To regenerate reviewed outputs intentionally, omit `--check`, run `build_bundle.py` before `build_manifest.py`, then repeat every checksum and acceptance check above. Review and commit any changed artifact together; never hand-edit the generated bundle, report, or manifest.

### Disposable database staging and publication audit

Publication changes the selected database. First rehearse against a new disposable, migrated SQLite database—not a production file and not the repository's normal development database. Choose a unique path, confirm it does not already exist, and keep the URL explicit on every command:

```bash
export COMPOSITE_DB_DIR="$(mktemp -d /private/tmp/unbound-composite-english.XXXXXX)"
export COMPOSITE_DB_PATH="$COMPOSITE_DB_DIR/audit.db"
export COMPOSITE_DB_URL="sqlite:///$COMPOSITE_DB_PATH"
test ! -e "$COMPOSITE_DB_PATH" || exit 1
PYTHONPATH=backend DATABASE_URL="$COMPOSITE_DB_URL" ./venv/bin/python -c \
  'from database import engine; from models import Base; Base.metadata.create_all(bind=engine)'
PYTHONPATH=backend DATABASE_URL="$COMPOSITE_DB_URL" ./venv/bin/alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli seed-canon --database-url "$COMPOSITE_DB_URL"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli stage --manifest backend/data/scripture/eotc-composite-en/manifest.json --database-url "$COMPOSITE_DB_URL"
```

The legacy runtime bootstrap must run before Alembic. The application still
mirrors published reading text into `biblical_texts`; migration 0007 inspects
that table and adds its unique verse-identity index when the table is present.

Copy the exact `run_id` from the stage command's JSON output, then validate, publish with explicit confirmation, and audit persisted coverage:

```bash
export COMPOSITE_RUN_ID="paste-run-id-from-stage-here"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli validate --run-id "$COMPOSITE_RUN_ID" --database-url "$COMPOSITE_DB_URL"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli publish --run-id "$COMPOSITE_RUN_ID" --confirm --database-url "$COMPOSITE_DB_URL"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli coverage-report --run-id "$COMPOSITE_RUN_ID" --edition EOTC-COMPOSITE-EN --database-url "$COMPOSITE_DB_URL"
```

The staged and published counts must be 38,938, validation must report zero errors, persisted coverage must total 83 populated works and 1,520 chapters, and the 13 unavailable `ETHIO81` works must remain absent. Before publishing to any non-disposable database, back it up, review the active edition and per-work source records, and obtain the required operational approval.

Rollback restores only the immediate distinct predecessor and therefore requires an earlier published snapshot. It is expected to fail on a fresh one-publication rehearsal. Where a reviewed predecessor exists, audit first, run the atomic rollback, then audit again:

```bash
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli coverage-report --edition EOTC-COMPOSITE-EN --database-url "$COMPOSITE_DB_URL"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli rollback --edition EOTC-COMPOSITE-EN --database-url "$COMPOSITE_DB_URL"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli coverage-report --edition EOTC-COMPOSITE-EN --database-url "$COMPOSITE_DB_URL"
```

After the rehearsal and any rollback audit are complete, confirm `COMPOSITE_DB_DIR` is the temporary directory created above, then remove only its database file and the now-empty directory:

```bash
test -n "$COMPOSITE_DB_DIR" && test "$COMPOSITE_DB_DIR" != /private/tmp || exit 1
test "$COMPOSITE_DB_PATH" = "$COMPOSITE_DB_DIR/audit.db" || exit 1
rm -f -- "$COMPOSITE_DB_PATH"
rmdir -- "$COMPOSITE_DB_DIR"
```
