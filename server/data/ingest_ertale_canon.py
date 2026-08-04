#!/usr/bin/env python3
"""Retired legacy scripture importer; retained only for operator discoverability."""

import sys


NOTICE = """This legacy direct Ertale ingester path is retired and performs no data operation.

The reviewed `ertale` adapter is planned for Phase 3 and unavailable today.
Once it is available, use the verified ingestion workflow:
  PYTHONPATH=backend python -m app.library.ingest.cli stage --manifest <reviewed-manifest>
  PYTHONPATH=backend python -m app.library.ingest.cli validate --run-id <run-id>
  PYTHONPATH=backend python -m app.library.ingest.cli publish --run-id <run-id> --confirm

Do not bypass stage, validation, or publish --confirm.
"""


def main():
    print(NOTICE, file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
