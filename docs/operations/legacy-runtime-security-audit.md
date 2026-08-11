# Legacy runtime security audit

## Decision

The supported runtime is the modular FastAPI application at
`backend/app/application.py`. Production and staging must launch
`app.application:app`, use an explicitly configured PostgreSQL database, and
use the configured modular authentication service. The retired launchers remain
in the repository only for compatibility tests and migration/reference work;
they are not deployment entry points.

Repository-local SQLite fallback patches for the retired runtimes are rejected.
A missing `DATABASE_URL` must stop those modules at import time instead of
silently opening `unbound_bible.db` or `auth_forum.db`. A silent fallback could
start an apparently healthy process against the wrong data store, bypass the
release configuration checks, and contradict the production runbook.

## Runtime inventory

| Module or configuration | Classification | Security decision |
| --- | --- | --- |
| `backend/app/application.py` | Active and imported | Sole backend application factory and production ASGI target. |
| `backend/app/config.py` | Active and imported | Development and tests may use the documented SQLite default. Staging and production validation reject SQLite, weak/default JWT secrets, insecure public URLs, and unsafe CORS/provider settings. |
| `backend/app/database.py` | Active and imported | Builds the engine from validated `Settings`; its SQLite support is limited to allowed development/test configuration. |
| `backend/app/auth/` | Active and imported | Uses the one `Settings.jwt_secret_key`; there is no alternate guest or default signing path in the production launcher. |
| `.replit` and `backend/Dockerfile` | Active launch configuration | Both select `app.application:app`; neither selects `backend/main.py`. |
| `backend/main.py`, `backend/auth.py`, `backend/database.py` | Retired compatibility runtime | Not a production launch path. The database and JWT modules remain fail closed when their required environment values are missing. |
| `auth-forum-api/main.py`, `auth-forum-api/auth.py`, `auth-forum-api/database.py` | Retired standalone service | Replaced by the modular community and account routes. Its database and JWT modules remain fail closed and have no guest/default signing key. |
| `backend/alembic/`, explicit ingestion/migration commands, and `backend/tests/` | Migration or test-only | Explicit SQLite URLs are allowed for deterministic local migrations, import rehearsals, and isolated tests. Production migrations receive `DATABASE_URL` through the protected environment. |
| Older scripts that import top-level `database` | Legacy maintenance | Not imported by `app.application:app` and not approved as production launchers. Operators should prefer the modular CLI/runbook paths. |

The regression suite checks the production launch targets, verifies that the
modular application source does not import the retired top-level `main`, `auth`,
or `database` modules, and verifies both retired database modules against the
same fail-closed policy. It also proves the policy helper rejects a temporary
module containing `sqlite:///unbound_bible.db`.

## Authentication findings

Both retired authentication modules read `JWT_SECRET_KEY` explicitly and raise
when it is absent. The audit rejects guest-token behavior, an insecure default
key, or an alternate fallback key. The active modular runtime takes its signing
key from validated `Settings`; staging and production reject the development
default and secrets shorter than 32 characters.

## User-owned working-tree changes

This audit was developed in the isolated `release/readiness` worktree. The main
working tree contained user-owned changes and they were left untouched:

- newline-only end-of-file edits in `backend/auth.py` and
  `auth-forum-api/auth.py`; these do not change runtime behavior;
- proposed SQLite fallbacks in `backend/database.py` and
  `auth-forum-api/database.py`; these are deliberately not accepted because
  they violate the fail-closed decision above;
- SQLite compatibility work in `server/models/edition_metadata.py` and
  `server/models/integrate_edition_metadata.py`;
- an untracked `backend/app/library/__init__.py` package marker, which can be
  evaluated independently of this security decision; and
- untracked ingestion, migration, and translation-bias scripts, which remain
  outside this audit.

None of those main-working-tree files were reset, deleted, copied into this
branch, or included in the audit commit.

## Release rule

Keep the focused legacy-runtime regression test in the release gate. Any future
need for local legacy data must use an explicit test or migration command and an
explicit database URL; do not reintroduce an implicit repository database file.
