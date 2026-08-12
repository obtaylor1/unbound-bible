# The Unbound Bible Production Runbook

## Runtime topology

- Serve the React production build behind TLS.
- Run `uvicorn app.application:app` from `backend/`; do not run the legacy `backend/main.py` entry point in production.
- Use PostgreSQL for production. SQLite remains supported for tests and local evaluation.
- The former `auth-forum-api` runtime is retired. Community routes live under `/api/v1/community` and use unified accounts.

## Required production settings

```text
ENVIRONMENT=production
DATABASE_URL=postgresql://...
JWT_SECRET_KEY=<random value of at least 32 characters>
PUBLIC_BASE_URL=https://your-domain.example
CORS_ORIGINS=["https://your-domain.example"]
AI_CHAT_PROVIDER=openai_compatible|ollama
AI_EMBEDDING_PROVIDER=openai_compatible|ollama
AI_TRANSCRIPTION_PROVIDER=openai_compatible
AI_API_KEY=<required for OpenAI-compatible providers>
AI_CHAT_MODEL=<deployed model>
AI_EMBEDDING_MODEL=<deployed embedding model>
AI_TRANSCRIPTION_MODEL=<deployed transcription model>
```

Production startup rejects SQLite, HTTP public URLs, wildcard CORS, weak JWT secrets, missing required provider credentials, and demo providers. A deliberate demonstration deployment may set `ALLOW_PRODUCTION_DEMO=true`; the UI must remain visibly labeled Demo.

Optional controls include `AUTH_RATE_LIMIT`, `AI_RATE_LIMIT`, `SEARCH_RATE_LIMIT`, `SHARING_RATE_LIMIT`, `SERMON_RATE_LIMIT`, `UPLOAD_MAX_BYTES`, `UPLOAD_MAX_DURATION_SECONDS`, and `UPLOAD_TEMP_DIR`.

## Private staging configuration

Create `.env.staging` only on the protected staging host or in the deployment provider's encrypted configuration. Never commit it. Use this exact template, replacing every angle-bracket value:

```text
ENVIRONMENT=staging
POSTGRES_DB=unbound_bible
POSTGRES_USER=unbound_bible
POSTGRES_PASSWORD=<random database password>
DATABASE_URL=postgresql+psycopg2://unbound_bible:<URL-encoded database password>@db:5432/unbound_bible
JWT_SECRET_KEY=<random value of at least 32 characters>
PUBLIC_BASE_URL=https://<private-staging-host>
CORS_ORIGINS=["https://<private-staging-host>"]
AI_CHAT_PROVIDER=demo
AI_EMBEDDING_PROVIDER=demo
AI_TRANSCRIPTION_PROVIDER=demo
ALLOW_PRODUCTION_DEMO=true
BACKUP_DIR=/var/backups/unbound-bible
```

Staging uses the same fail-closed database, JWT, HTTPS, CORS, and provider checks as production. Use an OpenAI-compatible provider and `AI_API_KEY` instead of the explicit demo override when provider-backed features are under test. Limit access at the provider or TLS proxy; do not expose the database port.

From the repository root, validate configuration with `docker compose --env-file .env.staging -f compose.staging.yml config`, then start with `docker compose --env-file .env.staging -f compose.staging.yml up -d --build`. The API container applies Alembic migrations before Uvicorn starts. Readiness requires successful responses from `/api/v1/health`, `/api/v1/health/providers`, and the web container's `/healthz` endpoint.

## Continuous delivery to private staging

The Quality workflow runs backend tests, frontend unit tests, lint, production build, and Playwright before release review. The Railway API and web services are connected to the `main` branch with **Wait for CI** enabled, so Railway deploys the exact commit SHA only after GitHub reports successful Quality checks. Pull requests, forks, and similarly named branches do not deploy. Do not add a post-deployment GitHub workflow to this repository while **Wait for CI** is enabled: Railway treats it as another required action, which creates a circular wait between the deployment and its own health check.

Railway health checks verify `/api/v1/health` for the API service and `/healthz` for the web service before a deployment becomes active. After Railway reports both services online, verify `https://staging.theunboundbible.com/healthz`, `/api/v1/health`, and `/api/v1/health/providers` from outside Railway. This deployment path requires no deploy hook or long-lived provider secret.

