# Scripture Research Library Foundation Design

**Date:** 2026-08-17
**Status:** Core rights foundation implemented; CI validation pending
**Milestone:** Compatibility-first research library foundation and proof corpus

## 1. Objective

Expand The Unbound Bible from a verse-centered reading application into a
source-aware biblical research library without destabilizing its existing
reader, comparison, commentary, authentication, notes, studies, sharing, or
grounded Scripture Research AI features.

The first milestone establishes the generalized library, rights, ingestion,
retrieval, citation, administration, and compatibility architecture. It proves
the complete workflow with three reviewed sources:

- World English Bible;
- the existing sourced 1 Enoch material;
- the existing sourced Jubilees material.

The milestone does not attempt to import the entire long-term corpus. Brenton's
Septuagint, Hebrew morphology, SBL Greek New Testament, Josephus, Early Church
Fathers, Dead Sea Scroll material, Meqabyan, and broader scholarly collections
follow after the foundation and rights gate are proven.

## 2. Product principles

1. **Evidence before synthesis.** AI answers are generated only from eligible,
   retrieved evidence.
2. **Edition-level rights.** Rights attach to the exact edition or dataset, not
   merely to an ancient work.
3. **Source identity is always visible.** Scripture, ancient literature,
   history, commentary, scholarship, and AI synthesis remain distinguishable.
4. **Existing features remain operational.** New models extend the current
   library and ingestion systems rather than replacing them in one migration.
5. **Uncertainty is explicit.** Missing, reconstructed, inferred, traditional,
   and disputed claims are labeled accurately.
6. **Publication is controlled.** Stored content is not public evidence until
   its source, rights, validation, and publication states all permit retrieval.
7. **Citations resolve to evidence.** Every meaningful factual claim must lead
   to a real content record and edition.

## 3. Scope

### Included

- Generalized work profiles and hierarchical divisions.
- Exact-edition and dataset records.
- Dedicated, edition-level rights records.
- Publication status and server-enforced public eligibility.
- Generalized content units, citation anchors, and research chunks.
- Compatibility registration for existing Scripture and commentary editions.
- Controlled adapters and staging for the three-source proof corpus.
- PostgreSQL full-text plus vector hybrid retrieval with lexical fallback.
- Source-aware ranking, source classification, and claim certainty.
- Shared Source Inspector for research, reader, comparison, and commentary.
- Read-only administrator source dashboard.
- Explicit administrator role, protected assignment command, and audit events.
- Protected operator commands for import, validation, activation, restriction,
  rollback, and embedding jobs.
- Additive migrations, feature flags, regression tests, and rollback paths.

### Deferred

- Browser-based upload, validation, approval, and rollback actions.
- Brenton Septuagint ingestion.
- Open Scriptures Hebrew Bible token, lemma, and morphology ingestion.
- SBL Greek New Testament ingestion.
- Josephus and Early Church Fathers ingestion.
- Dead Sea Scroll transcriptions, manuscript records, images, and comparison.
- Meqabyan and additional Ethiopian or Ge'ez source acquisition.
- Archaeology and modern scholarship datasets.
- Automated Unbound research translations.
- A broad entity graph beyond relationships required by the proof corpus.

## 4. Compatibility-first architecture

The existing `library_works` table remains the stable work identity. New tables
provide capabilities that do not fit the current verse and commentary models.
No existing text is deleted or moved in this milestone.

### 4.1 Work profiles

`research_work_profiles` is a one-to-one extension of `library_works`.

It records:

- short title and description;
- source classification;
- source hierarchy level;
- traditions and canonical statuses;
- original languages;
- authorship or attributed authorship;
- approximate date or era;
- historical and literary classification.

Initial stored work classifications include:

- canonical Scripture;
- Ethiopian canon;
- deuterocanonical Scripture;
- ancient biblical translation;
- ancient Jewish literature;
- Dead Sea Scroll manuscript;
- ancient historical source;
- early Christian writing;
- Jewish tradition;
- church tradition;
- archaeology;
- modern scholarship.

