# Ethiopian Canon Research Collection source

This directory registers the **Ethiopian Canon Research Collection**, a **mixed-source English research collection**. It is **not complete, official, uniform, or ecclesiastically authorized**. It is not one Ethiopian Orthodox translation and does not claim approval by an Ethiopian Orthodox church body.
It is not a complete English translation of the traditional Ethiopian Orthodox canon.

Source remediation covers exactly **39 WMB + 27 Murdock + 6 permanent KJV fallback + 1 Jubilees = 73** verified works. The other ten supplied works remain readable and honestly marked `in_progress` until their independent source reviews are complete.

## Reviewed scope

- 83 populated source works and 1,520 chapters
- 82 works mapped to the ETHIO81 library canon
- Prayer of Manasseh retained as one clearly marked supplemental work
- 38,487 publishable corrected verse rows
- 44,114 raw archive records are an audit count only; they include 5,252 exact duplicate excess records and 17 conflicting duplicate excess records

Thirteen ETHIO81 library works remain unavailable: Esther Greek Additions, Psalm 151, Tegsats, Paralipomena of Jeremiah, Josippon, Sirate Tsion, Tizaz, Gitsew, Abtilis, Metsihafe Kidan I, Metsihafe Kidan II, Qalementos, and Didesqelya.

## Frozen inputs and provenance

