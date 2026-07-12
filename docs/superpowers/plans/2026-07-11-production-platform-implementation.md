# The Unbound Bible Production Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace prototype-only behavior with a unified, production-capable platform providing one account, durable studies, provider-independent AI, trustworthy citations, real sharing, global search, notifications, and complete verification.

**Architecture:** Consolidate authentication and community routes into the primary FastAPI application while keeping domain modules isolated behind routers, services, and repositories. Introduce Alembic migrations, a single ownership model, normalized AI provider adapters, and one authenticated frontend API client; migrate one phase at a time behind compatibility routes.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic, PostgreSQL/SQLite, JWT, React 19, Vite 7, Vitest, React Testing Library, pytest, HTTPX.

---

## Scope and sequencing

This master plan contains seven independently releasable phases. Do not begin a later phase until the earlier phase’s tests and migration checks pass. Do not delete the separate forum service until Phase 7 parity verification succeeds.

## Phase 1: Backend foundation and unified identity

### Task 1: Introduce backend application structure and test harness

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/application.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/api/router.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_application.py`
- Modify: `backend/main.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write the failing application-factory test**

```python
from fastapi.testclient import TestClient
from app.application import create_application


def test_application_exposes_versioned_health_endpoint(test_settings):
    client = TestClient(create_application(test_settings))
    response = client.get('/api/v1/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'healthy', 'service': 'unbound-bible'}
```

- [ ] **Step 2: Run the test and verify RED**

Run: `cd backend && pytest tests/test_application.py -q`

Expected: FAIL because `app.application` does not exist.

- [ ] **Step 3: Add typed settings with production validation**

```python
class Settings(BaseSettings):
    environment: Literal['development', 'test', 'production'] = 'development'
    database_url: str
    jwt_secret_key: SecretStr
    public_base_url: AnyHttpUrl = 'http://localhost:5001'
    cors_origins: list[str] = ['http://localhost:5001']
    ai_chat_provider: str = 'demo'
    ai_embedding_provider: str = 'demo'
    ai_transcription_provider: str = 'demo'

    @model_validator(mode='after')
    def validate_production(self):
        if self.environment == 'production' and len(self.jwt_secret_key.get_secret_value()) < 32:
            raise ValueError('Production JWT secret must contain at least 32 characters')
        if self.environment == 'production' and '*' in self.cors_origins:
            raise ValueError('Wildcard CORS is forbidden in production')
        return self
```

- [ ] **Step 4: Implement the application factory**

Create FastAPI in `create_application(settings)`, attach settings to app state, include the versioned router, and expose `/api/v1/health`. Change `backend/main.py` to export `app = create_application(get_settings())` while leaving legacy imports temporarily available.

- [ ] **Step 5: Add isolated test settings and database fixtures**

Use a temporary SQLite database per test, create transactions per test, and override database dependencies. Tests must never open `unbound_bible.db` or `auth_forum.db`.

- [ ] **Step 6: Run backend tests**

Run: `cd backend && pytest tests/test_application.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app backend/tests backend/main.py pyproject.toml
git commit -m "refactor: add modular backend application factory"
```

### Task 2: Add Alembic and unified user/session schema

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_unified_identity.py`
- Create: `backend/app/auth/models.py`
- Create: `backend/app/auth/schemas.py`
- Create: `backend/app/auth/repository.py`
- Create: `backend/tests/migrations/test_unified_identity.py`
- Modify: `backend/app/database.py`

- [ ] **Step 1: Write a failing migration test**

The test upgrades an empty database to `head` and asserts the existence of `users`, `auth_sessions`, and `revoked_tokens`, including unique indexes on normalized email and token identifier.

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/migrations/test_unified_identity.py -q`

Expected: FAIL because Alembic and the migration do not exist.

- [ ] **Step 3: Define identity models**

```python
class User(Base):
    __tablename__ = 'users'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str]
    role: Mapped[str] = mapped_column(String(20), default='member')
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
```

- [ ] **Step 4: Create reversible migrations**

The migration creates the new tables without deleting forum tables. The downgrade removes only newly created identity/session objects.

- [ ] **Step 5: Test SQLite and PostgreSQL SQL generation**

Run the migration test on SQLite and run `alembic upgrade head --sql` with the production URL dialect in CI.

- [ ] **Step 6: Verify GREEN**