AI synthesis remains a parallel response classification. It may never be stored
as a research work or ingested as primary textual evidence.

### 4.2 Flexible divisions

`work_divisions` represents a parent-child hierarchy within a work. A division
has a stable ID, work ID, optional parent ID, type, label, normalized locator,
sequence, and optional display metadata.

Supported types initially include:

- book;
- section;
- chapter;
- verse;
- paragraph;
- fragment;
- column;
- line.

This supports Scripture, 1 Enoch sections, Jubilees, Josephus, patristic works,
and future manuscript fragments without forcing every work into
`book -> chapter -> verse`.

### 4.3 Exact editions and acquisitions

`source_editions` identifies the exact edition or dataset represented by stored
content. It records work scope, title, edition label, translator, editor,
publisher, publication year, original publication, language, script, source
URL, acquisition source, checksum, versification or locator scheme, attribution,
and verification date.

`source_edition_works` links an edition to every covered work and records any
work-specific source label, locator scheme, or attribution override. An edition
can therefore cover one work or a defined collection without duplicating its
edition-level rights record. Existing
`text_editions`, `edition_work_sources`, commentary sources, and publications
link to `source_editions` through compatibility records. Existing APIs continue
to use their current tables until consumers are migrated deliberately.

### 4.4 Rights records

`license_records` belongs to an exact edition or dataset. It records:

- license name and URL;
- public-domain determination;
- commercial-use permission;
- redistribution permission;
- modification permission;
- attribution requirement and required attribution;
- source-text rights;
- translation rights;
- image rights;
- reviewed source URLs;
- reviewer and verification date;
- explanatory notes.

Unknown values are not treated as permission. An edition whose public rights
cannot be established is set to `needs_rights_review` or
`internal_research_only`.

### 4.5 Publication control

`source_publications` stores the current public state and publication history.
Stored status codes are:

- `needs_rights_review`;
- `importing`;
- `verified`;
- `active`;
- `disabled`;
- `restricted`;
- `internal_research_only`.

At most one publication per source edition is selected as current by the
edition's active pointer. Multiple immutable historical snapshots may retain
the `active` status classification; replacement or rollback changes only the
active pointer transactionally rather than rewriting prior content.

Public retrieval eligibility is enforced by one server-side policy service.
An evidence record is eligible only when:

1. its publication is active;
2. its source validation is approved;
3. commercial display is allowed;
4. redistribution is allowed for the requested response behavior;
5. required attribution can be displayed;
6. its visibility is public;
7. it is not disabled, restricted, or internal-only.

Frontend visibility never substitutes for this policy.

### 4.6 Content, citations, and chunks

`content_units` stores edition-specific text attached to one division and one
immutable source publication. It records language, script, direction, sequence,
normalized text, source locator, and textual certainty.

Textual certainty values support:

- visible text;
- reconstructed text;
- supplied text;
- translation;
- editorial note.

`citation_anchors` provides stable human and machine locators for content units
and compatible legacy records. Each anchor resolves to a Source Inspector route.

`research_chunks` contains naturally bounded searchable units. Preferred
boundaries are verse, paragraph, section, chapter, fragment, manuscript column,
or commentary entry. A chunk records its source edition, work, division,
citation, classification, language, rights/publication linkage, content digest,
search document, and optional embedding.

Chunks are deduplicated by edition, division, boundary type, and content digest.

### 4.7 Audit events

`source_audit_events` is append-only. It records actor, source, action, prior
state, resulting state, timestamp, validation run, reason, and relevant
checksums for:

- registration;
- rights review;
- validation;
- activation;
- restriction;
- replacement;
- rollback;
- administrator assignment.

## 5. Administrator authorization

The existing user model gains an explicit role with initial stored values
`reader` and `administrator`; new accounts default to `reader`.
The first verified administrator account belongs to Obie Taylor. The account is
assigned through a protected one-time deployment command that accepts an
operator-supplied account identifier. No email address is hard-coded, and an
email match during normal sign-in can never grant administrator access.

