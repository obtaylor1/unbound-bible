#!/usr/bin/env python3
"""Retired legacy scripture writer; retained only for operator discoverability."""

import sys


NOTICE = """This direct Adam and Eve embedding writer is retired and performs no data operation.

Published scripture rows are immutable outside the verified publisher. The reviewed manifest and
installed adapter are unavailable. Run from the backend directory:
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