Run: `cd backend && pytest tests/migrations/test_unified_identity.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic.ini backend/alembic backend/app/auth backend/tests/migrations
git commit -m "feat: add unified identity schema"
```

### Task 3: Implement unified authentication APIs

**Files:**
- Create: `backend/app/auth/router.py`
- Create: `backend/app/auth/service.py`
- Create: `backend/app/auth/security.py`
- Create: `backend/app/auth/dependencies.py`
- Create: `backend/tests/auth/test_auth_flow.py`
- Modify: `backend/app/api/router.py`

- [ ] **Step 1: Write failing end-to-end auth tests**

Cover registration, duplicate email, login, `/auth/me`, refresh rotation, logout, revoked refresh reuse, invalid password, and inactive account.

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/auth/test_auth_flow.py -q`

Expected: FAIL with missing routes.

- [ ] **Step 3: Implement token/session behavior**

Hash refresh tokens before storing them. Put stable `user_id`, `session_id`, token type, issued time, and expiry in tokens. Rotate refresh tokens atomically and revoke the previous session token.

- [ ] **Step 4: Implement APIs**

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
PUT  /api/v1/auth/profile
```

- [ ] **Step 5: Verify GREEN**

Run: `cd backend && pytest tests/auth/test_auth_flow.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth backend/app/api/router.py backend/tests/auth
git commit -m "feat: add unified authentication API"
```

## Phase 2: Durable notes and studies

### Task 4: Add owner-scoped note and study persistence

**Files:**
- Create: `backend/alembic/versions/0002_studies_and_notes.py`
- Create: `backend/app/studies/models.py`
- Create: `backend/app/studies/schemas.py`
- Create: `backend/app/studies/repository.py`
- Create: `backend/app/studies/service.py`
- Create: `backend/app/studies/router.py`
- Create: `backend/tests/studies/test_study_permissions.py`
- Modify: `backend/app/api/router.py`

- [ ] **Step 1: Write failing permission tests**

Create two users. Assert one user cannot read, update, or delete the other user’s notes or study sessions. Assert anonymous access receives 401.

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/studies/test_study_permissions.py -q`

Expected: FAIL with missing models/routes.

- [ ] **Step 3: Implement schema and migration**

Create `user_notes`, `study_sessions`, `study_messages`, and `study_sources`. Add indexes for owner/date and foreign keys with explicit cascade rules.

- [ ] **Step 4: Implement CRUD routes**

```text
GET/POST       /api/v1/notes
GET/PUT/DELETE /api/v1/notes/{note_id}
GET/POST       /api/v1/studies
GET/PUT/DELETE /api/v1/studies/{study_id}
POST           /api/v1/studies/{study_id}/messages
```

- [ ] **Step 5: Verify GREEN**

Run: `cd backend && pytest tests/studies/test_study_permissions.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/0002_studies_and_notes.py backend/app/studies backend/tests/studies backend/app/api/router.py
git commit -m "feat: persist user notes and studies"
```

### Task 5: Add authenticated frontend API client and account provider

**Files:**
- Create: `frontend/src/api/client.js`
- Create: `frontend/src/api/client.test.js`
- Create: `frontend/src/auth/AuthProvider.jsx`
- Create: `frontend/src/auth/AuthProvider.test.jsx`
- Create: `frontend/src/auth/AuthDialog.jsx`
- Create: `frontend/src/auth/AccountMenu.jsx`
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/src/components/Navigation.jsx`
- Modify: `frontend/src/components/SavedStudies.jsx`
- Modify: `frontend/src/components/StudyAssistantSidebar.jsx`

- [ ] **Step 1: Write failing token-refresh tests**