Admin routes require authentication and server-side administrator permission.
Every mutating operator command creates an audit event. The milestone's browser
dashboard is read-only.

## 6. Ingestion and publication lifecycle

Every source follows the same lifecycle:

1. **Register acquisition.** Record source, checksum, edition, proposed
   classification, and rights-review inputs.
2. **Attach rights.** Create or select the exact license record.
3. **Stage.** Parse into normalized works, divisions, content units, and citation
   anchors. Staged data is never publicly retrievable.
4. **Validate.** Check schema, hierarchy, sequence, Unicode, duplicate locators,
   expected coverage, checksums, citation resolution, attribution, and rights.
5. **Review.** Produce rights and quality findings for administrator review.
6. **Publish.** Atomically activate an approved publication and create research
   chunks.
7. **Embed.** Generate embeddings only for eligible active chunks. Failure does
   not make a source unavailable to lexical retrieval.
8. **Verify.** Confirm public retrieval, filters, citations, attribution, and
   restricted-source exclusion.
9. **Rollback.** Restore the preceding publication without deleting import or
   audit history.

Adapters feed one normalized staging contract. The architecture accepts JSON,
XML/OSIS, USFM, CSV, TXT, and TEI XML. Only adapters required by the proof corpus
must be production-ready in this milestone. Other formats have validated
interfaces and fixtures but are not advertised as operational until exercised
with an approved dataset.

## 7. Proof corpus

### 7.1 World English Bible

Register the exact acquired WEB dataset, edition scope, checksum, source URL,
public-domain basis, attribution, and verification date. Preserve existing WEB
reader data. Create or link generalized divisions, citation anchors, chunks,
and compatibility records rather than inserting duplicate public verses.

### 7.2 1 Enoch

Register the exact existing historical English edition only after confirming
the digital transcription and translation rights. Its profile identifies it as
canonical in the Ethiopian Orthodox Tewahedo tradition and as ancient Jewish
apocalyptic literature.

The division hierarchy includes:

- Book of the Watchers, chapters 1-36;
- Book of Parables, chapters 37-71;
- Astronomical Book, chapters 72-82;
- Dream Visions, chapters 83-90;
- Epistle of Enoch, chapters 91-108.

### 7.3 Jubilees

Register the exact existing historical English edition only after confirming
the digital transcription and translation rights. Store its Ethiopian
canonical status, ancient Jewish literary classification, chapter divisions,
and reviewed Genesis/Exodus relationships.

If either historical digital edition fails rights review, it remains
`needs_rights_review` and the milestone proceeds with eligible sources. No
unverified substitute is made public.

## 8. Compatibility registration

Existing Scripture and commentary sources are registered without a destructive
rewrite.

- Legacy work IDs map to `library_works`.
- Existing text and commentary editions link to `source_editions`.
- Existing publication rows link to generalized publication records.
- Existing verse and commentary locators gain citation anchors.
- `legacy_source_links` and `legacy_content_links` hold typed references to the
  originating table and stable legacy identifier; generalized tables do not
  store polymorphic foreign keys without validation.
- Existing public endpoints keep their response contracts.
- Current rights metadata is imported when complete.
- Incomplete records receive explicit review findings and are not automatically
  added to the expanded AI corpus.

The current reader behavior remains authoritative during this milestone. The
generalized library becomes the authoritative source for eligibility and new
research retrieval.

## 9. Hybrid retrieval

The grounded research coordinator gains a generalized retriever with four
stages.

### 9.1 Intent and reference parsing

Detect exact references, named works, people, places, concepts, comparisons,
source scopes, and research modes. Existing event-range and exact-reference
parsing is reused.

### 9.2 Eligibility filtering

Apply source publication, validation, rights, classification, tradition,
language, and visibility filters before content can enter candidate search.

### 9.3 Candidate retrieval

Combine:

