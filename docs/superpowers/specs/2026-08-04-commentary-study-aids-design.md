# Commentary Study Aids Design

## Goal

Add verified historical Bible commentaries as dependable study aids without displacing Scripture as the primary reading experience. Commentary must be understandable and accessible for readers from approximately age 13 through age 70, clearly attributed, usable on desktop and mobile, and available without depending on a third-party service during normal reading.

## Product Direction

Commentary becomes a dedicated tool inside the existing **Study Tools** experience.

- On desktop, it opens in the current right-side Study Tools drawer.
- On mobile, it opens in the existing accessible full-height sheet.
- Opening Commentary without selecting a verse shows the current chapter overview.
- Selecting a verse in the Scripture reader updates the tool to verse-specific commentary.
- A visible **Back to chapter overview** action restores the broader context.
- Closing Study Tools preserves the reader's position and selected verse.

This approach keeps Scripture visually dominant, reuses familiar navigation, and avoids a permanently crowded split-screen reader. A separate Commentary Library may be added later for browsing and research, but it is not part of the first release.

## Initial Sources

The initial import targets these five historical commentary collections identified as public domain in the supplied project guide:

1. Matthew Henry
2. John Gill
3. Adam Clarke
4. Jamieson–Fausset–Brown
5. Keil–Delitzsch

Public-domain status, source location, edition identity, and attribution must be independently verified before any collection is published. The import process must preserve the exact source and acquisition details rather than treating the supplied guide as sufficient legal evidence.

The data model must allow later additions from Ethiopian Orthodox, African, Eastern Christian, Catholic, Jewish, and contemporary licensed sources. Historical Western commentaries are presented as interpretive perspectives, not as definitive or neutral explanations.

Tyndale and other licensed collections are excluded from the first release. They require a separate licensing, attribution, redistribution, and share-alike review before ingestion.

## Reader Experience

### Opening Commentary

The Commentary tool initially shows:

- the current book and chapter;
- a **Chapter Overview** view;
- the active commentary source;
- author, publication period, tradition, and license information;
- a concise explanation when the source has no chapter-level entry.

The tool remembers the reader's last commentary source locally. It does not silently change sources when commentary is unavailable.

### Selecting a Verse

Verses in the Scripture reader become selectable without interfering with text selection, copying, notes, bookmarks, or links. Selecting a verse:

1. visibly highlights the verse using more than color alone;
2. opens or refreshes Commentary for that verse;
3. announces the new reference to assistive technology;
4. displays an entry that covers the verse, including a wider verse range where applicable;
5. ignores obsolete responses if the reader changes verses quickly.

Previous Verse and Next Verse controls permit linear study. The current Scripture text remains visible, and opening or closing the panel must not unexpectedly scroll the chapter.

### Commentary Controls

The tool provides:

- a plainly labeled source selector;
- **Chapter Overview** and **Selected Verse** tabs;
- Previous Verse and Next Verse controls;
- source information and a full citation;
- text-size controls shared with, or consistent with, the Scripture reader;
- search within the currently displayed commentary;
- copy text and copy citation actions;
- an expanded reading view;
- a later **Compare commentaries** view for two sources.

Icons supplement visible text labels rather than replacing them. Primary targets are at least 44 by 44 CSS pixels.

## Visual and Content Hierarchy

Scripture remains the primary layer. Published commentary is a secondary scholarly layer, and AI-generated explanations are a distinct tertiary layer.

- Scripture keeps the strongest reading typography and central position.
- Published commentary shows its source prominently at the top of every entry.
- AI-generated text is labeled **AI explanation** and never styled as quotation from a commentary author.
- Gold continues to identify primary navigation and citations, purple identifies study-tool selection, and amber identifies incomplete coverage or historical-context notices.
- Red remains reserved for genuine failures.

Commentary body text uses a highly readable serif face, a comfortable measure, adjustable size, and generous line height. Interface controls use the app's accessible sans-serif typography. Light and dark themes must both meet comfortable contrast targets.

## Data Strategy

Commentary is downloaded through an administrator-controlled ingestion workflow, validated, and stored locally. The production reader never depends on the upstream commentary API for passage display.

The supplied `download_commentaries.py` is useful as a source-discovery prototype, but it must not be used directly as the production importer. The production workflow adds:

- bounded requests, timeouts, and retry policy;
- resumable source-by-source imports;
- strict schema and reference validation;
- response-size and content-type checks;
- raw-source checksums;
- normalized book-name mapping;
- duplicate and overlap detection;
- per-book and per-chapter coverage reports;
- provenance and license records;
- staging and explicit publish approval;
- an audit record for every import and publication.

Unverified or incomplete imports stay in staging and are invisible to readers. Publishing uses a transactional edition switch so a failed import cannot partially replace live data.

## Data Model

The normalized backend model includes the following concepts.

### Commentary source

- stable source code;
- title and common abbreviation;
- author or editorial body;
- publication dates and edition description;
- tradition and historical context;
- language;
- license status and attribution text;
- upstream location and retrieval date;
- active publication edition.

### Commentary edition

