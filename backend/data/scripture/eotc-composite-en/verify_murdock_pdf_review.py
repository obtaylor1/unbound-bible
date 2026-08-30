#!/usr/bin/env python3
"""Reproduce the locked Murdock PDF review crop hashes and selection math."""
from __future__ import annotations
import argparse, difflib, json, math, resource, shutil, subprocess, sys, tempfile
from hashlib import sha256
from pathlib import Path

SOURCE_DIRECTORY = Path(__file__).resolve().parent
BACKEND_DIRECTORY = SOURCE_DIRECTORY.parents[2]
if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIRECTORY))
from app.library.verification.adapters.murdock_sword import (  # noqa: E402
    VISUAL_REVIEW_FILENAME, VISUAL_REVIEW_SHA256, _ocr_leaf_records,
    _secure_read, _tokens, build_historical_evidence,
)

PDF_SHA256 = "be4d1425fe69b4ff24fa418e15a2a2fbfb924db50d7e06861a937cfd3c81bc05"
RENDER_WIDTH, RENDER_HEIGHT = 1275, 1650
PDF_600DPI_WIDTH, PDF_600DPI_HEIGHT = 5100, 6600
EXPECTED_RGB_BYTES = RENDER_WIDTH * RENDER_HEIGHT * 3
PPM_HEADER = b"P6\n1275 1650\n255\n"
MAX_PPM_BYTES = len(PPM_HEADER) + EXPECTED_RGB_BYTES
MAX_LOG_BYTES = 64 * 1024
RENDER_TIMEOUT_SECONDS, VERSION_TIMEOUT_SECONDS = 30, 5
_BOUNDARY_LEAVES = {
    ("2-thessalonians", "beginning", 1, 8): (428, 429),
    ("james", "end", 5, 3): (470, 471),
    ("2-peter", "beginning", 1, 11): (479,),
}

