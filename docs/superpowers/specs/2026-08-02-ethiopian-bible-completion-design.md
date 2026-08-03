# Ethiopian Bible Completion

## Goal

Complete the app's Ethiopian Orthodox Bible experience as a truthful, navigable, English-first collection based on the official 81-book canon. Use verified public-domain or openly licensed English texts where they exist, preserve verified Ge'ez or Amharic text where lawful English is unavailable, and identify every translation, recension, license, and coverage limitation.

The application must never imply that a canonical book is absent merely because a selected edition lacks its text. It must never store placeholders, summaries, sample prose, or AI-generated writing as scripture.

## Approved Direction

Use a verified multi-source collection rather than presenting `ETH81` as one complete uniform translation.

- The Ethiopian Orthodox Tewahedo Church's official 46 Old Testament and 35 New Testament list is the canon-membership authority.
- English is the primary reading language.
- Public-domain and openly licensed editions may be combined at the collection level, but each displayed passage keeps its real edition identity.
- Verified Ge'ez or Amharic text may fill original-language coverage gaps.
- A related Greek, Syriac, Latin, or Hebrew recension may be offered when useful, but it must be labeled as related rather than Ethiopian.
- No copyrighted text may be imported without explicit authorization.

## Definitions of Completion

The project distinguishes four kinds of completeness:

1. **Canon completeness:** all official Ethiopian Orthodox canon entries are represented and navigable.
2. **Edition completeness:** an edition contains every expected chapter and verse declared by its own versification.
3. **English coverage:** a lawful English reading text is available for a canon entry.
4. **Ethiopian-recension coverage:** a verified text derived from the Ethiopian Ge'ez tradition is available.

The product may be canon-complete while still showing explicit English-translation or Ethiopian-recension gaps. The interface must not call the collection a complete English Ge'ez translation unless that statement becomes verifiably true.

## Canon Model

Canon membership, book navigation, edition coverage, and passage text are separate data concerns.

### Canon Membership

A canon definition records the official name, ordering, grouping, and counting rules. The Ethiopian canon uses the official 46 Old Testament and 35 New Testament structure. Some entries combine works that English interfaces commonly expose separately. The application may provide navigable subworks, but the canon total must follow the official grouping rules instead of counting every navigation item as a separate canonical book.

The existing hard-coded `ETHIO81` list must be reconciled with the official structure. Its present displayed categories must not claim a total of 81 while enumerating a different number of standalone navigation entries.

### Works and Aliases

Each canonical work has one stable internal identifier and may have multiple names, including English, transliterated Ge'ez, historical, and current app aliases. Examples include Meqabyan/Maccabees naming, Ezra traditions, Dominos/Book of the Covenant, Qalementos/Clement, and Didesqelya/Didascalia.

Aliases affect lookup only. They must not collapse distinct works or imply that Ethiopian Meqabyan is the same text as Greek Maccabees.

### Editions and Coverage

An edition is a distinct textual source. Every edition records:

- stable edition code and display name;
- translator or editor;
- publication and publication date;
- reading language and source language;
- script;
- license and required attribution;
- provenance URL and source checksum;
- recension or textual tradition;
- versification identifier;
- expected work, chapter, and verse coverage;
- exact-Ethiopian, related-recension, or general-reading classification;
- verification and ingest status.

Coverage is computed from validated text records rather than inferred from canon membership.

## Initial Source Strategy

The source registry begins with independently verified editions drawn from the following classes:

- public-domain KJV for the shared 66-book English reading corpus;
- public-domain KJV Apocrypha, Revised Version Apocrypha, or Brenton Septuagint where appropriate for additional works;
- R. H. Charles's public-domain English translations of 1 Enoch and Jubilees;
- CC BY-SA community English translations of Meqabyan 1-3, with attribution and chapter-structure notes;
- public-domain scholarly translations for available church-order texts, including Didascalia, Te'ezaz, Apostolic Canons, and related material;
- verified Ge'ez or Amharic digital texts whose licenses permit application use;
- related-recension editions only when the relationship and differences are disclosed.

The Ertale source catalog is a bibliography and discovery aid, not an unquestioned authority or a single edition. Each underlying work and license must be independently registered. A website being publicly readable is not sufficient permission to ingest it.

The supplied 2024 Edward Jones PDF is excluded unless the copyright holder provides written reproduction permission.

## Ingestion Architecture

### Source Registry

A machine-readable source manifest defines edition metadata, authorization, expected coverage, canonical mappings, attribution, and source locations. Imports without complete license and provenance metadata fail before download or parsing.

### Acquisition

An edition-specific adapter reads an authorized local file, structured public dataset, or permitted remote source. Acquisition saves a source version and checksum so later imports can detect upstream changes.

Remote adapters must use TLS verification, bounded concurrency, timeouts, retries, rate limits, and a descriptive user agent. The existing pattern that disables TLS certificate verification is not acceptable for the production pipeline.

### Normalization

Normalization maps source book names to stable work identifiers, preserves the source's verse numbering, normalizes Unicode and whitespace, and records transformations. It must not silently rewrite verses to match another edition.

Composite works and alternative chapter systems retain explicit mappings. For example, a seven-chapter English Meqabyan source must not be presented as if it used the traditional 36-chapter structure.

### Staging and Validation

Adapters write to staging records, never directly to published scripture tables. Validation checks:

- expected books and chapters;
- missing, duplicated, or non-monotonic verse numbers;
- empty or suspiciously short content;
- placeholder phrases and sample text;
- unexpected HTML, OCR debris, or encoding corruption;
- source checksum changes;
- edition metadata and attribution completeness;
- declared versus observed coverage;
- repeat-import consistency.

