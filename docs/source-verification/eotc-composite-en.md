# EOTC composite English verification and release runbook

## Public identity and limits

`EOTC-COMPOSITE-EN` is the **Ethiopian Canon Research Collection**, a **mixed-source English research collection**. It is **not complete, official, uniform, or ecclesiastically authorized**. It combines independently sourced texts for research and general reading; it is not one Ethiopian Orthodox translation and does not claim approval by an Ethiopian Orthodox church body.

The supplied archive contains 83 readable works. Source remediation covers exactly **39 WMB + 27 Murdock + 6 permanent KJV fallback + 1 Jubilees = 73** verified works. The other ten supplied works remain readable with their existing provenance and `in_progress` status: 1 Enoch, 1–3 Meqabyan, 1 Esdras, 2 Esdras, Tobit, Judith, Wisdom of Solomon, and Sirach. An in-progress record is not a verified-source claim.

The six fallback works—Baruch, Letter of Jeremiah, Prayer of Azariah, Susanna, Bel and the Dragon, and Prayer of Manasseh—always display `KJV fallback`. Verification must never remove that flag or imply a distinct Ethiopian Orthodox English translation.

Thirteen ETHIO81 catalog works do not have supplied English text in this edition and remain visibly unavailable. No placeholder or generated scripture is published for them. Prayer of Manasseh is readable only as a supplemental `LIBRARY` work.

## Reviewed source families

