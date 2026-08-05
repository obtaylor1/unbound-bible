# Commentary import operations

This runbook publishes only the five reviewed, provider-declared public-domain commentary sources pinned in `backend/data/commentaries/sources.json`. Run every command from the repository root. Keep `DATABASE_URL` pointed at the migrated operator database for the entire procedure.

## 1. Prepare and back up

1. Stop commentary import or publication jobs so there is one operator for this source.
2. Confirm database migrations are current.
3. Create and verify a database backup before acquisition or publication. For PostgreSQL, retain a tested `pg_dump` backup and record its restore command. For a local SQLite operator database, stop writers and copy the database plus its `-wal` and `-shm` files as one backup set.
4. Set the explicit database target:

   ```text
   export DATABASE_URL='postgresql://…'
   ```

## 2. Review the source license record

Before acquiring a source, open its record in `backend/data/commentaries/sources.json` and check every item:

- source ID, title, author, publication period, and attribution identify the intended work;
- `license_spdx` is `LicenseRef-Public-Domain`;
- `license_url` is the Creative Commons Public Domain Mark 1.0 URL;
- `license_basis` explains the provider declaration;
- `license_reviewed_on` records the completed review date;
- `upstream_url`, expected book IDs, expected book count, and catalog checksum match the approved provider catalog;
- no unreviewed source or book ID has been added.

Stop if any field is missing, changed, or uncertain. A technical import does not replace a license review.

## 3. Acquire checksum-protected artifacts

Run the command for the reviewed source. Acquisition accepts only HTTPS URLs below `https://bible.helloao.org/api/`, writes resumable `.part` files, validates JSON and size limits, and creates a SHA-256 sidecar for every completed artifact.

```text
PYTHONPATH=backend python -m app.commentary.ingest.cli acquire --source matthew-henry --output backend/data/commentaries/raw
```

Repeat with `john-gill`, `adam-clarke`, `jamieson-fausset-brown`, or `keil-delitzsch` as needed. A successful response has `"status":"acquired"`. A response with `"status":"error"` is a blocked gate; correct the reported cause and rerun. Do not rename or edit acquired JSON or `.sha256` files.

## 4. Stage locally reviewed data

```text
PYTHONPATH=backend python -m app.commentary.ingest.cli stage --source matthew-henry --input backend/data/commentaries/raw/matthew-henry
```

Expected status: `staged`. Save the returned `run_id`. Staging creates no public publication, and checksum or source-identity mismatches block the command.

## 5. Validate and review coverage

```text
PYTHONPATH=backend python -m app.commentary.ingest.cli validate --run-id RUN_UUID
PYTHONPATH=backend python -m app.commentary.ingest.cli report --run-id RUN_UUID --output commentary-coverage.json
```

Expected validation status is `verified` with zero errors. `validated` means publication is blocked. Review `commentary-coverage.json` before continuing:

- every expected book is present;
- entries and per-book counts are plausible;
- coverage has not regressed by more than five percent;
- duplicate, overlapping, unsafe-markup, locator, or provenance findings are absent;
- warnings about missing introductions are understood and accepted.

The report is deterministically serialized and atomically written. Keep it with the operator record for the release.

## 6. Publish with explicit confirmation

Reconfirm the database backup and the `run_id`, then publish:

```text
PYTHONPATH=backend python -m app.commentary.ingest.cli publish --run-id RUN_UUID --confirm
```

Expected status: `published`. Record the returned `publication_id`, version, source ID, and edition ID. Without `--confirm`, publication is refused. The command commits only after the complete publication succeeds; a failure rolls back the transaction and leaves the previous active edition in place.

## 7. Smoke test the published source

With the app running at `http://localhost:5001`, open and verify:

- `http://localhost:5001/#scriptures?book=Genesis&chapter=1&translation=KJV&canon=ETHIO81`
- `http://localhost:5001/api/v1/commentaries/sources`
- `http://localhost:5001/api/v1/commentaries/entries?source=matthew-henry&book=Genesis&chapter=1`
- `http://localhost:5001/api/v1/commentaries/entries?source=matthew-henry&book=Genesis&chapter=1&verse=1`

Confirm the source name, attribution, license, chapter overview, exact verse or covering range, and explicit unavailable state. Compare at least one displayed entry with the acquired checksum-protected artifact. The API routes become available with the commentary API delivery task; until then, perform the database and report checks only.

## 8. Roll back if verification fails

Rollback is available only when the active publication has a previous immutable edition. Use the active `publication_id` returned by publish:

```text
PYTHONPATH=backend python -m app.commentary.ingest.cli rollback --publication-id PUBLICATION_ID --confirm
```

Expected status: `rolled_back`. Rollback creates a new active publication version pointing to the preceding immutable edition; it does not rewrite historical commentary entries. Run the report and smoke tests again, record the new publication ID and version, and retain the failed run and its findings for investigation.

All commands print exactly one JSON document to standard output. Automation must treat any nonzero exit code or `"status":"error"` response as failure and must not proceed to the next gate.
