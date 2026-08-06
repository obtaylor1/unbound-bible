# Ethiopian Orthodox Composite English source

This directory registers a **provisional mixed-source general-reading compilation**. It is not an official Ethiopian Orthodox edition, not a uniform translation, and not a complete English translation of the traditional 81-book canon.

## Reviewed scope

- 83 populated source works and 1,520 chapters
- 82 works mapped to the ETHIO81 library canon
- Prayer of Manasseh retained as one clearly marked supplemental work
- 38,938 publishable corrected verse rows
- 44,114 raw archive records are an audit count only; they include 5,252 exact duplicate excess records and 17 conflicting duplicate excess records

Thirteen ETHIO81 library works remain unavailable: Esther Greek Additions, Psalm 151, Tegsats, Paralipomena of Jeremiah, Josippon, Sirate Tsion, Tizaz, Gitsew, Abtilis, Metsihafe Kidan I, Metsihafe Kidan II, Qalementos, and Didesqelya.

## Frozen inputs and provenance

| Input | SHA-256 | Provenance and terms |
|---|---|---|
| `Ethiopian Orthodox Bible (Non-KJV Edition).zip` | `0f4bdff8e24ee7e67afbd939d68a8dc40c0f1cf27026066dbb9f92ce34b183a2` | User-supplied mixed-source archive; per-work verification remains provisional |
| `eng-webbe_vpl.zip` | `dc16460ed5e890e7b169cd3caeaa7e4adb4f7a6b5031bff85e4503389cd03b11` | [Official World English Bible British Edition with Deuterocanon](https://ebible.org/details.php?id=eng-webbe), public domain |
| `project-gutenberg-77935.txt` | `10d325355a810badf67bbbd1fe6bda77dc6e294eae78c2f6c69290188af45b14` | [R. H. Charles, *The Book of Enoch* (1917), ebook 77935](https://www.gutenberg.org/ebooks/77935), public domain in the USA |

Generated outputs are deterministic:

- `corrected-bundle.zip`: `fbf19b5ea60b2c7ece71efa741ea342a1b6da1b6e71c37f71fb367356b5d16e6`
- `data-quality-report.json`: `ee9be2af8a95a7366ecae6a70d7a28758ca53005683602d81b7f8fff1dd57c69`
- `manifest.json`: `5b1e39ac8425251f2b0b7e910df30ee2e86cf14c865da2e15fec8c0afc941e20`

The report records the corrected bundle checksum and all row-level coverage totals; the manifest binds that checksum as the only publishable source file.

## Source groups

The input archive contains 39 World Messianic Bible works, 27 Murdock Peshitta works, 6 WEB deuterocanonical works, 6 KJV fallback works, 3 Meqabyan works, and 2 Charles-related works.

The six KJV fallback works are Baruch, Letter of Jeremiah, Prayer of Azariah, Susanna, Bel and the Dragon, and Prayer of Manasseh. Their reader metadata must retain the visible KJV fallback label.

The Meqabyan texts are attributed to Wikisource contributors under CC BY-SA 4.0. Reuse must preserve attribution, identify changes, link the license, and use compatible ShareAlike terms. Frozen revisions are [1 Meqabyan oldid 16044809](https://en.wikisource.org/w/index.php?title=Translation:1_Meqabyan&oldid=16044809), [2 Meqabyan oldid 16044810](https://en.wikisource.org/w/index.php?title=Translation:2_Meqabyan&oldid=16044810), and [3 Meqabyan oldid 16044811](https://en.wikisource.org/w/index.php?title=Translation:3_Meqabyan&oldid=16044811). The 2 Meqabyan revision has no labels 16:9 or 21:9; the build preserves those two known gaps and invents no placeholder text.

The Murdock archive also contains ten blank reserved positions, preserved as declared omissions rather than invented text: Matthew 26:30 and 26:45; Mark 4:10, 8:19, 9:31, and 11:19; Luke 18:35; Acts 19:41 and 20:17; and 2 Corinthians 13:14.

## Deterministic corrections

The original archive is never mutated. The generator:

1. verifies all three frozen-input checksums and recomputes the raw duplicate audit;
2. canonicalizes and numerically sorts chapter identifiers while rejecting duplicate or missing chapters;
3. replaces 1 Esdras, 2 Esdras, Tobit, Judith, Wisdom, and Sirach with the official WEB British Edition VPL source;
4. omits WEB labels whose official VPL rows contain no text, then assigns contiguous structural output numbers in source order without changing scripture words;
5. replaces Enoch with the Project Gutenberg plain-text edition, joins wrapped/lettered fragments deterministically, and normalizes presentation whitespace;
6. stores source chapters Enoch 3, 4, 35, and 44—which have no source verse numbering—as structural verse 1 solely for the app container;
7. removes Murdock `FI` emphasis delimiters and `RF` translator-note blocks, omits and declares ten blank reserved positions without renumbering other verses, and normalizes four U+000F source separator characters across three verse texts to ordinary spaces; and
8. rejects duplicate output positions and every undeclared verse gap.

No blanket “Yeshua”/“Jesus” substitution or other prose rewrite is performed.

## Rebuild and verify

Run from the repository root with the project Python environment:

```bash
python backend/data/scripture/eotc-composite-en/build_bundle.py
python backend/data/scripture/eotc-composite-en/build_manifest.py
python backend/data/scripture/eotc-composite-en/build_bundle.py --check
python backend/data/scripture/eotc-composite-en/build_manifest.py --check
python -c 'from pathlib import Path; from app.library.ingest.manifest import SourceManifest; SourceManifest.model_validate_json(Path("backend/data/scripture/eotc-composite-en/manifest.json").read_text())'
python -m pytest backend/tests/library/ingest/test_composite_english_bundle_adapter.py::test_reviewed_corrected_ethiopian_composite_bundle_is_reproducible_and_truthful -q
```

The acceptance test regenerates twice into temporary directories, requires byte-identical artifacts, confirms the frozen inputs were unchanged, loads the strict Pydantic manifest, and parses all corrected rows through the production adapter.