After deployment, record the commit SHA, confirm all three health endpoints, run the release-readiness browser journey against the private URL, and compare release-critical row counts. Do not open access when any check fails.

## Deployment sequence

1. Back up PostgreSQL and verify that the backup can be listed and restored.
2. Record counts for users, studies, notes, shares, notifications, community posts/comments, and biblical texts.
3. Run `alembic -c backend/alembic.ini upgrade head` with the production `DATABASE_URL`.
4. Before retiring the standalone forum, run `cd backend && python -m app.community.migration --source sqlite:////absolute/path/auth_forum.db --report /secure/path/community-migration-report.json`. Require empty `unmapped_posts` and `unmapped_comments`, and reconcile imported plus existing users/posts/comments with the source counts. The importer is idempotent and preserves legacy ownership, password hashes, timestamps, and IDs.
5. Start the modular backend and check `/api/v1/health` and `/api/v1/health/providers`.
6. Deploy the frontend build. Confirm its environment has `VITE_ENABLE_DEMO=false`.
7. Run the critical browser suite against the deployment.
8. Compare row counts and investigate any unexplained reduction before opening traffic. Keep the source database read-only until the retention window closes.

## Backup and restore

Use platform-native PostgreSQL snapshots plus the repository's logical backup. Encrypt exported backups, restrict operator access, and test restoration on a separate database. The staging API receives an explicit `BACKUP_DIR=/var/backups/unbound-bible`; Compose mounts the persistent `backup_data` volume there. `DATABASE_URL` remains explicit in the protected `.env.staging` file and must never be placed in a command line copied into a ticket or terminal transcript.

Create a custom-format logical backup from the repository root with the `./scripts/backup-staging.sh` wrapper:

```sh
docker compose --env-file .env.staging -f compose.staging.yml run --rm api ./scripts/backup-staging.sh
```

The backup wrapper creates the directory with mode `0700`, writes a temporary dump with mode `0600`, flushes completed files and publication renames to stable storage, and publishes a UTC-named `unbound-bible-YYYYMMDDTHHMMSSZ.dump` alongside an atomically written mode-`0600` `.dump.manifest.json`. The versioned manifest records release-critical counts and the dump's SHA-256 digest. A crash between the two publication renames can leave an orphan dump; automatic latest-backup selection ignores it and uses the newest structurally complete dump/manifest pair. It does not fall back when the newest complete pair is present but malformed or tampered—verification fails and deployment remains blocked. Restoration also refuses an overly permissive, renamed, symlinked, non-regular, oversized, or digest-mismatched manifest, so counts from one backup cannot silently validate another dump.

Counts and `pg_dump` use the same PostgreSQL exported `REPEATABLE READ`, read-only snapshot: the count transaction remains open while `pg_dump --snapshot` completes. Writes committed after snapshot export are consistently excluded from both the dump and recorded counts. Do not run migrations, DDL, database renames, or table maintenance during the backup window; schedule those only after the dump and manifest have both appeared. Copy both files from the named volume into encrypted, access-controlled storage according to the provider retention policy. A container volume is not a substitute for an off-host encrypted copy.

Before every deploy and on the scheduled recovery rehearsal, verify the newest dump with the `./scripts/restore-check-staging.sh` wrapper:

```sh
docker compose --env-file .env.staging -f compose.staging.yml run --rm api ./scripts/restore-check-staging.sh
```

The restore check never restores over the source. It validates the manifest and digest before database creation, then creates a cryptographically random, strictly prefixed disposable database; restores with `pg_restore`; applies Alembic migrations; starts the restored API; checks `/api/v1/health` and `/api/v1/health/providers`; and compares `biblical_texts`, users, studies, notes, shares, notifications, community posts, and community comments against the counts recorded at backup time—not a changing live source. It terminates only connections to that guarded disposable database and attempts to drop it after either success or failure. If verification and cleanup both fail, the primary verification error remains the reported failure and carries a safe critical cleanup note; deployment stays blocked until an operator confirms removal. A mismatch, unhealthy endpoint, migration error, restore error, or cleanup error blocks deployment. Never rename a normal database to the disposable prefix or run these wrappers with a superuser broader than the staging cluster requires.

