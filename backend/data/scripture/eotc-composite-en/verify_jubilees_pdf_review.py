#!/usr/bin/env python3
"""Reproduce every locked R. H. Charles Jubilees visual-review crop hash."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile

SOURCE_DIRECTORY = Path(__file__).resolve().parent
BACKEND_DIRECTORY = SOURCE_DIRECTORY.parents[2]
if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.library.verification.adapters.charles_jubilees import (  # noqa: E402
    VISUAL_REVIEW_FILENAME,
    VISUAL_REVIEW_SHA256,
    _load_visual_review,
    _secure_read,
)

PDF_SHA256 = "bf8b2578e258b2798ca5ee89b9083b7733e5ed89dc4c338473df685913ad7203"
RENDER_WIDTH, RENDER_HEIGHT = 1275, 1650
PPM_HEADER = b"P6\n1275 1650\n255\n"
EXPECTED_RGB_BYTES = RENDER_WIDTH * RENDER_HEIGHT * 3
MAX_PPM_BYTES = len(PPM_HEADER) + EXPECTED_RGB_BYTES
MAX_LOG_BYTES = 64 * 1024
PDF_MAX_BYTES = 22_516_657
RENDER_TIMEOUT_SECONDS, VERSION_TIMEOUT_SECONDS, INFO_TIMEOUT_SECONDS = 30, 5, 5
EXPECTED_PDF_PAGES = 380
EXPECTED_CROPS = 18
MAX_RENDERED_PAGES = 18


def _child_file_limit(limit: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
    return apply


def _run_checked(
    command: list[str], *, timeout_seconds: int, file_limit: int = MAX_LOG_BYTES,
) -> bytes:
    """Run a locked renderer command with bounded time, files, and logs."""
    with tempfile.TemporaryFile() as log:
        try:
            result = subprocess.run(
                command, check=False, stdout=log, stderr=log,
                timeout=timeout_seconds, preexec_fn=_child_file_limit(file_limit),
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError("Jubilees review renderer timed out") from error
        log.seek(0, 2)
        if log.tell() > MAX_LOG_BYTES:
            raise ValueError("Jubilees review renderer log exceeded its limit")
        log.seek(0)
        output = log.read(MAX_LOG_BYTES + 1)
    if result.returncode:
        raise ValueError(
            "Jubilees review renderer failed: " + output.decode("utf-8", "replace")
        )
    return output


def _ppm(path: Path) -> tuple[int, int, bytes]:
    try:
        size = path.lstat().st_size
    except OSError as error:
        raise ValueError("Jubilees review renderer PPM is missing") from error
    if size > MAX_PPM_BYTES:
        raise ValueError("Jubilees review renderer PPM size exceeds its limit")
    raw = _secure_read(path, maximum=MAX_PPM_BYTES, context="Jubilees review PPM")
    if len(raw) != MAX_PPM_BYTES or not raw.startswith(PPM_HEADER):
        raise ValueError("Jubilees renderer did not produce canonical 1275x1650 RGB PPM")
    return RENDER_WIDTH, RENDER_HEIGHT, raw[len(PPM_HEADER):]


def _crop_hash(width: int, height: int, pixels: bytes, bbox: list[int]) -> str:
    if (
        type(bbox) is not list or len(bbox) != 4
        or any(type(value) is not int for value in bbox)
    ):
        raise ValueError("Jubilees review crop bounds are invalid")
    x1, y1, x2, y2 = bbox
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("Jubilees review crop is outside the rendered PDF page")
    digest = sha256()
    for y in range(y1, y2):
        start = (y * width + x1) * 3
        digest.update(pixels[start:start + (x2 - x1) * 3])
    return digest.hexdigest()


def _all_crops(review: dict[str, object]) -> list[dict[str, object]]:
    crops = [record["visual_review"] for record in review["samples"]]
    crops.extend(record["visual_review"] for record in review["marker_repairs"])
    crops.extend(review["chapter_27_recovery"]["crops"])
    if len(crops) != EXPECTED_CROPS:
        raise ValueError("Jubilees visual-review crop inventory changed")
    return crops


def verify(renderer: Path) -> int:
    renderer = Path(renderer)
    version = _run_checked(
        [str(renderer), "-v"], timeout_seconds=VERSION_TIMEOUT_SECONDS,
    )
    if b"pdftoppm version 26.05.0" not in version:
        raise ValueError("Jubilees review requires the recorded Poppler 26.05.0 renderer")
    pdfinfo = renderer.with_name("pdfinfo")
    if not pdfinfo.is_file():
        raise ValueError("Jubilees review requires pdfinfo beside the pinned renderer")

    verification = SOURCE_DIRECTORY / "verification"
    review, review_sha256 = _load_visual_review(verification)
    review_path = verification / "reports" / VISUAL_REVIEW_FILENAME
    review_snapshot = _secure_read(
        review_path, maximum=64 * 1024, context="Jubilees visual review",
    )
    if review_sha256 != VISUAL_REVIEW_SHA256 or json.loads(review_snapshot) != review:
        raise ValueError("Jubilees visual-review record changed")
    pdf = _secure_read(
        verification / "artifacts/bookofjubileesor00char.pdf",
        maximum=PDF_MAX_BYTES, context="Jubilees scan authority PDF",
    )
    if len(pdf) != PDF_MAX_BYTES or sha256(pdf).hexdigest() != PDF_SHA256:
        raise ValueError("Jubilees scan authority PDF changed")
    crops = _all_crops(review)
    pages = sorted({crop["pdf_page"] for crop in crops})
    if not pages or len(pages) > MAX_RENDERED_PAGES:
        raise ValueError("Jubilees review rendered-page bound exceeded")

    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        snapshot = temporary_path / "source.pdf"
        snapshot.write_bytes(pdf)
        info = _run_checked(
            [str(pdfinfo), str(snapshot)], timeout_seconds=INFO_TIMEOUT_SECONDS,
        )
        page_lines = [line for line in info.splitlines() if line.startswith(b"Pages:")]
        if page_lines != [b"Pages:           380"] or review["pdf_pages"] != EXPECTED_PDF_PAGES:
            raise ValueError("Jubilees review PDF page count changed")
        for page in pages:
            prefix = temporary_path / f"page-{page:04d}"
            _run_checked(
                [
                    str(renderer), "-f", str(page), "-l", str(page),
                    "-scale-to-x", str(RENDER_WIDTH), "-scale-to-y", str(RENDER_HEIGHT),
                    "-singlefile", str(snapshot), str(prefix),
                ],
                timeout_seconds=RENDER_TIMEOUT_SECONDS,
                file_limit=MAX_PPM_BYTES,
            )
            width, height, pixels = _ppm(prefix.with_suffix(".ppm"))
            for crop in (item for item in crops if item["pdf_page"] == page):
                if _crop_hash(width, height, pixels, crop["render_bbox"]) != crop["crop_rgb_sha256"]:
                    raise ValueError(f"Jubilees PDF review crop changed on page {page}")
    return len(crops)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdftoppm", type=Path)
    args = parser.parse_args()
    renderer = args.pdftoppm or (
        Path(found) if (found := shutil.which("pdftoppm")) else None
    )
    if renderer is None:
        raise SystemExit("pdftoppm is required to reproduce the Jubilees PDF review")
    print(f"verified {verify(renderer)} locked Jubilees PDF visual-review crops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
