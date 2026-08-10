# Public release checklist

Record evidence, date, owner, and status for every row. Use **Pending** for work not yet completed; never substitute assumptions for evidence.

| Gate | Command or evidence | Status | Owner / date |
| --- | --- | --- | --- |
| Backend tests | `cd backend && pytest` | Pending |  |
| Frontend unit tests | `cd frontend && npm test -- --run` | Pending |  |
| Frontend lint | `cd frontend && npm run lint` | Pending |  |
| Frontend build | `cd frontend && npm run build` | Pending |  |
| Playwright release gate | `cd frontend && npx playwright test e2e/release-readiness.spec.js` | Pending |  |
| Composite data audit | Record audit command, report path, and reviewer | Pending |  |
| Exact release commit | SHA: __________ | Pending |  |
| Exact scripture/data counts | Dataset version and counts: __________ | Pending |  |

## Content, safety, and product review

- [ ] Source, license, attribution, provisional-status, and fallback-language review completed.
- [ ] Composite edition and per-work provenance are understandable and do not overstate verification.
- [ ] Auth, notes, bookmarks/highlights, commentary, AI citations, and error recovery are reviewed with evidence.
- [ ] Mobile 390px and desktop 200% zoom journeys pass, including keyboard/modal behavior and accessibility findings.
- [ ] Sign-in failure, network interruption, and unavailable-text recovery preserve a path back to available reading.

## Human public-launch blocker

Public launch is blocked until at least one real participant aged 13–17 (with guardian or responsible-organization consent) and at least one real participant aged 65+ have completed the usability protocol. Severity 1 and 2 findings must be resolved or explicitly accepted by a named owner with rationale and date.

| Required human evidence | Status | Evidence / owner |
| --- | --- | --- |
| Age 13–17 session with consent | Pending |  |
| Age 65+ session | Pending |  |
| Severity 1/2 findings resolved or owner-accepted | Pending |  |

## Staging and recovery

| Operational check | Status | Evidence / owner |
| --- | --- | --- |
| Staging provider confirmed | Pending |  |
| Staging HTTPS and health endpoint checked | Pending |  |
| Rollback command, prior artifact, and decision owner confirmed | Pending |  |
| Backup configuration reviewed | Pending |  |
| Backup restoration rehearsal completed | Pending |  |
| Monitoring, logs, and incident contact verified | Pending |  |

## Sign-off

| Role | Name | Decision (approve / block) | Date | Notes |
| --- | --- | --- | --- | --- |
| Engineering |  |  |  |  |
| Content / source review |  |  |  |  |
| Accessibility / QA |  |  |  |  |
| Operations |  |  |  |  |
| Release owner |  |  |  |  |