Assert one 401 triggers one refresh request, concurrent 401s share the refresh promise, the original request retries once, and failed refresh clears credentials without looping.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/api/client.test.js src/auth/AuthProvider.test.jsx`

Expected: FAIL because the client and provider do not exist.

- [ ] **Step 3: Implement the API client**

Expose `api.get/post/put/delete`. Store access tokens in memory and refresh credentials using the selected secure refresh strategy. Normalize errors to `{status, code, message, fieldErrors}` and support `AbortSignal`.

- [ ] **Step 4: Implement the authentication provider**

Expose `user`, `status`, `login`, `register`, `logout`, and `refresh`. Restore the user from `/auth/me` on app startup.

- [ ] **Step 5: Replace navigation placeholders**

Sign In opens `AuthDialog`. Signed-in state shows `AccountMenu` with profile, preferences, local-data import, and logout.

- [ ] **Step 6: Add explicit guest-data import**

Preview counts before import, require confirmation, upload records idempotently, and remove local copies only after server confirmation.

- [ ] **Step 7: Verify GREEN**

Run: `cd frontend && npm test -- --run src/api/client.test.js src/auth/AuthProvider.test.jsx`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api frontend/src/auth frontend/src/main.jsx frontend/src/components/Navigation.jsx frontend/src/components/SavedStudies.jsx frontend/src/components/StudyAssistantSidebar.jsx
git commit -m "feat: connect unified accounts and durable studies"
```

## Phase 3: Provider-independent AI and grounded retrieval

### Task 6: Implement AI provider interfaces and adapters

**Files:**
- Create: `backend/app/ai/contracts.py`
- Create: `backend/app/ai/providers/openai_compatible.py`
- Create: `backend/app/ai/providers/ollama.py`
- Create: `backend/app/ai/providers/demo.py`
- Create: `backend/app/ai/factory.py`
- Create: `backend/tests/ai/test_provider_contract.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Write a parameterized provider contract test**

```python
@pytest.mark.parametrize('provider_name', ['openai_compatible', 'ollama', 'demo'])
async def test_chat_providers_return_normalized_metadata(provider_name, provider_factory):
    provider = provider_factory(provider_name)
    result = await provider.complete([ChatMessage(role='user', content='Question')])
    assert result.provider == provider_name
    assert result.model
    assert result.content
    assert result.is_demo is (provider_name == 'demo')
```

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/ai/test_provider_contract.py -q`

Expected: FAIL because providers do not exist.

- [ ] **Step 3: Implement chat, embedding, and transcription protocols**

Keep provider SDK response objects inside adapters. Normalize timeouts, rate limits, authentication failures, unavailable models, and malformed responses.

- [ ] **Step 4: Add provider selection and startup diagnostics**

The factory selects configured adapters independently for chat, embeddings, and transcription. `/api/v1/health` reports provider readiness without exposing credentials.

- [ ] **Step 5: Verify GREEN**

Run: `cd backend && pytest tests/ai/test_provider_contract.py -q`

Expected: PASS using mocked HTTP transports for non-demo providers.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ai backend/app/config.py backend/tests/ai/test_provider_contract.py
git commit -m "feat: add provider-independent AI adapters"
```

### Task 7: Make retrieval reference-aware and citations verifiable

**Files:**
- Create: `backend/app/ai/references.py`
- Create: `backend/app/ai/retrieval.py`
- Create: `backend/app/ai/citations.py`
- Create: `backend/app/ai/router.py`
- Create: `backend/tests/ai/test_grounded_answer.py`
- Modify: `frontend/src/services/studyApi.js`
- Modify: `frontend/src/components/AskTheBible.jsx`

- [ ] **Step 1: Write failing grounding tests**

For “What does Genesis 1:1 say?”, assert all primary retrieval results reference Genesis 1:1 and every returned citation ID exists. Assert missing evidence produces `grounding_status='insufficient'` rather than fabricated citations.

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/ai/test_grounded_answer.py -q`

Expected: FAIL against the current broad semantic fallback.

- [ ] **Step 3: Implement reference parsing and constrained retrieval**

Parse canonical book aliases, chapter, verse, ranges, and optional translation. Retrieve exact references before linked and thematic sources.

- [ ] **Step 4: Validate citations before serialization**

Drop no citation silently. If a generated citation cannot resolve, mark the answer insufficient and record the validation failure for diagnostics.

- [ ] **Step 5: Replace the current chat route**

Return normalized fields: `answer`, `provider`, `model`, `is_demo`, `grounding_status`, `sources`, `follow_ups`, and `study_message_id`.

- [ ] **Step 6: Update frontend provenance rendering**

Use server metadata as authoritative; remove content-string detection once compatibility support is no longer needed.

- [ ] **Step 7: Run backend and frontend tests**

Run: `cd backend && pytest tests/ai/test_grounded_answer.py -q`