- exact citation-anchor matches;
- PostgreSQL full-text search;
- vector similarity;
- entity and reviewed cross-text relationships;
- current event-range retrieval.

If vector search or embedding generation is unavailable, exact-reference and
full-text retrieval remain operational.

### 9.4 Ranking

Rank direct passage matches first. Then rank relevant Level 1 primary textual
evidence, Level 2 biblical translations, Level 3 ancient literature, Level 4
historical interpretation, and eligible Level 5 modern scholarship according
to the user's scope and intent. Level 6 AI synthesis is never retrieved as
evidence.

Combine lexical, vector, reference, relationship, source-diversity, and
classification signals. Penalize duplicate chunks, weak semantic matches, and
sources outside the requested tradition. The exact weighting is configurable
and covered by deterministic ranking tests.

## 10. Grounded response behavior

The existing structured response and citation validation remain the final AI
boundary.

Every evidence record returned to the model contains:

- stable source ID;
- work, edition, and exact citation;
- excerpt;
- source classification and hierarchy level;
- tradition and canonical status;
- language and translation;
- textual certainty;
- rights-safe Source Inspector target.

Every meaningful factual claim cites one or more retrieved source IDs. Invalid
citations are rejected. Unsupported claims are removed or downgraded. The
response distinguishes explicitly stated, strongly supported, inferred,
traditional, disputed, and unknown claims.

Provider failure returns evidence-only results. Retrieval failure returns a
safe insufficient-evidence response. Neither path permits general model
knowledge to masquerade as local evidence.

## 11. Research and Source Inspector UX

The existing Scripture Research AI page remains the principal workspace.
Source scopes are presented in expandable groups:

- Scripture and biblical traditions;
- ancient translations and original languages;
- ancient literature and history;
- early Christian writings;
- manuscripts;
- scholarship.

Unavailable categories are clearly identified and cannot generate simulated
results.

Answer claims display classification and certainty labels. Citation controls
open a shared Source Inspector used by research, the Scripture Reader,
comparison, and commentary surfaces.

The Source Inspector shows:

- work and exact passage or division;
- source type and hierarchy level;
- tradition and canonical status;
- language and script;
- edition, translator, editor, and publication date;
- textual certainty;
- rights status and required attribution;
- source verification date;
- Open Full Text when permitted.

## 12. Read-only admin dashboard

The protected Research Library Sources dashboard shows:

- source and exact edition;
- classification and language;
- license and commercial-use status;
- publication and validation status;
- content and chunk coverage;
- checksum and last verification;
- unresolved rights and quality findings;
- recent audit events;
- the protected operator command required for the next action.

The dashboard cannot import, approve, activate, restrict, or roll back sources
in this milestone. Those actions use secured, tested commands. A later milestone
may add browser mutation after the command workflows and permissions are proven.

## 13. Database migrations

Migrations are additive and preserve existing records. They:

- create the generalized library, rights, publication, content, citation,
  chunk, compatibility, and audit tables;
- create foreign keys and indexed lookup paths;
- add explicit administrator authorization;
- register current sources in idempotent batches;
- preserve existing publication and user data;
- avoid dropping or rewriting legacy Scripture and commentary tables.

Compatibility registration is resumable and produces a report. Failed batches
roll back atomically. Destructive cleanup is outside this milestone.

## 14. Performance and operations

- Use indexed work, edition, division, citation, status, and rights lookups.
- Use PostgreSQL full-text indexes for lexical retrieval.
- Use `pgvector` in PostgreSQL for embedding storage and similarity search. A
  deployment preflight verifies extension availability before enabling vector
  retrieval; the public system retains a lexical-only fallback until that gate
  passes.
- Paginate library and admin queries.
- Lazy-load full works and division children.
- Deduplicate chunks before embedding.
- Run embedding and entity jobs outside request transactions.
- Bound retrieved evidence count, excerpt length, and model context.
- Cache stable source metadata and rights decisions with explicit invalidation.
- Record retrieval latency, excluded-source counts, citation failures, and
  embedding backlog.

