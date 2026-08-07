# Local community migration report

Date: 2026-07-12

The checked local legacy database (`auth_forum.db`) contains the expected three source tables and no user content:

| Source table | Rows |
| --- | ---: |
| `auth_users` | 0 |
| `forum_posts` | 0 |
| `forum_comments` | 0 |

No local records require migration. This result does not authorize production cutover: operators must run the idempotent importer against the production legacy database, save its JSON report outside the repository, reconcile counts, and resolve every unmapped post or comment before retiring that service.