Run: `cd frontend && npm test -- --run src/services/studyApi.test.js`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/ai backend/tests/ai frontend/src/services/studyApi.js frontend/src/services/studyApi.test.js frontend/src/components/AskTheBible.jsx
git commit -m "fix: ground AI answers in verified references"
```

## Phase 4: Real sharing

### Task 8: Persist share snapshots and visibility policies

**Files:**
- Create: `backend/alembic/versions/0003_shared_studies.py`
- Create: `backend/app/sharing/models.py`
- Create: `backend/app/sharing/schemas.py`
- Create: `backend/app/sharing/policies.py`
- Create: `backend/app/sharing/service.py`
- Create: `backend/app/sharing/router.py`
- Create: `backend/tests/sharing/test_visibility.py`

- [ ] **Step 1: Write failing visibility tests**

Test owner access, non-owner denial for private shares, anonymous unlisted access by identifier, public listing inclusion, unlisted exclusion from listings, visibility changes, revocation, and deletion.

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/sharing/test_visibility.py -q`

Expected: FAIL with missing sharing domain.

- [ ] **Step 3: Implement immutable snapshots**

Store title, session type, message/source JSON snapshot, visibility, random public identifier hash, created time, revoked time, and owner ID. Updating a source study never mutates an existing snapshot.

- [ ] **Step 4: Implement sharing APIs**

```text
POST   /api/v1/shares
GET    /api/v1/shares/{share_id}
PATCH  /api/v1/shares/{share_id}
DELETE /api/v1/shares/{share_id}
POST   /api/v1/shares/{share_id}/revoke
POST   /api/v1/shares/{share_id}/duplicate
GET    /api/v1/shares/public
```

- [ ] **Step 5: Verify GREEN**

Run: `cd backend && pytest tests/sharing/test_visibility.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/0003_shared_studies.py backend/app/sharing backend/tests/sharing
git commit -m "feat: persist secure shared studies"
```

### Task 9: Connect frontend sharing and public study routes

**Files:**
- Modify: `frontend/src/components/ShareStudyModal.jsx`
- Modify: `frontend/src/components/ShareStudyModal.test.jsx`
- Create: `frontend/src/sharing/PublicStudyPage.jsx`
- Create: `frontend/src/sharing/PublicStudyPage.test.jsx`
- Create: `frontend/src/services/sharingApi.js`
- Modify: `frontend/src/routing/pageRoutes.js`

- [ ] **Step 1: Write failing persistence and intent tests**

Assert Copy Link waits for share creation, visibility changes call the API, email and WhatsApp links are correctly encoded, Community sharing requires confirmation, and revoked shares render an unavailable state.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/components/ShareStudyModal.test.jsx src/sharing/PublicStudyPage.test.jsx`

Expected: FAIL because sharing is still local-only.

- [ ] **Step 3: Implement sharing API calls and states**

Add creating, created, copying, error, and retry states. Never generate a client-only fake URL.

- [ ] **Step 4: Implement external intents**

Build `mailto:` and `https://wa.me/?text=` URLs with `URLSearchParams` or `encodeURIComponent`. Open them only after a persisted share exists.

- [ ] **Step 5: Implement public route**

Resolve `/share/{share_id}` outside authenticated navigation. Render citations, provenance, unavailable/revoked state, and owner-selected title without exposing private user data.

- [ ] **Step 6: Verify GREEN**

Run: `cd frontend && npm test -- --run src/components/ShareStudyModal.test.jsx src/sharing/PublicStudyPage.test.jsx`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ShareStudyModal.jsx frontend/src/components/ShareStudyModal.test.jsx frontend/src/sharing frontend/src/services/sharingApi.js frontend/src/routing/pageRoutes.js
git commit -m "feat: connect persistent study sharing"
```

## Phase 5: Search and notifications

### Task 10: Add permission-aware global search

**Files:**
- Create: `backend/app/search/schemas.py`
- Create: `backend/app/search/service.py`
- Create: `backend/app/search/router.py`
- Create: `backend/tests/search/test_search_permissions.py`
- Create: `frontend/src/search/SearchDialog.jsx`
- Create: `frontend/src/search/SearchDialog.test.jsx`
- Modify: `frontend/src/components/Navigation.jsx`

- [ ] **Step 1: Write failing backend permission tests**

Assert results group scripture, factbook, locations, community, public shares, and the current user’s private records. Assert other users’ private notes/studies never appear.

- [ ] **Step 2: Write failing frontend keyboard tests**

Assert Search opens from navigation and keyboard shortcut, arrows move through results, Enter navigates, Escape closes, and empty/offline states are announced.

- [ ] **Step 3: Verify RED**

Run: `cd backend && pytest tests/search/test_search_permissions.py -q`

Run: `cd frontend && npm test -- --run src/search/SearchDialog.test.jsx`

- [ ] **Step 4: Implement grouped backend search**

Use bounded per-type limits, normalized ranking, permission filters inside queries, and stable result URLs. Record optional user-owned history only when enabled.

- [ ] **Step 5: Implement the search dialog**

Debounce input, cancel stale requests, display grouped results and recent searches, and preserve query state across navigation when appropriate.

- [ ] **Step 6: Verify GREEN**

Run both focused test commands; expected PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/search backend/tests/search frontend/src/search frontend/src/components/Navigation.jsx
git commit -m "feat: add global permission-aware search"
```

