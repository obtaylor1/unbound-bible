#!/usr/bin/env python3
"""Retired legacy scripture importer; retained only for operator discoverability."""

import sys


NOTICE = """This legacy Ethiopian canon ingester is retired and performs no data operation.

Use `seed-canon` for the Ethiopian 81-book catalog only; it does not import verse text.
For scripture, Phase 3's reviewed manifest and installed adapter are unavailable.
Once they are available, follow the Phase 3 steps below.
Run from the backend directory:
  python -m app.library.ingest.cli seed-canon --database-url <migrated-database-url>
  python -m app.library.ingest.cli stage --manifest <reviewed-manifest> --database-url <migrated-database-url>
  python -m app.library.ingest.cli validate --run-id <run-id> --database-url <migrated-database-url>
  python -m app.library.ingest.cli publish --run-id <run-id> --confirm --database-url <migrated-database-url>

Do not bypass stage, validation, or publish --confirm.
An explicitly set DATABASE_URL is permitted instead of --database-url.
"""


def main():
    print(NOTICE, file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
