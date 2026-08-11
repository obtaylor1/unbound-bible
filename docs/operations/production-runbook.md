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
```

Staging uses the same fail-closed database, JWT, HTTPS, CORS, and provider checks as production. Use an OpenAI-compatible provider and `AI_API_KEY` instead of the explicit demo override when provider-backed features are under test. Limit access at the provider or TLS proxy; do not expose the database port.

From the repository root, validate configuration with `docker compose --env-file .env.staging -f compose.staging.yml config`, then start with `docker compose --env-file .env.staging -f compose.staging.yml up -d --build`. The API container applies Alembic migrations before Uvicorn starts. Readiness requires successful responses from `/api/v1/health`, `/api/v1/health/providers`, and the web container's `/healthz` endpoint.

## Continuous delivery to private staging

The Quality workflow runs backend tests, frontend unit tests, lint, production build, and Playwright before release review. Only a successful Quality workflow produced by a push to `main` in this same repository can start the package-writing staging build; pull requests, forks, and similarly named branches cannot trigger it. Staging builds the exact tested commit SHA, publishes API and web images, resolves each pushed manifest to an immutable digest reference (`repository@sha256:...`), and sends only those digest references to the provider. A tag that contains a commit SHA is traceable, but it is not itself immutable.

Configure a protected GitHub environment named `staging`, require reviewer approval, and add `STAGING_DEPLOY_HOOK_URL` as an environment secret. The hook must deploy the two exact digest references from the request body and report a non-success HTTP status if the provider rejects the release. The workflow never interprets a secret as shell code. Concurrency is serialized so only one staging release at a time can build, await approval, and deploy; later releases queue rather than canceling an approved release.

After deployment, record the commit SHA and immutable image digest references, confirm all three health endpoints, run the release-readiness browser journey against the private URL, and compare release-critical row counts. Do not open access when any check fails.

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

Use platform-native PostgreSQL snapshots plus a logical `pg_dump`. Encrypt backups, restrict access, and test restoration on a separate database. Restore into a new database, run migrations, smoke-test it, then switch the application connection; do not overwrite the only production copy.

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

## Verification record — 2026-07-12

- Empty database upgraded through `0006_platform_integrity` successfully.
- PostgreSQL offline SQL generation succeeded for the identity migration.
- Production-like SQLite rehearsal preserved 1/1 pre-existing biblical-text rows across upgrade and full downgrade; all platform tables were removed on downgrade.
- Backend suite: 39 tests passed with no warnings.
- Frontend suite: 22 tests, lint, and production build passed.
- Browser suite: 10 applicable journeys passed across desktop Chromium and 390px Chromium; 2 device-inapplicable checks were skipped.
- 390px coverage includes account/study/share, search, community, and no-overflow journeys; hardware-Tab focus is intentionally tested on desktop because touch emulation does not expose it.
- `npm audit`: 0 known vulnerabilities after compatible dependency updates.
