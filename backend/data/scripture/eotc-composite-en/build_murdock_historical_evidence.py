#!/usr/bin/env python3
"""Build or check the locked Murdock historical-sampling evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile


SOURCE_DIRECTORY = Path(__file__).resolve().parent
BACKEND_DIRECTORY = SOURCE_DIRECTORY.parents[2]
if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.library.verification.adapters.murdock_sword import (  # noqa: E402
    HISTORICAL_EVIDENCE_FILENAME,
    write_historical_evidence_pair,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = SOURCE_DIRECTORY / "verification/reports"
    if not args.check:
        write_historical_evidence_pair(SOURCE_DIRECTORY / "verification", output)
        return 0
    with tempfile.TemporaryDirectory() as temporary:
        generated = Path(temporary)
        write_historical_evidence_pair(SOURCE_DIRECTORY / "verification", generated)
        stem = HISTORICAL_EVIDENCE_FILENAME.removesuffix(".json")
        for suffix in (".json", ".md"):
            expected = output / f"{stem}{suffix}"
            actual = generated / f"{stem}{suffix}"
            if not expected.is_file() or expected.read_bytes() != actual.read_bytes():
                raise SystemExit(f"stale Murdock historical evidence: {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
