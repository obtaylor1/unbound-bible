#!/usr/bin/env python3
"""Retired legacy scripture importer; retained only for operator discoverability."""

import sys


NOTICE = """This legacy Ethiopian canon ingester is retired and performs no data operation.

Use `seed-canon` for the Ethiopian 81-book catalog only; it does not import verse text.
For scripture, Phase 3's reviewed manifest and installed adapter are unavailable.
Once they are available, use:
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
