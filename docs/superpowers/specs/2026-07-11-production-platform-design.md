# The Unbound Bible Production Platform Design

## Purpose

Turn the current research-grade prototype into a reliable production application by replacing implicit demos and disconnected services with unified identity, durable persistence, provider-independent AI, trustworthy citations, working sharing, global search, notifications, and complete end-to-end verification.

The product remains accessible to everyday readers while supporting pastors, students, and academic researchers. Its defining qualities remain historical context, original-language study, diverse canons, transparent provenance, and decolonial analysis without imposing a single doctrinal conclusion.

## Scope

This design covers seven coordinated workstreams:

1. Consolidated backend and unified identity.
2. Provider-independent AI and reference-aware retrieval.
3. Durable notes, studies, and sharing.
4. Global search and notifications.
5. Community and external sharing integration.
6. Production-safe configuration and data migration.
7. Automated backend, frontend, and browser verification.

These workstreams will be delivered as independently testable phases. Each phase must leave the application working and deployable; later phases cannot depend on unverified partial migrations.

## Architecture

### Consolidated FastAPI application

The main FastAPI application becomes the only public backend. The separate forum/authentication API is migrated into modules inside the main backend. The browser communicates exclusively with `/api/v1`.

The backend is divided by domain rather than accumulated in `main.py`:

- `auth`: registration, login, refresh, logout, profile, and authorization.
- `community`: posts, comments, moderation, mentions, and activity.
- `studies`: sessions, messages, sources, notes, and saved work.
- `sharing`: snapshots, visibility, public pages, revocation, and external links.
- `search`: grouped, permission-aware search across all supported content.
- `notifications`: inbox, unread state, event creation, and preferences.
- `ai`: provider adapters, retrieval, citations, and response provenance.
- `scripture`: existing texts, canons, translations, geography, and lexical APIs.

Routers expose domain APIs while services contain business logic and repositories contain database queries. API schemas are separate from database models.

### Database

SQLite remains supported for local development. PostgreSQL is the documented production database. Alembic migrations replace automatic table creation and one-off production schema scripts.

The authoritative ownership graph starts at one `users` table. Existing forum users are migrated without changing their stable IDs where possible. The following records reference `users.id`:

- `user_notes`
- `study_sessions`
- `study_messages`
- `study_sources`
- `shared_studies`
- `notifications`
- `notification_preferences`
- `search_history`
- `forum_posts`
- `forum_comments`

Foreign keys, cascading behavior, visibility constraints, uniqueness rules, and indexes are defined in migrations and validated by integration tests.

## Unified identity and authorization

One account works across notes, saved studies, sharing, notifications, and community participation.

JWT access and refresh tokens remain the initial authentication mechanism. Required changes:

- Production requires a strong `JWT_SECRET_KEY`; insecure fallback secrets are development-only.
- Refresh sessions and revoked token identifiers are persisted in the database rather than process memory.
- Access tokens remain short-lived; refresh sessions can be individually revoked.
- Password hashes use the existing modern hashing configuration and can be upgraded on login.
- Authorization checks operate on stable user IDs, not email addresses.
- Resource-level policies enforce owner, moderator, visibility, and guest permissions.
- The frontend has one authentication provider that restores sessions, refreshes tokens, and clears invalid state.

Guest users may create local notes and studies. The interface labels these as local-only. After authentication, users can explicitly import local work; no silent destructive migration occurs.

## Provider-independent AI

### Provider contract

The AI domain defines separate interfaces for:

- chat completion
- embeddings
- audio transcription

Initial adapters support:

- OpenAI-compatible HTTP APIs
- Ollama/local models
- an explicit demonstration provider for local development

Chat, embeddings, and transcription providers can be configured independently. The rest of the application depends only on normalized domain responses.

### Provenance

Every AI operation records:

- provider and model
- live or demonstration mode
- retrieval query
- source record IDs
- source references shown to the user
- timestamps and request status

An answer can display “cited library sources” only when every shown citation maps to an actual database record. Demonstration output is never presented as live or verified.

### Reference-aware retrieval

The query pipeline first detects explicit biblical references and canonical context. Retrieval order is:

1. exact book/chapter/verse records
2. translation and original-language records for those references
3. linked historical, geographical, bias, and factbook records
4. semantic thematic results

The system validates that retrieved references match the question before generating an answer. If relevant evidence is unavailable, the response states that limitation instead of fabricating grounding.

## Studies, notes, and sharing

### Durable studies

Signed-in study sessions, messages, citations, notes, and analysis artifacts are persisted in the backend. The frontend uses optimistic updates only where conflict recovery is defined.

### Share snapshots

Sharing creates an immutable snapshot so later edits to the original session do not silently change what recipients saw. Owners can create a new version when desired.