## 15. Error handling

- Invalid source packages fail staging without public writes.
- Rights uncertainty produces `needs_rights_review`, not implicit approval.
- Validation findings block activation according to severity.
- Publication and rollback are edition-scoped and transactional.
- Embedding failure does not deactivate otherwise eligible lexical content.
- Retrieval excludes any source whose eligibility cannot be determined.
- Citation-resolution failure removes the candidate before model generation.
- Admin authorization failures reveal no source-management details.
- Existing reader and commentary APIs remain available if the generalized
  research index is temporarily unavailable.

## 16. Testing and quality gates

Required automated coverage includes:

- restricted and unreviewed sources never enter public retrieval;
- every public citation resolves to an active eligible content unit;
- edition and rights metadata appear in the Source Inspector;
- Hebrew right-to-left rendering and diacritics are preserved in shared
  components, even though full Hebrew ingestion is deferred;
- Greek and Ge'ez Unicode remain unchanged;
- division hierarchy, locators, and sequence validate correctly;
- duplicate citations, content units, and chunks are rejected;
- inactive content cannot become searchable through stale embeddings;
- vector failure falls back to exact-reference and full-text retrieval;
- source scopes enforce classification and tradition;
- AI claims cannot cite sources outside the retrieved evidence;
- compatibility registration is idempotent and resumable;
- publication and rollback preserve unrelated editions;
- existing reader, comparison, commentary, authentication, notes, studies,
  sharing, and research-trail tests remain green;
- admin routes reject non-admin users and all mutations create audit records;
- proof-corpus coverage and source checksums match reviewed manifests.

## 17. Rollout

1. Deploy additive schema and compatibility services behind feature flags.
2. Assign the verified initial administrator through the protected command,
   explicitly supplying both the deployment operator account ID and target
   account ID. The audit actor is always the supplied operator; the target is
   recorded separately as a deployment-bootstrap target, even when both IDs
   intentionally identify the same account.
3. Register existing sources and create findings for incomplete rights records.
4. Import, validate, and review WEB, 1 Enoch, and Jubilees.
5. Generate citation anchors, natural chunks, and embeddings for eligible
   publications.
6. Enable hybrid retrieval in staging while preserving the existing retriever
   as a fallback.
7. Run rights, citation, ranking, accessibility, regression, and load checks.
8. Activate the expanded corpus in production.
9. Monitor retrieval latency, excluded sources, unsupported claims, citation
   failures, and embedding backlog.
10. Roll back the feature flag or edition publication independently if a release
    gate fails.

## 18. Acceptance criteria

The milestone is complete when:

1. an eligible exact edition cannot be public without a reviewed rights record;
2. existing source editions appear in the admin dashboard without breaking
   their current reader behavior;
3. the verified administrator can inspect every source and audit event;
4. a user can ask a cross-source question using WEB, 1 Enoch, or Jubilees;
5. hybrid retrieval respects scope, tradition, classification, and rights;
6. each meaningful answer claim resolves through the shared Source Inspector;
7. Scripture, Ethiopian canon, ancient literature, and AI synthesis are visually
   and semantically distinct;
8. unavailable or disputed evidence is stated rather than invented;
9. vector unavailability falls back safely to lexical retrieval;
10. all existing production feature suites remain green.

## 19. Subsequent milestones

After acceptance, the next source milestones proceed independently:

1. Brenton Septuagint and cross-text alignment.
2. Open Hebrew text, tokens, lemmas, morphology, and Word Inspector.
3. Open Greek New Testament text and licensed lexical layers.
4. Josephus and Early Christian Writings.
5. Dead Sea Scroll metadata, certainty-aware transcription, and comparisons.
6. Additional Ethiopian and Ge'ez sources.
7. Browser-based admin import and approval workflow.
8. Expanded entity graph, archaeology, and approved scholarship.

Each source milestone must identify the exact digital edition, verify rights,
create a manifest, pass ingestion and retrieval quality gates, and obtain
administrator approval before public activation.
