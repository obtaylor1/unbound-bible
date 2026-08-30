# Scripture Source Verification and Progressive Publication Design

**Date:** 2026-08-17  
**Status:** Approved  
**Edition:** `EOTC-COMPOSITE-EN`

## 1. Purpose

Make every work already supplied in the mixed-source English research collection readable while completing reproducible source verification for the 73 works whose manifest records do not preserve an exact provenance URL. Verification must replace text from an approved official or historical source when the current text does not match, retain transparent fallback labels, and never describe the collection as a complete or officially authorized Ethiopian Orthodox Bible.

This design supplements the verification and publication sections of `2026-08-06-ethiopian-composite-english-design.md`. Existing safety, deterministic-build, canon-mapping, supplemental-work, attribution, and known-omission requirements remain in force.

## 2. Product and Editorial Rules

1. All 83 supplied works remain readable during verification.
2. The collection is presented as an **Ethiopian Canon Research Collection** or **mixed-source English research collection**, not as a complete, official, uniform, or ecclesiastically authorized Ethiopian Bible.
3. The 73 affected works display **Source verification in progress** until their exact source evidence and comparison results pass review.
4. A failed verification never deletes or silently changes the readable text.
5. When the readable text materially differs from the approved frozen source, the frozen source replaces it through the reviewed deterministic build.
6. The six KJV-derived works permanently retain a conspicuous text label: **KJV fallback**.
7. Source and verification meaning is never communicated by color alone.
8. Public-domain claims record the jurisdiction and supporting evidence. This system records evidence; it does not substitute for legal advice.

## 3. Affected Work Inventory

The 73 works with missing exact provenance are grouped by their current source-family claims.

### World Messianic Bible — 39

Genesis, Exodus, Leviticus, Numbers, Deuteronomy, Joshua, Judges, Ruth, 1 Samuel, 2 Samuel, 1 Kings, 2 Kings, 1 Chronicles, 2 Chronicles, Ezra, Nehemiah, Esther, Job, Psalms, Proverbs, Ecclesiastes, Song of Solomon, Isaiah, Jeremiah, Lamentations, Ezekiel, Daniel, Hosea, Joel, Amos, Obadiah, Jonah, Micah, Nahum, Habakkuk, Zephaniah, Haggai, Zechariah, and Malachi.

### Murdock Peshitta — 27

Matthew, Mark, Luke, John, Acts, Romans, 1 Corinthians, 2 Corinthians, Galatians, Ephesians, Philippians, Colossians, 1 Thessalonians, 2 Thessalonians, 1 Timothy, 2 Timothy, Titus, Philemon, Hebrews, James, 1 Peter, 2 Peter, 1 John, 2 John, 3 John, Jude, and Revelation.

### KJV 1611 fallback — 6

Baruch, Letter of Jeremiah, Prayer of Azariah, Susanna, Bel and the Dragon, and Prayer of Manasseh.

### R. H. Charles — 1

Jubilees.

The other ten supplied works already preserve precise upstream provenance: six WEB British Edition deuterocanonical works, three Wikisource Meqabyan works, and the Project Gutenberg edition of 1 Enoch. They remain subject to normal checksum and regression checks but are outside this 73-work remediation count.

## 4. Verification Status Model

Verification is stored per edition and work, not inferred from the edition code or source-family name.

| Status | Meaning | Public behavior |
|---|---|---|
| `in_progress` | Exact source evidence or comparison review is incomplete | Readable with **Source verification in progress** |
| `verified_exact` | Normalized text exactly matches the frozen source | Readable with **Source verified** |
| `verified_formatting` | Differences are limited to reviewed, documented non-wording transformations | Readable with **Verified with documented formatting changes** |
| `verified_rebuilt` | Material differences were resolved by rebuilding from the frozen source | Readable with **Rebuilt from verified source** |
| `review_required` | Rights evidence, parsing, coverage, or wording comparison has an unresolved material problem | Existing text remains readable with **Source review required** and is not promoted as verified |

Status changes require a completed comparison report and reviewer identity. A source-family result may update several work records in one reviewed release, but no work inherits verification merely because another work from that family passed.

## 5. Provenance Record

Each readable work has one active provenance record for its installed source edition. The record contains:

- edition identifier and canonical or supplemental work identifier;
- source-family key and public display label;
- translator or translation name;
- source language and tradition;
- exact edition, publication year, and upstream revision or archive identifier;
- exact source URL and rights-evidence URL;
- license identifier or public-domain statement with jurisdiction;
- original filename, retrieval date, byte size, and SHA-256 checksum;
- chapter count, populated verse-position count, and declared omissions;
- parser and normalization version;
- ordered, human-readable transformation notes;
- comparison totals for exact, formatting-only, missing, extra, and wording-different positions;
- comparison-report checksum and location;
- fallback and archive-modified flags;
- verification status, reviewer identity, review date, and optional review note.