Each run produces a human-readable and machine-readable coverage report. Publication is blocked by validation errors. Known source limitations may pass only as explicit reviewed warnings.

### Publication and Rollback

Publishing is transactional and edition-scoped. It stores the import run, source version, checksum, validation result, and affected records. Re-running an unchanged source is idempotent. A faulty edition can be rolled back without deleting other editions or canon mappings.

## Reader Experience

The reader separates two choices:

- **Canon:** controls which works are available for navigation.
- **Reading edition:** controls which actual text is displayed.

Choosing Ethiopian Orthodox shows every official canon entry. When a work is opened, the reader selects the best verified English reading edition according to a documented preference order, while displaying the edition's real name. The app must not rename KJV, Charles, or another source as an Ethiopian critical text.

An **About this text** panel shows translator, language, license, source tradition, recension relationship, coverage, and verification. The ordinary reading surface remains simple enough for readers approximately age 13 through age 70, with plain labels, large touch targets, strong contrast, readable type, keyboard support, and screen-reader semantics.

### Coverage Language

The interface uses direct, nonjudgmental status language:

- `Verified English text available`
- `Verified original-language text available`
- `Related recension - differences may exist`
- `English translation still needed`
- `<Book> is included in the Ethiopian Orthodox canon`

An unavailable edition is never described as a canon exclusion. Technical details remain expandable instead of blocking ordinary reading.

## Comparison Experience

The comparison workspace compares only editions containing real passage text. Missing editions do not count as wording differences and cannot become a usable base text.

Each comparison card shows the edition identity and textual relationship. Comparing a related Greek or Syriac recension with a Ge'ez-derived translation is allowed only when the relationship is visible. Summary language refers to available editions rather than implying that all selected sources contain the passage.

## Error Handling

- A network or API failure produces a retryable request error, not a false unavailable-edition state.
- A missing edition passage produces an edition-coverage state while retaining canon membership.
- A failed import leaves the last verified published edition untouched.
- License, provenance, checksum, or validation failures block publication and identify the exact source and reason.
- A withdrawn or disputed source can be disabled at edition level while preserving audit history.

## Testing

### Canon Tests

- Verify the official 46 Old Testament and 35 New Testament membership, ordering, grouping, and total.
- Verify aliases without conflating distinct works.
- Verify composite-work navigation and counting.

### Ingestion Tests

- Test every adapter with frozen fixtures.
- Verify normalization, Unicode handling, chapter mappings, and versification preservation.
- Reject placeholders, duplicates, missing required metadata, and malformed passages.
- Verify idempotent imports, transactional publication, and rollback.
- Verify license and attribution rules, including CC BY-SA requirements.

### Application Tests

- Verify that canon selection and edition selection remain independent.
- Verify Genesis and all shared books remain visible in the Ethiopian canon.
- Verify accurate fallback edition names and About-this-text metadata.
- Verify coverage, request-error, and related-recension states.
- Verify comparison behavior when a selected edition is missing.
- Verify keyboard navigation, screen readers, contrast, responsive layouts, and large text.

### Coverage Gate

A canon entry is marked complete only when expected navigation metadata exists and at least one verified lawful text or an explicit translation-needed record is present. An edition is marked complete only when its declared chapter and verse coverage passes validation with no placeholders.

## Rollout

1. Reconcile and test the official canon model and aliases.
2. Add edition, license, coverage, import-run, and validation metadata.
3. Replace direct and placeholder ingestion with the staged pipeline.
4. Import and verify the shared English corpus.
5. Import and verify additional public-domain and open-license works source by source.
6. Publish a coverage report and resolve critical gaps.
7. Update reader and comparison interfaces to consume canon and edition coverage separately.
8. Remove or quarantine placeholder scripture records.
9. Run application, accessibility, ingestion, and data-integrity checks before enabling the completed collection by default.

## Acceptance Criteria

- The Ethiopian Orthodox canon follows the official 46-plus-35 structure and reports 81 using its documented grouping rules.
- Every official entry is navigable and has a truthful coverage state.
- Genesis is always recognized as Ethiopian-canon scripture and opens a lawful English reading text.
- No edition is mislabeled as an Ethiopian critical text.
- No placeholder, summary, sample, or AI-generated sentence is served as scripture.
- Every published text has source, translator, language, license, provenance, recension, versification, and verification metadata.
- Related recensions and incomplete translations are clearly labeled.
- Imports are staged, validated, idempotent, auditable, and reversible.
- Reader and comparison tests pass across keyboard, screen-reader, responsive, and large-text scenarios.
- A generated coverage report identifies verified English, verified original-language, related-recension, and translation-needed status for every canon entry.

## Out of Scope

- Creating new scripture translations with generative AI.
- Importing copyrighted modern editions without permission.
- Claiming ecclesiastical endorsement for the multi-source English collection.
- Resolving scholarly disagreements by silently selecting one recension.
- Redesigning unrelated application areas.

## Authoritative and Source References

- Ethiopian Orthodox Tewahedo Church, official canon list: https://ethiopianorthodox.org/english/canonical/books.html
- Ertale Ethiopian Canon source index: https://bible.ertale.com/ethiopiancanon/
- Ertale source bibliography and edition caveats: https://bible.ertale.com/sources/
- eBible public-domain and open-license Bible datasets: https://ebible.org/
- English Wikisource licensing and source texts: https://en.wikisource.org/