- source identifier and dataset version;
- import job and checksum;
- record and coverage counts;
- validation status;
- staged, published, superseded, or rejected state;
- publication and rollback timestamps.

### Commentary entry

- canonical book identifier;
- chapter;
- starting and ending verse, when verse-scoped;
- entry type: book introduction, chapter overview, verse, or verse range;
- heading and normalized body;
- stable ordering within a reference;
- original source locator for citation;
- edition identifier.

Verse-range entries such as Genesis 1:1–3 remain ranges rather than being copied into three misleading independent entries. Queries for any covered verse return the range and label it accurately.

### Import audit

- job state and initiating administrator;
- source URL and retrieval details;
- validation errors and warnings;
- coverage comparison against the previous edition;
- publication decision and administrator;
- machine-readable report artifacts.

## API Design

Commentary endpoints live with the backend's library/read-only content domain and provide:

- published source metadata and coverage;
- chapter-overview entries;
- verse and verse-range entries for a canonical reference;
- a source comparison response for at most two sources;
- administrator-only import status, validation reports, publish, and rollback actions.

Reader requests are paginated or size-bounded, cacheable by edition and reference, and loaded only after Commentary is opened. Responses include source and edition identifiers so the interface can render accurate citations.

The public API never returns staged data. Unsupported books, absent commentary, incomplete imports, and server failures have distinct response states.

## Empty, Loading, and Error States

The interface distinguishes:

- **No entry for this passage:** the published source contains no applicable commentary.
- **Source not yet imported:** the collection is planned but not published locally.
- **Coverage incomplete:** a published edition is known to omit part of the requested material.
- **Entry covers a wider passage:** commentary applies to a verse range that includes the selected verse.
- **Unable to load commentary:** a genuine request or application error.

Every state offers a useful next action, such as choosing another source, returning to the chapter overview, or retrying. The app never fabricates, paraphrases, or silently substitutes commentary to fill a missing record.

Existing static or simulated commentary cards are removed when the real tool is connected. Until then, any retained demonstration content must be explicitly labeled as a preview and must not appear to be sourced commentary.

## Accessibility and Responsive Behavior

- Study Tools retains its current focus trap, Escape dismissal, focus restoration, and modal semantics.
- Tabs, source selection, verse state, expanded view, and comparison controls expose their state programmatically.
- The selected verse has a visible marker, accessible name, and screen-reader announcement.
- Color is never the only indicator of selection, coverage, warning, source, or error state.
- Commentary supports browser zoom and large text without horizontal page scrolling.
- Motion respects `prefers-reduced-motion`.
- On mobile, controls remain reachable without covering the commentary text or the system keyboard.
- Plain-language labels and short supporting explanations are favored over specialist terminology.

## AI Study Integration

AI Study integration follows only after verified commentary reading is complete.

- The user may explicitly include selected commentary sources as AI Study context.
- Generated answers cite the commentary source and exact Scripture reference.
- Citations link back to the locally stored published entry.
- AI content remains clearly separated from verbatim or edited commentary text.
- Missing commentary is never represented as evidence used by the AI.
- Source quotations are bounded and attribution is preserved.

## Delivery Phases

### Phase 1: Trusted ingestion foundation

Create models, migrations, source metadata, administrator-controlled importing, validation, coverage reporting, staged publication, rollback, and backend tests.

### Phase 2: Initial public-domain corpus

Verify licensing and provenance, import the five approved sources, resolve book/reference mappings, review coverage reports, and publish only validated editions.

### Phase 3: Core Commentary tool

Add the Study Tools entry, chapter overview, verse selection, source selector, citations, accurate availability states, desktop drawer behavior, and mobile sheet behavior.

### Phase 4: Reading enhancements

Add within-entry search, expanded reading view, copy/citation actions, source details, text-size integration, and Previous/Next Verse navigation.

### Phase 5: Comparison and AI grounding

Add two-source comparison, then allow explicitly selected published entries to ground AI Study responses with visible citations.

## Testing and Acceptance

Backend tests cover:

- source, edition, entry, range, and audit constraints;
- canonical reference mapping;
- invalid schemas, oversized responses, interrupted imports, retries, and duplicate records;
- coverage reporting and regression thresholds;
- staging isolation, transactional publishing, and rollback;
- public versus administrator authorization;
- cache and edition correctness.

Frontend tests cover:

- Commentary closed by default;
- chapter overview on initial open;
- verse selection, highlighting, announcement, and stale-request protection;
- verse-range labels;
- source persistence and unavailable-source behavior;
- loading, no-entry, incomplete-coverage, offline, and error states;
- copy, citation, search, text size, and expanded view;
- keyboard use, focus behavior, screen-reader names, zoom, and reduced motion;
- desktop, tablet, and mobile layouts in light and dark themes;
- regression protection for Scripture selection, notes, bookmarks, and other Study Tools.

The first release is complete when all five approved sources have verified provenance and coverage reports, published entries are served entirely from local data, chapter and verse commentary work in the existing accessible Study Tools experience, synthetic commentary is not presented as genuine source material, and the relevant automated and manual accessibility checks pass.