| Input | SHA-256 | Provenance and terms |
|---|---|---|
| `Ethiopian Orthodox Bible (Non-KJV Edition).zip` | `0f4bdff8e24ee7e67afbd939d68a8dc40c0f1cf27026066dbb9f92ce34b183a2` | Historical user-supplied input retained for reproducibility and pre-rebuild comparison; it is not the publication authority for the 73 verified remediation works |
| `engwmb_vpl.zip` | `02aef8d71addf7bf01438d1d132536f3d2cceb21820df6427015cddd608cfbf8` | [Official eBible World Messianic Bible VPL archive](https://ebible.org/find/show.php?id=engwmb), retrieved 2026-08-18; August 2022 stable text, dedicated to the public domain, with the World Messianic Bible trademark naming condition |
| `murdock-source.zip` | `4f0adeba385acbfa37921f66677d4aaf99e23b4e65ca162f122832689036641f` | [Official CrossWire Murdock SWORD module](https://crosswire.org/sword/modules/ModInfo.jsp?modName=Murdock), version 1.2, public domain, retrieved 2026-08-29 |
| `syriacnewtestam00murdgoog.djvu` | `8777ab6536ba7242e017b0aca426858c85fa791ba5d1ed601f93c069a5775f9e` | [1915 ninth edition](https://archive.org/details/syriacnewtestam00murdgoog), used as a historical witness to Murdock's translation first published in 1852 and never represented as an 1852 scan; the primary and its three OCR/leaf derivatives are locked to the same Internet Archive item |
| `syriacnewtestam00murdgoog.pdf` | `be4d1425fe69b4ff24fa418e15a2a2fbfb924db50d7e06861a937cfd3c81bc05` | [PDF derivative of the same 1915 ninth-edition Internet Archive item](https://archive.org/details/syriacnewtestam00murdgoog), locked for reproducible visual review of the exact predetermined samples that OCR could not confirm |
| `project-gutenberg-124.txt` | `83de0c18742ba22b3d442c3a5bc828fe9e91dff27ae3c298e9b5c9a6ecfbf4d4` | [Project Gutenberg eBook 124](https://www.gutenberg.org/ebooks/124), whose [UTF-8 text link](https://www.gutenberg.org/ebooks/124.txt.utf-8) resolves to the locked `pg124.txt`; 835,071-byte electronic KJV-family Apocrypha transcription credited to Robert Kraft, updated 2021-08-26, public domain in the USA, retrieved 2026-08-29 |
| `upenn-1611-great-he-iiif-manifest.json` and `upenn-1611-great-he-pages/p1143.jpg`–`p1158.jpg` | Exact per-artifact checksums in `verification/kjv-1611-historical-artifacts.lock.json` | [University of Pennsylvania Colenda 1611 Great HE editio princeps](https://colenda.library.upenn.edu/catalog/81431-p3rv0df45), Robert Barker, NoC-US; locked catalog, IIIF manifest, and native page images used as historical authority |
| `eng-webbe_vpl.zip` | `dc16460ed5e890e7b169cd3caeaa7e4adb4f7a6b5031bff85e4503389cd03b11` | [Official World English Bible British Edition with Deuterocanon](https://ebible.org/details.php?id=eng-webbe), public domain |
| `project-gutenberg-77935.txt` | `10d325355a810badf67bbbd1fe6bda77dc6e294eae78c2f6c69290188af45b14` | [R. H. Charles, *The Book of Enoch* (1917), ebook 77935](https://www.gutenberg.org/ebooks/77935), public domain in the USA |
| `rh-charles-jubilees-1917-authorized-reprint.html` | `e48d840d060a64cfdee1c7cec640770fdf1c3f2daf76c84383163ce9126dd54a` | [Authorized 1917 reprint transcription](https://www.globalgreyebooks.com/online-ebooks/r-h-charles_book-of-jubilees_complete-text.html) of R. H. Charles's translation published in 1902; public domain in the USA |
| `bookofjubileesor00char.pdf` | `bf8b2578e258b2798ca5ee89b9083b7733e5ed89dc4c338473df685913ad7203` | [Original 1902 A. and C. Black scan](https://archive.org/details/bookofjubileesor00char), locked as edition and numbering authority with catalog, OCR, coordinate, and page-map derivatives |
| `rh-charles-jubilees-1902-visual-review.json` | `87b4e81fdb6793b97dccedff60c319c5dff5cd796205b2af81d246a215979597` | Canonical AI-assisted review record for 18 reproducible scan crops; `verify_jubilees_pdf_review.py` pins Poppler 26.05.0 and verifies page count, crop selection, dimensions, bounds, and RGB hashes |

Generated outputs are deterministic:

- `corrected-bundle.zip`: `238bc987c8033f73fee8ffd0dd7401edb076b596c5e35afab3a7a4f3e8eb4693`
- `data-quality-report.json`: `3b20766cbc215da8a0e00d94293a52675599dd5fa9b050055d6fb8877d9ac93b`
- `manifest.json`: `f3210ba80b1c845b722464b6352745b2a2f81ddb9027efa5d231c0710df98dbf`

The report records the corrected bundle checksum and all row-level coverage totals; the manifest binds that checksum as the only publishable source file.

## Source groups

The original input archive contains 39 World Messianic Bible works, 27 Murdock Peshitta works, 6 WEB deuterocanonical works, 6 KJV fallback works, 3 Meqabyan works, and 2 Charles-related works. The generated collection now installs all 39 Old Testament works from the frozen official eBible World Messianic Bible VPL artifact. The reviewed pre-rebuild comparison found 12 works verified exact and 27 works rebuilt from the verified source; the final comparison contains 23,145 exact positions and no formatting, missing, extra, or wording differences.

The World Messianic Bible text is dedicated to the public domain, but the World Messianic Bible name is a trademark. Its naming condition says changed wording must not continue to use that name. The installed wording matches the official artifact exactly; deterministic conversion only changes the storage container from VPL rows to app JSON.

All 27 New Testament works now come from the locked official CrossWire Murdock module. The reviewed pre-rebuild comparison found 1,074 wording and one formatting difference across 26 works; 3 John was already exact. Those 26 works are classified `verified_rebuilt`; 3 John is `verified_exact`. The official-source rebuild finishes with 7,947 exact populated positions and no formatting, missing, extra, or wording differences. The exact ten blank source positions remain declared omissions. Historical corroboration uses the accurately labeled 1915 ninth edition. Before OCR inspection, the sampler fixes the median source position in each work third: 39 full verse sequences match one exact contiguous OCR window, 41 OCR failures are confirmed against auditable crops from the locked PDF, and Jude 1:13 has one explicitly disclosed historical-witness formatting variance (`shootingstars` in the CrossWire source versus `shooting-stars` in the historical witness) without changing Jude's rebuilt status. No fixed sample remains unresolved, and no alternate verse or generic token-joining rule is used. The visual evidence review is attributed to OpenAI Codex as an AI-assisted source verification; no human visual review is claimed.

The six KJV fallback works are Baruch, Letter of Jeremiah, Prayer of Azariah, Susanna, Bel and the Dragon, and Prayer of Manasseh. Project Gutenberg eBook 124 supplies exactly 387 reviewed positions: 140, 73, 67, 64, 42, and 1 respectively. The structural mappings are Baruch 6:1–73 to Letter of Jeremiah 1:1–73, Song of the Three Holy Children 2–68 to Prayer of Azariah 1:1–67, and the unnumbered Prayer of Manasses to Prayer of Manasseh 1:1; Song 1 and quoted canonical Daniel prose are excluded. The locked pre-rebuild reports record 9 exact and 378 wording-different positions. Every difference was adjudicated against the locked 1611 scan leaves, with 18 predetermined beginning/middle/end samples. Four apparent electronic transcription defects were narrowly corrected from the scan: `drinck` to `drink` (Bel 1:15), `dour` to `door` (Bel 1:18), `life up` to `lift up`, and `iniquites` to `iniquities` (Prayer of Manasseh 1:1). The final reports contain 387 exact positions and no remaining differences. This was an AI-assisted visual source review by OpenAI Codex; no human visual review is claimed. Verification never removes or softens the visible `KJV fallback` label, attribution, or API fallback flag.

Jubilees is rebuilt from the locked authorized-reprint transcription to the 1,307 numbered positions established by the original 1902 scan. The previous 1,758 app fragments compared as 54 exact, 1,253 wording/segmentation differences, and 451 extras. Nine fixed beginning/middle/end scan samples detected no revision in those sampled passages; this is not a full-edition collation. A pinned Poppler 26.05.0 reproducer verifies 18 locked scan crops covering those nine samples, all seven exact parser repairs, and full-page evidence for chapter 27 positions 1–13, with exact PDF, OCR/XML, scandata, page, coordinate, dimension, and crop-hash gates. The parser excludes introductory/editorial material, footnotes, page headers, marginal A.M. labels, and end matter; normalizes Unicode, HTML whitespace, and marker whitespace; corrects only seven scan-confirmed marker defects; and recovers the collapsed chapter-27 paragraph only from explicit scan-confirmed markers. The frequently repeated 1,341 count was rejected because the primary scan's 50 chapter maxima total 1,307. This is an AI-assisted source verification by OpenAI Codex; no human visual review is claimed.

The Meqabyan texts are attributed to Wikisource contributors under CC BY-SA 4.0. Reuse must preserve attribution, identify changes, link the license, and use compatible ShareAlike terms. Frozen revisions are [1 Meqabyan oldid 16044809](https://en.wikisource.org/w/index.php?title=Translation:1_Meqabyan&oldid=16044809), [2 Meqabyan oldid 16044810](https://en.wikisource.org/w/index.php?title=Translation:2_Meqabyan&oldid=16044810), and [3 Meqabyan oldid 16044811](https://en.wikisource.org/w/index.php?title=Translation:3_Meqabyan&oldid=16044811). The 2 Meqabyan revision has no labels 16:9 or 21:9; the build preserves those two known gaps and invents no placeholder text.

The Murdock archive also contains ten blank reserved positions, preserved as declared omissions rather than invented text: Matthew 26:30 and 26:45; Mark 4:10, 8:19, 9:31, and 11:19; Luke 18:35; Acts 19:41 and 20:17; and 2 Corinthians 13:14.

The official WEB British Edition Sirach VPL contributes 36 declared absent labels. Twenty-four are explicit blank rows: 1:5, 1:7, 1:21, 3:19, 10:21, 11:15, 13:14, 16:15, 17:5, 17:9, 17:16, 17:18, 17:21, 18:3, 19:18, 19:21, 20:3, 20:32, 22:9, 23:28, 24:18, 24:24, 25:12, and 26:19. Twelve additional numeric labels have no VPL row: 11:16, 16:16, 19:19, 22:10, and 26:20–27. These are omitted and declared without placeholders; every nonblank WEB row keeps its official chapter and verse identity. Together with the two Meqabyan and ten Murdock omissions, the manifest declares exactly 48 absent source/alignment positions.

## Deterministic corrections

The original archive is never mutated. The generator:

1. verifies all seven frozen build-input checksums and recomputes the raw duplicate audit;
2. canonicalizes and numerically sorts chapter identifiers while rejecting duplicate or missing chapters;
3. replaces all 39 WMB-group Old Testament works with the frozen official eBible World Messianic Bible VPL rows, preserving every official work, chapter, verse label, and scripture text;
4. replaces 1 Esdras, 2 Esdras, Tobit, Judith, Wisdom, and Sirach with the official WEB British Edition VPL source;
5. omits and declares the 24 explicit blank WEB Sirach rows and 12 additional absent numeric labels without renumbering any nonblank official verse;
6. replaces Enoch with the Project Gutenberg plain-text edition, follows Charles's Ethiopic (`E`) main reading while excluding separately marked Greek alternate-recension blocks (`G^g`, `G^s`, `G^{s1}`, `G^{s2}`), joins numbered and lettered fragments under their integer verse in source order, and normalizes presentation whitespace;
7. stores source chapters Enoch 3, 4, 35, and 44—which have no source verse numbering—as structural verse 1 solely for the app container;
8. replaces all 27 Peshitta-group New Testament works from the official CrossWire Murdock 1.2 module, removes only `FI` presentation delimiters and `RF` translator-note blocks, omits and declares ten blank reserved positions without renumbering other verses, normalizes four U+000F source separators to spaces while preserving surrounding words, and recovers Philemon 1:1 from the module's unique `philemon1:01` spill marker without inventing wording; and
9. replaces the six KJV fallback works with the scan-reviewed eBook 124 transcription, applies only the four position-specific scan-backed corrections documented above, and permanently preserves their KJV fallback disclosure; and
10. replaces Jubilees with the reviewed matching Charles edition and its exact 1,307-position structure using only the transformations documented above; and
11. rejects duplicate output positions and every undeclared verse gap.

No blanket “Yeshua”/“Jesus” substitution or other prose rewrite is performed.

## Rebuild and verify

Run from the repository root with the project Python environment:

```bash
python backend/data/scripture/eotc-composite-en/build_bundle.py
python backend/data/scripture/eotc-composite-en/build_manifest.py
python backend/data/scripture/eotc-composite-en/build_murdock_historical_evidence.py --check
python backend/data/scripture/eotc-composite-en/verify_murdock_pdf_review.py --pdftoppm /path/to/Poppler-26.05.0/pdftoppm
python backend/data/scripture/eotc-composite-en/build_bundle.py --check
python backend/data/scripture/eotc-composite-en/build_manifest.py --check
python -c 'from pathlib import Path; from app.library.ingest.manifest import SourceManifest; SourceManifest.model_validate_json(Path("backend/data/scripture/eotc-composite-en/manifest.json").read_text())'
python -m pytest backend/tests/library/ingest/test_composite_english_bundle_adapter.py::test_reviewed_corrected_ethiopian_composite_bundle_is_reproducible_and_truthful -q
```

The acceptance test regenerates twice into temporary directories, requires byte-identical artifacts, confirms the frozen inputs were unchanged, loads the strict Pydantic manifest, and parses all corrected rows through the production adapter.

## Release-scope audit

Run this command from `backend` after reviewing the bundle metadata:

```bash
python -m app.library.audit --bundle data/scripture/eotc-composite-en --markdown ../docs/operations/ethiopian-composite-release-audit.md
```

The audit cross-checks `manifest.json` with `data-quality-report.json`, freezes the reviewed scope and source-group counts, records provisional source records and KJV fallback works, and rejects any undeclared output gap. The generated report is an operational release record: it describes a mixed-source English compilation, not one uniform Ethiopian translation.