## Rollback

Prefer application rollback while leaving forward-compatible migrations in place. Schema downgrades delete data introduced by their corresponding feature and therefore run only on a restored copy or after an explicit data export. The full SQLite rehearsal confirmed that downgrade removes only platform tables and preserves the pre-existing `biblical_texts` table.

For staging, redeploy the last known-good API and web commit SHA as a pair through the same protected deployment hook. Do not use mutable tags such as `latest`. Recheck `/api/v1/health`, `/api/v1/health/providers`, and `/healthz` after rollback. If the failed release included an incompatible migration, keep the current database untouched, restore the verified pre-deploy backup into a new database, run the known-good migrations there, verify counts and health, and only then switch the connection.

## Provider operations

`/api/v1/health/providers` reports provider selection and configuration without credentials. Provider authentication failures, timeouts, unavailable models, and malformed responses are normalized. If generation is unavailable but verified evidence exists, the API returns an evidence-only state; it must not invent citations.

## Security and retention

- Refresh tokens are hashed, rotated, and revocable. Logout also revokes the server-side session checked by access-token authentication.
- Private notes/studies are owner-filtered inside database queries.
- Share links are immutable snapshots with private, unlisted, public, revoked, and deleted states.
- Audio accepts MP3/WAV/M4A only, with byte and duration caps. Temporary files are removed on success and failure.
- Logs redact authorization values, API/JWT secrets, and private content fields. Do not add raw study text or tokens to log messages.
- In-memory rate limits protect a single process. Multi-instance deployments should replace the limiter store with Redis or an equivalent shared atomic store.

## Incident diagnostics

Check, in order: health endpoints, migration revision, database connectivity/pool saturation, provider diagnostics, rate-limit responses and `Retry-After`, disk space in the upload temp directory, and recent redacted application errors. Revoke exposed sessions, rotate compromised secrets, and invalidate provider keys immediately. Never paste raw tokens, uploaded sermon content, or private studies into tickets.

## Release handoff — 2026-08-11

Tested application commit: `09d4e26`.

- Backend: 1,227 passed, 1 skipped. The skip is intentional and remains reported by the suite.
- Frontend: 30 test files and 423 tests passed; lint was clean; the production build completed with 109 modules.
- Browser matrix: 146 applicable journeys passed, 94 project/viewport-inapplicable cases were skipped, and none failed. The matrix used an isolated real API, a unique temporary SQLite database removed at shutdown, and the production frontend preview across desktop, tablet, 390px mobile, and 320px mobile projects.
- Composite audit: the committed report matched byte-for-byte at SHA-256 `ad65d87df85eab6ccaa9b0718baf478737d22ac1e0932d67af596caa1cc07f47`. It records 83 works (82 ETHIO81 and 1 supplemental), 1,520 chapters, 38,938 verses, 48 declared gaps, and no undeclared gaps.
- Independent specification and code-quality reviews approved the final verification harness and accessibility fixes.

This is a local verification handoff, not public-launch approval. Docker was unavailable on the verification host, so Compose validation, image builds, and a live PostgreSQL backup/restore rehearsal remain blocked. No hosted staging provider, private HTTPS URL, credentials, monitoring owner, or rollback artifact has been selected, so deployment and live health checks remain blocked. The required real usability sessions with one participant aged 13–17 and one aged 65+ also remain incomplete. Keep staging private and public traffic disabled until every blocked checklist row has named evidence and sign-off.

## Verification record — 2026-07-12

- Empty database upgraded through `0006_platform_integrity` successfully.
- PostgreSQL offline SQL generation succeeded for the identity migration.
- Production-like SQLite rehearsal preserved 1/1 pre-existing biblical-text rows across upgrade and full downgrade; all platform tables were removed on downgrade.
- Backend suite: 39 tests passed with no warnings.
- Frontend suite: 22 tests, lint, and production build passed.
- Browser suite: 10 applicable journeys passed across desktop Chromium and 390px Chromium; 2 device-inapplicable checks were skipped.
- 390px coverage includes account/study/share, search, community, and no-overflow journeys; hardware-Tab focus is intentionally tested on desktop because touch emulation does not expose it.
- `npm audit`: 0 known vulnerabilities after compatible dependency updates.