Visibility modes:

- `private`: owner and explicitly authorized collaborators only.
- `unlisted`: accessible through an unguessable share identifier but excluded from search and public listings.
- `public`: accessible without authentication and eligible for public listings and search.

Owners can rename, duplicate, change visibility, revoke, and delete shares. Revoked shares return a clear unavailable state. Share identifiers are random, non-sequential, and stored as hashes when appropriate.

### External and community sharing

- Copy Link copies the persisted share URL.
- Email opens a correctly encoded `mailto:` link.
- WhatsApp opens a correctly encoded share intent URL.
- Share to Community requires confirmation, then creates a forum post linked to the persisted share.

No sharing control is shown as functional unless its backend action or external intent is complete.

## Global search

One permission-aware endpoint searches:

- scripture and translations
- original-language and lexicon entries
- factbook and historical records
- biblical locations
- public community posts
- the current user’s notes and studies
- public shared studies

Results are grouped by content type with stable deep links. Private data is filtered in database queries, not removed after serialization. Search history is optional, user-owned, and clearable.

The navigation Search action opens a real search experience with keyboard navigation, recent searches, loading, empty, offline, and permission states.

## Notifications

The in-app notification system supports:

- replies to posts and comments
- mentions
- shared-study activity
- completed sermon analysis
- relevant system notices

Notifications store actor, recipient, event type, target, created time, read time, and deduplication key. The bell displays a real unread count and opens an inbox. Users can mark one or all items read and configure preferences.

Email delivery is an optional adapter. In-app notification behavior cannot depend on email configuration.

## Frontend behavior

The frontend uses one API client for authentication, retries, structured errors, and request cancellation. Domain services expose normalized data to components.

Sign In opens a real authentication dialog. An authenticated profile menu provides account settings, notification preferences, local-data import, and logout.

All data-backed screens implement consistent states:

- initial loading
- refreshing
- empty
- offline
- validation failure
- permission denied
- server failure with retry

Mock data is excluded from production paths. Demonstration mode requires explicit configuration and remains visibly labeled in every affected component.

## Migration strategy

1. Introduce Alembic against the current schema without deleting existing data.
2. Create unified identity and new domain tables.
3. Migrate forum users and activity into the consolidated database.
4. Add compatibility routes while the frontend transitions to `/api/v1`.
5. Migrate notes and studies where ownership can be identified.
6. Switch the frontend to the unified API.
7. Remove the separate forum service only after parity tests pass.

Every migration has a reversible downgrade where data loss is not inherent. Destructive cleanup requires a separately approved migration after production backups are verified.

## Security and production configuration

Production startup fails when:

- the JWT secret is missing or insecure
- the database URL is missing
- development CORS wildcards are enabled
- demo AI is selected without an explicit production override
- required encryption or public-base-URL settings are missing

Rate limits apply to login, registration, password recovery, AI generation, search, and public sharing. Uploaded sermon audio has size, type, duration, storage, and retention controls. Logs exclude tokens, passwords, private study contents, and raw provider credentials.

## Testing and acceptance criteria

### Backend

- Unit tests cover policies, provider normalization, citation validation, visibility, and notification generation.
- Database integration tests cover migrations, ownership, permissions, token sessions, sharing, search filtering, and community relationships.
- Contract tests verify every supported AI adapter returns the same normalized schema.

### Frontend

- Component tests cover authentication restoration, login, profile menus, local-data migration, search, notifications, notes, sharing, and all error states.
- Existing routing, navigation, AI provenance, and dialog tests remain green.

### Browser journeys

Automated browser verification covers:

1. register, verify session, refresh, and logout
2. ask a referenced Bible question and inspect real citations
3. save a note and study, reload, and recover both
4. create private, unlisted, and public shares
5. revoke a share and verify access disappears
6. use global search with private and public results
7. receive, read, and configure notifications
8. post and reply in Community with the same account
9. upload and complete sermon analysis
10. operate critical journeys using keyboard-only navigation and mobile viewport

The production-ready milestone requires all automated suites, lint, build, migrations, and browser journeys to pass with no console errors.

## Delivery phases

1. Foundation: modular backend, migrations, configuration, and unified identity.
2. Persistence: notes, studies, local-data import, and API client.
3. AI: provider contracts, reference-aware retrieval, and citation validation.
4. Sharing: snapshots, visibility, public routes, and external/community actions.
5. Discovery: global search and notifications.
6. Data replacement: remove production mock paths and seed authoritative records.
7. Hardening: rate limits, upload controls, observability, end-to-end tests, and retirement of the separate forum service.

Each phase ships independently with migrations, tests, documentation, and a rollback strategy.
