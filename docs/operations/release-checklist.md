# Public release checklist

Record evidence, date, owner, and status for every row. Use **Pending** for work not yet completed; never substitute assumptions for evidence.

| Gate | Command or evidence | Status | Owner / date |
| --- | --- | --- | --- |
| Backend tests | `python -m pytest backend/tests -q`: 1,227 passed, 1 skipped | Complete | Codex / 2026-08-11 |
| Frontend unit tests | `npm test -- --run`: 30 files, 423 tests passed | Complete | Codex / 2026-08-11 |
| Frontend lint | `npm run lint`: clean | Complete | Codex / 2026-08-11 |
| Frontend build | `npm run build`: 109 modules built | Complete | Codex / 2026-08-11 |
| Playwright release gate | Full five-project matrix: 146 passed, 94 project/viewport-inapplicable skips, 0 failed | Complete | Codex / 2026-08-11 |
| Composite data audit | `python -m app.library.audit`; committed report matched byte-for-byte, SHA-256 `ad65d87df85eab6ccaa9b0718baf478737d22ac1e0932d67af596caa1cc07f47` | Complete | Codex / 2026-08-11 |
| Exact tested application commit | `09d4e26` | Complete | Codex / 2026-08-11 |
| Exact scripture/data counts | EOTC composite English: 83 works, 1,520 chapters, 38,938 verses, 48 declared gaps, 0 undeclared gaps | Complete | Codex / 2026-08-11 |

## Content, safety, and product review

- [x] Source, license, attribution, provisional-status, and fallback-language review completed.
- [x] Composite edition and per-work provenance are understandable and do not overstate verification.
- [x] Auth, notes, bookmarks/highlights, commentary, AI citations, and error recovery are reviewed with automated evidence.
- [x] Mobile 390px and desktop 200% zoom journeys pass, including keyboard/modal behavior and automated accessibility findings.
- [x] Sign-in failure, network interruption, and unavailable-text recovery preserve a path back to available reading.

The automated accessibility result is not a substitute for the required human sessions below.

## Human public-launch blocker

Public launch is blocked until at least one real participant aged 13–17 (with guardian or responsible-organization consent) and at least one real participant aged 65+ have completed the usability protocol. Severity 1 findings must be resolved. Severity 2 findings must be resolved or explicitly accepted by a named owner with rationale and date.

| Required human evidence | Status | Evidence / owner |
| --- | --- | --- |
| Age 13–17 session with consent | Pending |  |
| Age 65+ session | Pending |  |
| Severity 1 resolved; Severity 2 resolved or owner-accepted | Pending |  |

## Staging and recovery

| Operational check | Status | Evidence / owner |
| --- | --- | --- |
| Staging provider confirmed | Blocked | No hosted provider or private URL selected; release owner required |
| Compose validation and image builds | Blocked | Docker is not installed on the verification host (`docker: command not found`) |
| Staging HTTPS and health endpoints checked | Blocked | Requires the selected private staging deployment |
| Rollback command, prior artifact, and decision owner confirmed | Blocked | Procedure is documented; provider artifact and named owner still required |
| Backup configuration reviewed | Complete (local) | Fail-closed scripts and focused tests reviewed / Codex, 2026-08-11 |
| Backup restoration rehearsal completed | Blocked | Requires Docker and a live disposable PostgreSQL staging database |
| Monitoring, logs, and incident contact verified | Blocked | Requires the selected provider and named operator |

## Sign-off

- [ ] Remove the temporary `require_admin` compatibility alias only after every call site has migrated to `require_administrator` in a future release.

| Role | Name | Decision (approve / block) | Date | Notes |
| --- | --- | --- | --- | --- |
| Engineering |  |  |  |  |
| Content / source review |  |  |  |  |
| Accessibility / QA |  |  |  |  |
| Operations |  |  |  |  |
| Release owner |  |  |  |  |