Frozen original artifacts and generated comparison reports live outside application-served paths. Database and API records reference immutable checksums rather than treating a mutable URL as sufficient proof.

## 6. Source Selection and Verification Order

Verification proceeds in this order to resolve 66 works before the smaller special-source groups:

1. **World Messianic Bible:** use the official eBible machine-readable release. Record its release identifier and public-domain/name-use statement. If current wording differs, rebuild from the official release. A modified derivative that violates upstream naming conditions is not labeled World Messianic Bible.
2. **Murdock Peshitta:** freeze one historical Murdock edition and one reviewed machine-readable transcription tied to that edition. Preserve the historical scan identifier. Existing removal of `FI` emphasis delimiters, `RF` translator notes, separator normalization, and ten declared alignment omissions remains explicitly documented.
3. **KJV fallbacks:** use the approved Project Gutenberg eBook 124 electronic transcription, corroborated against the locked University of Pennsylvania Colenda original 1611 Robert Barker Great HE editio princeps catalog, IIIF manifest, and native page images. Project Gutenberg metadata alone is not evidence of KJV edition identity. Parse exactly the six works and 387 positions; preserve the reviewed Baruch/Letter and Song/Prayer mappings, exclude editorial canonical Daniel prose, adjudicate every initial difference against the scan, and retain the permanent fallback disclosure regardless of verification status. The source amendment was approved 2026-08-29 after eBook 30 was rejected because it lacks the required inventory; no design or source record may claim eBook 30 supports these works.
4. **Jubilees:** compare the current text against the R. H. Charles edition it claims to represent. Use an original public-domain historical scan, not an unreviewed modern reprint. Freeze the matching edition and rebuild if the existing wording comes from a different or edited text.

   Approved implementation amendment (2026-08-30): use the locked Internet Archive 1902 A. and C. Black scan as edition/numbering authority and its OCR/XML/scandata only for page anchors; use the locked clean transcription of the authorized 1917 reprint as machine-readable publication text after nine fixed scan samples detect no revision in those sampled passages. This is sampled evidence, not a full-edition collation. A pinned deterministic renderer must reproduce locked crops for all nine samples, all seven exact parser repairs, and full-page evidence for chapter 27 positions 1–13. The primary evidence establishes 1,307 Charles-numbered positions, not the unsupported secondary 1,341 count. Reject the current 1,758-fragment segmentation, repair only the seven scan-confirmed marker defects and explicit chapter-27 collapsed markers, and attribute the review truthfully as AI-assisted without a human-review claim.

Changing a source edition after verification creates a new provenance record and a new review. It never mutates the evidence attached to a previously published release.

## 7. Verification Pipeline

The verifier is divided into focused units:

`SourceArtifactRegistry`
: Loads reviewed source definitions, checks approved host and artifact metadata, verifies the artifact checksum, and returns immutable source evidence.

`SourceFamilyParser`
: Converts one approved source format into normalized work, chapter, verse-position, and text records. Each source family has its own adapter; permissive parsing is not shared across unrelated formats.

`ScriptureNormalizer`
: Applies only declared comparison rules such as Unicode normalization, line-ending normalization, and documented presentation-marker removal. It produces both original and normalized values so wording changes cannot be hidden.

`WorkComparator`
: Compares complete work coverage and classifies each position as exact, formatting-only, missing, extra, or wording-different. It rejects duplicate positions and distinguishes declared omissions from accidental gaps.

`VerificationReportWriter`
: Produces deterministic JSON and readable Markdown reports, binds them to source and generated-text checksums, and calculates source-family and work-level totals.

`ReviewedReplacementBuilder`
: Builds replacement rows only from a passing, reviewed source artifact. It writes a candidate bundle and never mutates the current publication directly.

`VerificationPublisher`
: Publishes a reviewed candidate atomically through the existing edition-scoped ingest path, preserves rollback history, and updates work-level status only after post-publish checks pass.

## 8. Data Flow and Safeguards

1. A reviewed source definition identifies an exact artifact and expected checksum.
2. Retrieval places the artifact in immutable local evidence storage.
3. Checksum, type, size, archive-member, and parser preconditions are validated before parsing.
4. The source-family parser emits normalized comparison records without touching the published database.
5. The comparator checks the complete current work against the frozen source and writes a deterministic report.
6. Exact or formatting-only results await human review before status changes.
7. Material wording differences generate a replacement candidate and a full change report.
8. A reviewer approves the candidate; the existing verified-ingest mechanism stages it.
9. Coverage, API, reader, search, comparison, and checksum checks run against staging.
10. Publication swaps the edition-scoped candidate atomically. A failed post-publish health check rolls back to the previous release.