| Group | Immutable source identity | Locked artifact SHA-256 | Rights and jurisdiction | Review and transformations | Final report SHA-256 |
|---|---|---|---|---|---|
| 39 WMB works | [Official eBible `engwmb` August 2022 VPL archive](https://ebible.org/find/show.php?id=engwmb), artifact URL `https://ebible.org/Scriptures/engwmb_vpl.zip` | `02aef8d71addf7bf01438d1d132536f3d2cceb21820df6427015cddd608cfbf8` | Public-domain dedication; World Messianic Bible trademark naming condition applies | Reviewed by Obie Taylor on `2026-08-29T00:38:39Z`. Deterministic VPL-to-app conversion preserves scripture wording and verse identities. | `world-messianic-bible.json`: `b7ffa08d52fd42eea89567e6cf50a2541687fda9567a5591dc7f9d620eaeef9c` |
| 27 Murdock works | [CrossWire Murdock SWORD module 1.2](https://crosswire.org/sword/modules/ModInfo.jsp?modName=Murdock), immutable module identity `Murdock 1.2 (2002-01-01)`; historical witness [Internet Archive `syriacnewtestam00murdgoog`](https://archive.org/details/syriacnewtestam00murdgoog) | Module `4f0adeba385acbfa37921f66677d4aaf99e23b4e65ca162f122832689036641f`; historical PDF `be4d1425fe69b4ff24fa418e15a2a2fbfb924db50d7e06861a937cfd3c81bc05` | Public domain | OpenAI Codex, AI-assisted source verification, `2026-08-29T19:56:29Z`; no human visual review claimed. RF notes and FI display markers are removed, four source separators normalized, one unique Philemon spill recovered, and ten blank positions declared without invention. | `murdock-peshitta-1852.json`: `79185014f9d9fe35d2d4ac767a479bf04554387259dd28d0163ca660827a1456` |
| 6 permanent KJV fallback works | [Project Gutenberg eBook 124](https://www.gutenberg.org/ebooks/124), updated `2021-08-26`; historical authority [UPenn Colenda ARK `81431-p3rv0df45`](https://colenda.library.upenn.edu/catalog/81431-p3rv0df45) | Electronic text `83de0c18742ba22b3d442c3a5bc828fe9e91dff27ae3c298e9b5c9a6ecfbf4d4`; historical manifest and every locked page checksum are in `verification/kjv-1611-historical-artifacts.lock.json` | Public domain in the USA; UPenn rights statement `NoC-US` | OpenAI Codex, AI-assisted visual source verification, `2026-08-30T01:18:59Z`; no human visual review claimed. Exact structural mappings and four scan-backed corrections are recorded; the KJV fallback label is permanent. | `kjv-1611-fallback.json`: `72815efedf324f64b8e1207ea6daee8121230ba3811414a69330767ff90343b7` |
| 1 Jubilees work | [Global Grey authorized 1917 reprint transcription](https://www.globalgreyebooks.com/online-ebooks/r-h-charles_book-of-jubilees_complete-text.html); edition and numbering authority [Internet Archive `bookofjubileesor00char`](https://archive.org/details/bookofjubileesor00char), A. and C. Black 1902 | Transcription `e48d840d060a64cfdee1c7cec640770fdf1c3f2daf76c84383163ce9126dd54a`; 1902 PDF `bf8b2578e258b2798ca5ee89b9083b7733e5ed89dc4c338473df685913ad7203` | Public domain in the USA | OpenAI Codex, AI-assisted source verification, `2026-08-30T08:55:00Z`; no human visual review claimed. Editorial matter is excluded; only seven scan-confirmed marker repairs and the scan-confirmed chapter-27 structure are applied. The authentic 50-chapter numbering totals 1,307 positions; no positions were invented. | `rh-charles-jubilees-1902.json`: `3acb7eaf39ea1fc3b1e76574ee105e15fd79bd129d7009420548dee53c953341` |

Per-work artifact, rights, source edition/revision, transformation, reviewer, review time, and comparison-report checksums are authoritative in `manifest.json`. The family reports above are immutable audit summaries. Visual-review and pre-rebuild reports remain committed beside them; they do not override the final exact comparison.

## Release invariants

- All 83 supplied works remain readable. Verification changes evidence and, where reviewed, rebuilds text from the locked source; it does not hide in-progress supplied works.
- The 73 remediation works use only `verified_exact`, `verified_formatting`, or `verified_rebuilt` and have zero unexplained missing, extra, formatting, or wording differences in their final reports.
- The other ten supplied works remain `in_progress` until their own source review is complete.
- Every public source disclosure has a screen-reader name, plain-language status, keyboard-operable details, safe source links, and visible fallback wording where required.
- Publication is local-data-only, edition-scoped, atomic, and reversible. A publication never downloads a source and never changes another edition.
- Collection copy must use “Ethiopian Canon Research Collection” or “mixed-source English research collection”; it must not describe this edition as complete, official, uniform, or ecclesiastically authorized.

## Local verification gates

Run from the repository root with the project virtual environment. These commands read only committed local artifacts and create no publication:

```bash
./venv/bin/python backend/data/scripture/eotc-composite-en/build_bundle.py --check
./venv/bin/python backend/data/scripture/eotc-composite-en/build_manifest.py --check
PYTHONPATH=backend ./venv/bin/python -m pytest -q
(cd frontend && npm test -- --run && npm run lint && npm run build)
(cd frontend && npm run test:e2e -- scripture-source-verification.spec.js scripture-reader-accessibility.spec.js ethiopian-composite-english.spec.js compare-scripture.spec.js)
```

The source verifier never downloads. An operator may re-check a reviewed artifact already present in `verification/artifacts` by running a family comparison into a temporary directory:

```bash
export REVIEW_TMP="$(mktemp -d /private/tmp/unbound-source-review.XXXXXX)"
PYTHONPATH=backend ./venv/bin/python -m app.library.verification.cli compare-family world-messianic-bible --current-bundle backend/data/scripture/eotc-composite-en/corrected-bundle.zip --output "$REVIEW_TMP/wmb"
PYTHONPATH=backend ./venv/bin/python -m app.library.verification.cli compare-family murdock-peshitta-1852 --current-bundle backend/data/scripture/eotc-composite-en/corrected-bundle.zip --output "$REVIEW_TMP/murdock"
PYTHONPATH=backend ./venv/bin/python -m app.library.verification.cli compare-family kjv-1611-fallback --current-bundle backend/data/scripture/eotc-composite-en/corrected-bundle.zip --output "$REVIEW_TMP/kjv"
PYTHONPATH=backend ./venv/bin/python -m app.library.verification.cli compare-family rh-charles-jubilees-1902 --current-bundle backend/data/scripture/eotc-composite-en/corrected-bundle.zip --output "$REVIEW_TMP/jubilees"
```

Do not replace a locked artifact or source definition during a release. A new upstream edition requires a new lock, comparison, review, report, candidate, and approval.

## Isolated staging, health check, rollback, and republish

Never rehearse against the development or production database. The automated production-like rehearsal below creates a migrated temporary database, publishes a full 38,487-row predecessor and reviewed candidate, checks text and source evidence together, rolls back, and republishes the reviewed state:

```bash
PYTHONPATH=backend ./venv/bin/python -m pytest backend/tests/library/ingest/test_quality_gate_e2e.py::test_production_like_composite_staging_rollback_and_republish_rehearsal -q
```

For an operator-observed staging run, create a new disposable database, keep its URL explicit, and stop on any unexpected count:

```bash
export COMPOSITE_DB_DIR="$(mktemp -d /private/tmp/unbound-composite-staging.XXXXXX)"
export COMPOSITE_DB_URL="sqlite:///$COMPOSITE_DB_DIR/staging.db"
test ! -e "$COMPOSITE_DB_DIR/staging.db"
sqlite3 "$COMPOSITE_DB_DIR/staging.db" 'CREATE TABLE biblical_texts (id INTEGER PRIMARY KEY, book TEXT NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL, text TEXT NOT NULL, translation TEXT)'
PYTHONPATH=backend DATABASE_URL="$COMPOSITE_DB_URL" ./venv/bin/alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli seed-canon --database-url "$COMPOSITE_DB_URL"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli stage --manifest backend/data/scripture/eotc-composite-en/manifest.json --database-url "$COMPOSITE_DB_URL"
```

Copy the emitted run ID only after confirming `staged_count` is 38,487:

```bash
export COMPOSITE_RUN_ID="reviewed-run-id"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli validate --run-id "$COMPOSITE_RUN_ID" --database-url "$COMPOSITE_DB_URL"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli publish --run-id "$COMPOSITE_RUN_ID" --confirm --database-url "$COMPOSITE_DB_URL"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli coverage-report --run-id "$COMPOSITE_RUN_ID" --edition EOTC-COMPOSITE-EN --database-url "$COMPOSITE_DB_URL" | tee "$COMPOSITE_DB_DIR/health.json"
jq -e --arg run_id "$COMPOSITE_RUN_ID" '
  .run_id == $run_id and
  .active_run_id == $run_id and
  .is_active == true and
  .status == "published" and
  .checksum == "35b5878274f1287b0edf28315275ac7fcdff7bb7d7d41ffe2a5984a4e78b46cd" and
  .staged_count == 38487 and
  .published_count == 38487 and
  .errors == 0 and
  .inventory.populated_work_count == 83 and
  .inventory.chapter_count == 1520 and
  .inventory.verse_count == 38487 and
  .inventory.verified_work_count == 73 and
  .inventory.in_progress_work_count == 10 and
  .inventory.fallback_work_count == 6 and
  .inventory.catalog_unavailable_work_count == 13 and
  .inventory.catalog_unavailable_work_ids == [
    "abtilis",
    "didesqelya",
    "esther-greek-additions",
    "gitsew",
    "josippon",
    "metsihafe-kidan-1",
    "metsihafe-kidan-2",
    "paralipomena-jeremiah",
    "psalm-151",
    "qalementos",
    "sirate-tsion",
    "tegsats",
    "tizaz"
  ] and
  .inventory.verification_status_totals == {
    "in_progress": 10,
    "verified_exact": 13,
    "verified_rebuilt": 60
  }
' "$COMPOSITE_DB_DIR/health.json"
```

Validation must report zero errors, and `jq` must exit zero. The coverage report resolves the active publication even when `--run-id` is supplied and exposes `active_run_id` plus `is_active`; a displaced or rolled-back run cannot pass this gate. The assertion also fails closed unless the requested active run has the exact reviewed source checksum, published status, 38,487 staged and published rows, zero errors, 83 populated works, 1,520 chapters, 73 verified remediation records, ten in-progress supplied records, six fallback flags, and exactly the 13 unavailable ETHIO81 works excluded from the populated publication.

For the complete browser gate, keep the isolated database above and start a disposable local API in a separate terminal. The increased limits are test-only capacity for Playwright's five parallel projects; they do not change production configuration:

```bash
(cd backend && \
  ENVIRONMENT=test \
  DATABASE_URL="$COMPOSITE_DB_URL" \
  AUTH_RATE_LIMIT=1000 AI_RATE_LIMIT=1000 SEARCH_RATE_LIMIT=1000 SHARING_RATE_LIMIT=1000 \
  ../venv/bin/python -m uvicorn app.application:app --host 127.0.0.1 --port 8000)
```

Then, in the repository root, run the full public acceptance suite and stop the disposable API when it finishes. This confirms reader, search, comparison, commentary, research, authentication, sharing, mobile layouts, themes, zoom, keyboard access, screen-reader names, axe checks, and anonymous admin denial:

```bash
(cd frontend && LIVE_SOURCE_E2E=1 npm run test:e2e)
```

Rollback requires a distinct predecessor. Audit before and after; scripture rows and work-source evidence must change together:

```bash
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli coverage-report --edition EOTC-COMPOSITE-EN --database-url "$COMPOSITE_DB_URL"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli rollback --edition EOTC-COMPOSITE-EN --database-url "$COMPOSITE_DB_URL"
PYTHONPATH=backend ./venv/bin/python -m app.library.ingest.cli coverage-report --edition EOTC-COMPOSITE-EN --database-url "$COMPOSITE_DB_URL"
```

Republish only by staging and validating the reviewed manifest as a new run; a rolled-back run is immutable and cannot be reused. If any health check fails, leave the previous publication active and investigate. Real production publication, external services, and DNS are outside this local rehearsal and require separate operator approval, backup, and change control.
