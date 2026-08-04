#!/usr/bin/env python3
"""Retired legacy scripture importer; retained only for operator discoverability."""

import sys


NOTICE = """This legacy Ertale scripture ingester is retired and performs no data operation.

Adapter `ertale` is retired. No reviewed Ertale manifest ships until Phase 3; it is unavailable.
Once it is available, use the verified ingestion workflow:
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
