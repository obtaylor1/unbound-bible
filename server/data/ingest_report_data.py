#!/usr/bin/env python3
"""Retired legacy scripture importer; retained only for operator discoverability."""

import sys


NOTICE = """This legacy report ingester is retired and performs no data operation.

It mixed non-scripture auxiliary report data with unsafe Ethiopian placeholders.
No matching scripture manifest or adapter is available; it is unavailable and must be split into a
separately reviewed migration. Ethiopian scripture uses the Phase 3 safe CLI:
  PYTHONPATH=backend python -m app.library.ingest.cli stage --manifest <reviewed-manifest>
  PYTHONPATH=backend python -m app.library.ingest.cli validate --run-id <run-id>
  PYTHONPATH=backend python -m app.library.ingest.cli publish --run-id <run-id> --confirm

Do not bypass stage, validation, or publish --confirm.
"""


def main() -> int:
    print(NOTICE, file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