### Task 11: Add notification inbox and event generation

**Files:**
- Create: `backend/alembic/versions/0004_notifications.py`
- Create: `backend/app/notifications/models.py`
- Create: `backend/app/notifications/service.py`
- Create: `backend/app/notifications/router.py`
- Create: `backend/tests/notifications/test_notification_events.py`
- Create: `frontend/src/notifications/NotificationInbox.jsx`
- Create: `frontend/src/notifications/NotificationInbox.test.jsx`
- Modify: `frontend/src/components/Navigation.jsx`

- [ ] **Step 1: Write failing event tests**

Test reply, mention, shared-study activity, sermon completion, deduplication, unread count, mark-one-read, mark-all-read, and preference suppression.

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/notifications/test_notification_events.py -q`

Expected: FAIL with missing notification domain.

- [ ] **Step 3: Implement notification storage and APIs**

Create actor/recipient/event/target fields, deduplication key, created/read timestamps, and preferences. Expose inbox, unread count, read actions, and preference routes.

- [ ] **Step 4: Implement frontend inbox**

Replace the placeholder bell with unread count, inbox popover/page, optimistic read actions with rollback, and settings link.

- [ ] **Step 5: Verify backend and frontend tests**

Run focused pytest and Vitest commands; expected PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/0004_notifications.py backend/app/notifications backend/tests/notifications frontend/src/notifications frontend/src/components/Navigation.jsx
git commit -m "feat: add in-app notifications"
```

## Phase 6: Community migration and production data paths

### Task 12: Migrate community into the unified backend

**Files:**
- Create: `backend/alembic/versions/0005_community_migration.py`
- Create: `backend/app/community/models.py`
- Create: `backend/app/community/router.py`
- Create: `backend/app/community/service.py`
- Create: `backend/tests/community/test_forum_parity.py`
- Modify: `frontend/src/components/ForumPage.jsx`
- Modify: `frontend/vite.config.js`

- [ ] **Step 1: Capture current forum behavior as parity tests**

Cover listing, creation, editing, deletion, comments, author permissions, moderator behavior, and absence of private emails in public responses.

- [ ] **Step 2: Verify tests fail against missing consolidated routes**

Run: `cd backend && pytest tests/community/test_forum_parity.py -q`

- [ ] **Step 3: Implement models, migration, and routes**

Migrate users first, then posts/comments with owner mappings. Preserve IDs where safe and emit a migration report for unmapped records.

- [ ] **Step 4: Switch the frontend to the unified API**

Remove the separate forum token state and use the app-wide authentication provider and `/api/v1/community` routes.

- [ ] **Step 5: Run parity and frontend tests**

Expected: PASS before changing deployment configuration.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/0005_community_migration.py backend/app/community backend/tests/community frontend/src/components/ForumPage.jsx frontend/vite.config.js
git commit -m "refactor: unify community with app accounts"
```

### Task 13: Remove production mock paths

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/ai/providers/demo.py`
- Modify: `frontend/src/data/mockData.js`
- Modify: components importing `MOCK_*`
- Create: `backend/tests/test_production_configuration.py`
- Create: `frontend/src/config/runtime.js`

- [ ] **Step 1: Write failing production configuration tests**