Network retrieval is never part of an ordinary application request. The production reader serves installed, reviewed data and remains independent of upstream availability.

## 9. Failure Handling

- **Download or checksum failure:** stop before parsing; preserve the current text and status.
- **Unsupported or changed source format:** fail the family adapter; do not fall back to a permissive generic parser.
- **Duplicate, missing, or extra positions:** report every position and require review.
- **Unexplained wording differences:** set `review_required`; never classify them as formatting.
- **Insufficient rights evidence:** retain readability with a source-review warning, block verified promotion, and preserve the evidence reviewed so far.
- **Candidate ingest failure:** discard staging output and leave the active release untouched.
- **Post-publication health failure:** roll back to the last healthy edition-scoped publication.

Every failure produces an actionable report without exposing secrets, local filesystem paths, or hidden operational details in the public UI.

## 10. Reader, Compare, and Administrative Experience

### Reader

The reader shows a compact verification badge near the work's source label and an **About this text** or **Source details** action. The detail panel explains the source, language, edition, rights basis, transformations, fallback status, and verification date in plain language. Technical checksums are available in an expandable evidence section.

The collection-level disclosure states that sources vary by work and that the collection is intended for reading and research. It explicitly avoids claims of completeness or Ethiopian Orthodox Church authorization.

### Compare Scripture

Comparison cards use the same work-level provenance and status. Verification status is not treated as a wording difference. KJV fallback and source-review labels remain visible, and unavailable passage data is distinguished from a verified textual disagreement.

### Administration

An administrator can view the 83-work inventory grouped by source family, filter by status, inspect comparison totals, open source evidence, and see the reviewer and release associated with each work. Administrative actions do not provide a one-click way to mark a work verified without evidence and a passing report.

## 11. API Compatibility

Existing responses gain additive work-level provenance fields. At minimum, reader and comparison clients receive:

- public verification status and label;
- source display label and edition;
- source language and tradition;
- license or public-domain summary;
- fallback flag;
- concise transformation disclosure;
- verification date when verified;
- source-detail link or identifier.

Detailed evidence uses an authenticated administration endpoint or a focused public source-detail endpoint with safe fields. Clients never derive legal, fallback, or verification meaning from translation codes.

## 12. Testing and Acceptance Criteria

Automated tests must cover:

- the exact 39/27/6/1 affected-work grouping and total of 73;
- preservation of the ten already-provenanced works;
- manifest and database validation for every status and required provenance field;
- deterministic source parsing and comparison reports;
- checksum mismatch, changed format, duplicate position, accidental gap, and wording-difference failures;
- correct separation of formatting-only and material differences;
- candidate replacement without mutation of active data;
- atomic publication and rollback;
- reader and Compare Scripture labels for every status;
- permanent KJV fallback disclosure for all six works;
- collection naming and disclosure that avoid complete or official claims;
- search, navigation, commentary, comparison, and research access after replacement;
- keyboard use, screen-reader announcements, contrast, responsive layout, reduced motion, and 200% zoom;
- administrative progress totals and evidence access;
- production health checks after publication.

A source family is accepted only when every included work has a frozen source, exact edition and rights evidence, checksums, complete coverage comparison, no unexplained difference, documented transformations, reviewer identity, and passing application tests. The collection can remain publicly readable while verification is incomplete, but incomplete works retain their warning status.

## 13. Release Sequence

1. Add the status model, provenance fields, reports, and non-misleading public labels without replacing text.
2. Verify and, where required, rebuild the 39 World Messianic Bible works.
3. Verify and, where required, rebuild the 27 Murdock works.
4. Verify and, where required, rebuild the six KJV fallback works.
5. Verify and, where required, rebuild Jubilees.
6. Run the complete backend, frontend, browser, accessibility, data-integrity, and production health suites after every source-family release.

Each source-family release is independently reversible. A later family does not block already completed verification from remaining available.

## 14. Non-Goals

- Claiming that the collection is a complete or official Ethiopian Orthodox Bible.
- Treating a source-family name or public-domain label as sufficient provenance.
- Silently modernizing, harmonizing, paraphrasing, or replacing divine or personal names.
- Publishing AI-generated Scripture as a verified translation.
- Removing or obscuring KJV fallback identification.
- Reworking unrelated authentication, community, commentary, or research features.
- Providing a legal opinion about worldwide publication rights.