def _child_file_limit(limit: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
    return apply

def _run_checked(command: list[str], *, timeout_seconds: int, file_limit: int = MAX_LOG_BYTES) -> bytes:
    """Run a renderer command with time/file limits and bounded logs."""
    with tempfile.TemporaryFile() as log:
        try:
            result = subprocess.run(
                command, check=False, stdout=log, stderr=log,
                timeout=timeout_seconds, preexec_fn=_child_file_limit(file_limit),
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError("Murdock review renderer timed out") from error
        log.seek(0, 2)
        if log.tell() > MAX_LOG_BYTES:
            raise ValueError("Murdock review renderer log exceeded its limit")
        log.seek(0)
        output = log.read(MAX_LOG_BYTES + 1)
    if result.returncode:
        raise ValueError("Murdock review renderer failed: " + output.decode("utf-8", "replace"))
    return output

def _ppm(path: Path) -> tuple[int, int, bytes]:
    if path.lstat().st_size > MAX_PPM_BYTES:
        raise ValueError("review renderer PPM size exceeds its limit")
    raw = _secure_read(path, maximum=MAX_PPM_BYTES, context="Murdock review PPM")
    if len(raw) != MAX_PPM_BYTES or not raw.startswith(PPM_HEADER):
        raise ValueError("review renderer did not produce canonical 1275x1650 RGB PPM")
    return RENDER_WIDTH, RENDER_HEIGHT, raw[len(PPM_HEADER):]

def _crop_hash(width: int, height: int, pixels: bytes, bbox: list[int]) -> str:
    x1, y1, x2, y2 = bbox
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("review crop is outside the rendered PDF page")
    digest = sha256()
    for y in range(y1, y2):
        start = (y * width + x1) * 3
        digest.update(pixels[start:start + (x2 - x1) * 3])
    return digest.hexdigest()

def _derive_crop(source_text: str, canvas: tuple[int, int], records) -> dict[str, object]:
    source_tokens = _tokens(source_text)
    blocks = difflib.SequenceMatcher(
        None, source_tokens, tuple(token for token, _ in records), autojunk=False,
    ).get_matching_blocks()
    longest = max(blocks, key=lambda block: block.size)
    if longest.size < 3:
        raise ValueError("Murdock review crop has no stable OCR anchor")
    token_margin = len(source_tokens) + 8
    first = max(0, longest.b - token_margin)
    last = min(len(records), longest.b + longest.size + token_margin)
    coords = [record[1] for record in records[first:last]]
    ocr_bbox = [
        min(item[0] for item in coords), min(min(item[1], item[3]) for item in coords),
        max(item[2] for item in coords), max(max(item[1], item[3]) for item in coords),
    ]
    if PDF_600DPI_WIDTH != RENDER_WIDTH * 4 or PDF_600DPI_HEIGHT != RENDER_HEIGHT * 4:
        raise ValueError("Murdock review canvas scale is invalid")
    # First normalize each OCR box to the declared 600-DPI-equivalent canvas,
    # then apply the exact 4:1 review-render scale.
    scale_x = (PDF_600DPI_WIDTH / canvas[0]) / 4
    scale_y = (PDF_600DPI_HEIGHT / canvas[1]) / 4
    render_bbox = [
        max(0, math.floor(ocr_bbox[0] * scale_x) - 24),
        max(0, math.floor(ocr_bbox[1] * scale_y) - 24),
        min(RENDER_WIDTH, math.ceil(ocr_bbox[2] * scale_x) + 24),
        min(RENDER_HEIGHT, math.ceil(ocr_bbox[3] * scale_y) + 24),
    ]
    return {
        "ocr_token_start": first, "ocr_token_end": last,
        "anchor_source_start": longest.a, "anchor_page_start": longest.b,
        "anchor_size": longest.size, "ocr_canvas": list(canvas),
        "pdf_600dpi_canvas": [PDF_600DPI_WIDTH, PDF_600DPI_HEIGHT],
        "render_canvas": [RENDER_WIDTH, RENDER_HEIGHT],
        "token_margin": token_margin, "pixel_margin": 24,
        "ocr_bbox": ocr_bbox, "render_bbox": render_bbox,
    }

def _validate_crop_evidence(crop: dict[str, object], derived: dict[str, object]) -> None:
    if any(crop.get(field) != value for field, value in derived.items()):
        raise ValueError("Murdock review crop selection evidence changed")

def verify(renderer: Path) -> int:
    version = _run_checked([str(renderer), "-v"], timeout_seconds=VERSION_TIMEOUT_SECONDS)
    if b"pdftoppm version 26.05.0" not in version:
        raise ValueError("Murdock review requires the recorded Poppler 26.05.0 renderer")
    verification = SOURCE_DIRECTORY / "verification"
    evidence = build_historical_evidence(verification)
    pdf = _secure_read(verification / "artifacts/syriacnewtestam00murdgoog.pdf", maximum=16_716_405, context="Murdock visual review PDF")
    review = _secure_read(verification / "reports" / VISUAL_REVIEW_FILENAME, maximum=1024 * 1024, context="Murdock PDF visual review")
    if sha256(pdf).hexdigest() != PDF_SHA256 or sha256(review).hexdigest() != VISUAL_REVIEW_SHA256:
        raise ValueError("Murdock PDF review inputs changed")
    payload = json.loads(review)
    samples = {
        (item["work_id"], item["phase"], item["chapter"], item["verse"]): item
        for item in evidence["samples"] if item["result"] in {"confirmed_visual", "confirmed_formatting"}
    }
    xml = _secure_read(verification / "artifacts/syriacnewtestam00murdgoog_djvu.xml", maximum=20_240_247, context="Murdock page OCR")
    leaves = _ocr_leaf_records(xml)
    crops_by_page = {}
    for reviewed in payload["samples"]:
        key = (reviewed["work_id"], reviewed["phase"], reviewed["chapter"], reviewed["verse"])
        sample = samples[key]
        expected_leaves = _BOUNDARY_LEAVES.get(key, (sample["scan_leaf"],))
        if tuple(crop["leaf"] for crop in reviewed["crops"]) != expected_leaves:
            raise ValueError("Murdock review crop leaf selection changed")
        for crop in reviewed["crops"]:
            canvas, records = leaves[crop["leaf"]]
            derived = _derive_crop(sample["electronic_text"], canvas, records)
            _validate_crop_evidence(crop, derived)
            crops_by_page.setdefault(crop["pdf_page"], []).append(crop)
    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        snapshot = temporary_path / "source.pdf"
        snapshot.write_bytes(pdf)
        for page, crops in sorted(crops_by_page.items()):
            prefix = temporary_path / f"page-{page:04d}"
            _run_checked([
                str(renderer), "-f", str(page), "-l", str(page),
                "-scale-to-x", str(RENDER_WIDTH), "-scale-to-y", str(RENDER_HEIGHT),
                "-singlefile", str(snapshot), str(prefix),
            ], timeout_seconds=RENDER_TIMEOUT_SECONDS, file_limit=MAX_PPM_BYTES)
            width, height, pixels = _ppm(prefix.with_suffix(".ppm"))
            for crop in crops:
                if _crop_hash(width, height, pixels, crop["render_bbox"]) != crop["crop_rgb_sha256"]:
                    raise ValueError(f"Murdock PDF review crop changed on page {page}")
    return len(payload["samples"])

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdftoppm", type=Path)
    args = parser.parse_args()
    renderer = args.pdftoppm or (Path(found) if (found := shutil.which("pdftoppm")) else None)
    if renderer is None:
        raise SystemExit("pdftoppm is required to reproduce the Murdock PDF review")
    print(f"verified {verify(renderer)} locked Murdock PDF visual-review samples")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
