# Ethiopian Orthodox Composite English Design

**Date:** 2026-08-06

**Status:** Approved

## Purpose

Add the supplied `Ethiopian Orthodox Bible (Non-KJV Edition).zip` as a separately named English reading edition aligned with the app's `ETHIO81` canon. The import must preserve the existing Ge'ez research edition, identify the actual source used for every populated book, and remain honest about the canon works for which the archive supplies no English text.

## Source assessment

The supplied ZIP has SHA-256 checksum `0f4bdff8e24ee7e67afbd939d68a8dc40c0f1cf27026066dbb9f92ce34b183a2`. A read-only inspection found:

- 83 populated book files;
- 1,520 chapters;
- 44,114 verses;
- 11 additional canon-navigation records with no English text;
- no unsafe absolute or parent-traversal archive paths;
- six source groups: World Messianic Bible, Murdock Peshitta, World English Bible, KJV fallback, Wikisource Meqabyan, and R. H. Charles;
- six books explicitly identified by the archive as KJV fallbacks;
- 1,192 case-insensitive occurrences of `Yeshua` and no occurrences of `Jesus` in populated verse text.

The archive is a composite collection, not a single translation. Its source descriptions are useful but do not include precise source URLs, source revision identifiers, or checksums for every contributing text. The edition must therefore be published as provisional until source-level provenance is completed.

## Edition identity

- **Edition code:** `EOTC-COMPOSITE-EN`
- **Display name:** Ethiopian Orthodox Composite English
- **Reading language:** English
- **Canon:** `ETHIO81`
- **Subtitle:** An English reading collection aligned with the Ethiopian Orthodox canon; sources vary by book.
- **Verification status:** Provisional until all source records have precise, reviewed provenance.

`ETHIO81` remains a canon code and must never be used as a translation or edition code. `GEEZ1980-RESEARCH` remains a separate edition and its rows and metadata must not be replaced or mutated by this import.

## Coverage and missing works

All 83 populated books are imported after explicit mapping to the canonical work identifiers in `app.library.canon`. Chapter and verse coverage must be derived from and verified against the frozen archive.

The following eleven records remain visible in Ethiopian canon navigation but are not represented as translated text:

- Josephas son of Bengorion;
- Tegsats;
- Sirate Tsion;
- Tizaz;
- Gitsew;
- Abtilis;
- I Book of Dominos;
- II Book of Dominos;
- Book of Clement;
- Didascalia;
- the archive's separate `Metsihafe Tibeb` placeholder where it does not supply a distinct text beyond the mapped Wisdom tradition.

The importer must not generate, infer, or copy substitute verses for unavailable works. The catalog and reader show an `English text not yet available` state with the canon work's name and a short explanation. Unavailable works do not count toward installed edition coverage and do not appear as selectable comparison sources.

## Per-book source records

The existing edition-level provenance is insufficient for a mixed collection. Add a per-work source record associated with the edition and canonical work. Each record stores:

- source key and display label;
- translation or translator name;
- source language and source tradition;
- published year when known;
- SPDX license identifier;
- attribution text;
- provenance URL when verified;
- whether the text is a fallback;
- whether the archive compiler modified or standardized the text;
- an optional modification note.

The 83 populated books map to these source groups:

| Books | Source label | Source language | License treatment | UI badge |
| ---: | --- | --- | --- | --- |
| 39 | World Messianic Bible | Hebrew | Public domain | WMB |
| 27 | Murdock Peshitta (1852) | Syriac Aramaic | Public domain | Murdock |
| 6 | World English Bible | Greek/Hebrew | Public domain | WEB |
| 6 | KJV 1611 fallback | Greek/Hebrew | Public domain | KJV fallback |
| 3 | Wikisource Meqabyan | Ge'ez | CC BY-SA 4.0 | Ge'ez source |
| 2 | R. H. Charles | Ethiopic/Greek | Public domain | R. H. Charles |

The World English Bible name is only used for unchanged WEB source text. If the archive's `Yeshua` standardization altered a WEB-derived book, the source is described as `adapted from the World English Bible` instead. The same change disclosure applies to other source texts altered by the archive compiler.

The Meqabyan records must include appropriate credit, a link to CC BY-SA 4.0, an indication of changes, and the required ShareAlike treatment for distributed adaptations. Source-level attribution must remain available from the reader and comparison workspace.

## Archive ingestion

Add a dedicated adapter for this archive format rather than weakening the strict Ge'ez `weahadu_bundle` adapter. The new adapter:

1. accepts exactly one local, checksummed ZIP referenced by a reviewed manifest;
2. never executes archive code or extracts archive members to disk;
3. rejects encrypted, linked, absolute, backslash, empty, dot, and parent-traversal members;
4. enforces member-count and total-uncompressed-size limits;
5. requires an explicit source-book-to-canonical-work mapping;
6. rejects duplicate source IDs, duplicate canonical targets, missing mapped files, mismatched book identities, invalid chapters, invalid verses, empty text, and duplicate verse positions;
7. validates actual coverage against the manifest before allowing publication;
8. records a deterministic locator and checksum for every normalized verse;
9. stages and publishes through the existing atomic verified-ingest pipeline;
10. records unavailable navigation entries as coverage information, never as empty verse rows.

The original archive is stored as an immutable source artifact outside application-served paths. Its checksum is committed in the manifest. A checksum change requires a new reviewed ingest run and cannot silently update the edition.

## Verification lifecycle

The ingestion pipeline distinguishes two independent concepts:

- **Content validation:** the archive is structurally safe and its imported coverage and checksums match the reviewed manifest.
- **Source verification:** each contributing text is tied to a precise, reviewed provenance record and its license and modification claims are supported.

The edition may be installed after content validation but displays `Provisional source record` until source verification is complete. It must not inherit the existing pipeline's fully verified designation merely because the ZIP passes structural validation.

Publication is atomic and edition-scoped. Re-importing `EOTC-COMPOSITE-EN` replaces only that edition's active publication and preserves rollback history. It never deletes other translations or canonical catalog records.

## Reader experience

When `ETHIO81` is selected, `EOTC-COMPOSITE-EN` becomes the recommended English reading edition for covered works. The existing Ge'ez research edition remains selectable wherever it has coverage.

The reader displays:

- the edition name, not the canon code, as the selected translation;
- a concise source badge for the current book;
- a prominent red `KJV fallback` badge on the six fallback books;
- an `About this text` disclosure with translator, source language, tradition, date, license, provenance, modification note, and provisional status;
- an accessible unavailable-text state for the eleven missing works;
- an explanation that the collection combines sources and is not one uniform Ethiopian English translation.

Source badges must have text labels and cannot communicate meaning by color alone. Licensing and provisional status remain readable in light mode, dark mode, at 200% zoom, by keyboard, and with a screen reader.

## Compare Scripture behavior

Compare Scripture uses the same edition and per-book source metadata as the reader. It must:

- offer the composite only when it contains the requested work and passage;
- show the book's actual source label on its comparison card;
- show the KJV fallback badge where applicable;
- exclude unavailable works from translation-difference calculations;
- distinguish `text unavailable` from `wording differs`;
- retain the `ETHIO81` canon filter when switching editions.

## API behavior

Existing catalog and chapter responses gain additive source metadata without breaking current clients. The API exposes:

- edition verification status;
- current work's source label, language, license, fallback flag, modification flag, and attribution summary;
- coverage availability for each canonical work;
- an explicit unavailable reason where the edition has no English text.

Detailed provenance is available through the existing edition-detail pattern or a focused source-detail endpoint. The frontend must not derive legal or source labels from edition codes.

## Testing and acceptance

Automated coverage includes:

- archive safety and checksum failures;
- all 83 explicit book mappings;
- exact aggregate counts of 1,520 chapters and 44,114 verses;
- Genesis from the WMB group;
- one Murdock New Testament passage;
- all three Meqabyan books and their attribution;
- Enoch and Jubilees source records;
- all six KJV fallback badges;
- all eleven unavailable navigation records;
- preservation of `GEEZ1980-RESEARCH`;
- atomic publication and rollback isolation;
- reader edition selection, source disclosure, and unavailable states;
- Compare Scripture source labels and exclusion of unavailable texts;
- keyboard, screen-reader, contrast, responsive, and 200% zoom behavior.

Before release, run the complete backend, frontend unit, lint, build, desktop Playwright, mobile Playwright, and accessibility suites. A manual audit compares representative archive verses and source metadata against the installed database and reader output.

## Non-goals

- Translating the eleven unavailable works automatically.
- Calling the collection an official or uniform Ethiopian Orthodox English translation.
- Replacing the Ge'ez research edition.
- Hiding KJV-derived content behind a generic Ethiopian label.
- Claiming complete source verification without precise provenance evidence.
- Refactoring unrelated scripture, commentary, authentication, or community features.

## Future completion path

The eleven unavailable works require a separate translation project using verified Ge'ez source texts, documented textual witnesses, qualified human review, reconciliation of disputed readings, and versioned publication. AI may assist transcription and draft analysis but no generated verse is published as authoritative without human scholarly verification.