Assert production rejects insecure JWT secrets, wildcard CORS, missing database URL, and demo providers unless `ALLOW_PRODUCTION_DEMO=true` is explicitly set.

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/test_production_configuration.py -q`

- [ ] **Step 3: Route fixture data through explicit demo configuration**

Production components fetch real endpoints. Demo fixtures are imported only by demo adapters/screens through lazy imports and show a persistent Demo label.

- [ ] **Step 4: Add authoritative empty states**

When data is absent, show an honest empty state with ingestion/configuration guidance rather than silently substituting fixture records.

- [ ] **Step 5: Verify production build excludes fixture paths from initial bundles**

Run: `cd frontend && npm run build`

Inspect generated chunks and confirm mock data is not part of production route chunks unless explicit demo mode is enabled.

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/ai/providers/demo.py backend/tests/test_production_configuration.py frontend/src/config frontend/src/data frontend/src/components
git commit -m "fix: make demo data explicit and production-safe"
```

## Phase 7: Hardening and end-to-end verification

### Task 14: Add rate limits, upload controls, and safe logging

**Files:**
- Create: `backend/app/security/rate_limits.py`
- Create: `backend/app/security/uploads.py`
- Create: `backend/app/observability/logging.py`
- Create: `backend/tests/security/test_security_controls.py`
- Modify: authentication, search, AI, sharing, and sermon routers

- [ ] **Step 1: Write failing security tests**

Test login and AI rate limits, rejected oversized/invalid audio, upload cleanup, secret/token redaction, and private study-content redaction.

- [ ] **Step 2: Implement controls with configuration**

Use per-user/per-IP keys, structured error codes, bounded upload size/duration/type, temporary-file cleanup, retention configuration, and structured logs with redaction filters.

- [ ] **Step 3: Verify GREEN**

Run: `cd backend && pytest tests/security/test_security_controls.py -q`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/security backend/app/observability backend/tests/security backend/app
git commit -m "security: harden platform boundaries"
```

### Task 15: Add critical browser journeys and retire the forum service

**Files:**
- Create: `frontend/e2e/auth-study-sharing.spec.js`
- Create: `frontend/e2e/search-notifications-community.spec.js`
- Create: `frontend/e2e/sermon-mobile-accessibility.spec.js`
- Create: `docs/operations/production-runbook.md`
- Modify: `.replit`
- Remove only after parity: `auth-forum-api` runtime startup entry

- [ ] **Step 1: Automate the ten approved browser journeys**

Cover registration/refresh/logout, grounded AI citations, durable notes/studies, all visibility modes, revocation, global search permissions, notification read state, community activity, sermon analysis, keyboard use, and 390px mobile layout.

- [ ] **Step 2: Run complete backend verification**

Run: `cd backend && pytest -q`

Expected: all tests pass.

- [ ] **Step 3: Run complete frontend verification**

Run: `cd frontend && npm test -- --run && npm run lint && npm run build`

Expected: all commands exit 0 with no warnings.

- [ ] **Step 4: Run migrations against a production-like database copy**

Run upgrade, smoke tests, and downgrade rehearsal. Compare row counts and produce a migration report before changing service topology.

- [ ] **Step 5: Run browser journeys**

Expected: all critical journeys pass on desktop and 390px mobile with no console errors.

- [ ] **Step 6: Retire separate forum runtime**

Remove its startup entry only after parity tests, migration report, and rollback rehearsal succeed. Preserve source for one release window unless separately approved for deletion.

- [ ] **Step 7: Write the production runbook**

Document required settings, provider configuration, migrations, backup/restore, rollback, health checks, rate limits, upload retention, demo-mode safeguards, and incident diagnostics.

- [ ] **Step 8: Commit**

```bash
git add frontend/e2e docs/operations .replit
git commit -m "test: verify production platform end to end"
```

## Final acceptance gate

The platform is ready only when:

- Backend tests pass in SQLite and PostgreSQL CI jobs.
- Frontend tests, lint, and production build pass.
- Alembic upgrades succeed from the current production schema.
- Unified identity owns notes, studies, shares, notifications, and community records.
- AI adapters pass the shared contract and citations resolve to real records.
- Private data never appears in another user’s search, share, or community response.
- Private, unlisted, public, revoked, and deleted share states behave as specified.
- Demo mode is explicit and production startup is fail-closed.
- All critical browser journeys pass on desktop and mobile.
- Backup, migration, rollback, and provider-configuration procedures are documented and rehearsed.
