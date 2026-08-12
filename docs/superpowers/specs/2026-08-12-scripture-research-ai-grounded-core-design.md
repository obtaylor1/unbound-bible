# Scripture Research AI — Grounded Core Design

**Date:** 2026-08-12  
**Status:** Approved for implementation planning  
**Route:** `#aistudy` (`chat` internally)  
**Reference:** User-supplied Scripture Research AI desktop composition

## 1. Objective

Replace the existing Ask the Bible card-and-chat page with a premium, accessible Scripture Research AI workspace. The first release must let a user ask a natural-language biblical research question and receive a structured investigation built only from verified material already available in the application library.

The experience must distinguish source traditions and AI synthesis, retain context across follow-up questions, expose claim-level citations, and clearly state when the surviving or indexed evidence does not answer a question.

This is the grounded-core release, not the completion of every specialist research workflow. It establishes the shared research architecture and completely implements the signature **What Happened Between?** mode. Other visible modes use the common research composer and response engine in this release; advanced mode-specific tools follow in later releases.

## 2. Product Principles

1. **Evidence before synthesis.** Retrieval supplies the evidence from which the response is built.
2. **No invisible default canon.** Every source carries an explicit tradition and provenance category.
3. **Unknown is an answer.** Missing chronology, disputed interpretation, and unavailable evidence are identified rather than filled with speculation.
4. **AI is visually distinct.** AI synthesis never looks like Scripture or another primary text.
5. **Research remains navigable.** Follow-ups and branches retain their relationship to the active research session.
6. **Existing systems are extended.** Authentication, study saving, sharing, library content, commentary, reader navigation, and provider adapters are reused rather than duplicated.

## 3. Release Scope

### Included

- Redesigned `#aistudy` page matching the supplied dark editorial reference.
- Empty-first research composer with compact examples.
- Multiline question input, keyboard submission, microphone affordance, and Ask action.
- Multi-select Source Scope with **Biblical Canon** selected by default.
- Research Depth selector with **Deep Research** selected by default.
- Six-mode toolbar with shared research behavior.
- Complete **What Happened Between?** event selection, research, and timeline workflow.
- Structured response sections chosen according to available evidence.
- Contextual two-column research workspace on desktop.
- Verified inline citations and an accessible citation drawer.
- Explicit provenance and confidence on claims.
- Contextual sources, people, places, follow-ups, and research trail.
- Session-aware follow-up questions.
- Save and Share using the existing account-aware study infrastructure.
- Progressive research loading stages, evidence-only fallback, retry, and insufficient-evidence states.
- Responsive, keyboard-accessible, reduced-motion behavior.
- One verified Eden-to-Abel demonstration fixture for development and testing; it is offered as a compact example and is not automatically displayed on first visit.

### Deferred

- External web or scholarly retrieval.
- Completion of dedicated guided workflows for Explain a Book, Compare Accounts, People & Places, Original Languages, and Genealogy.
- A full standalone Book Explainer experience.
- Cross-reference graph visualization.
- New map or manuscript ingestion systems.
- Automated speech transcription unless an already configured transcription provider can support the microphone control safely.

The deferred modes remain usable as focused research presets through the shared composer. The UI must not imply that their future specialist controls are already complete.

## 4. Information Architecture and Visual Design

### Page Header

- Title: **Scripture Research AI ✦**
- Supporting text: **Ask any question to understand scripture, ancient texts, biblical history, and original languages.**
- Preserve the main application navigation and existing `#aistudy` route.

### Research Composer

The composer is the first and strongest focal point. It contains:

- a multiline textarea;
- microphone control with an accessible label;
- prominent purple Ask button with sparkle icon;
- Source Scope controls;
- Research Depth controls;
- subtle purple border light and restrained shadow.

`Enter` submits. `Shift+Enter` inserts a newline. Submission is disabled for an empty value or while the same request is active.

### Source Scope

The available controls are:

- Biblical Canon
- Ethiopian Tradition
- Apocrypha
- 1 Enoch
- Jubilees
- Ancient Sources
- Commentary
- All Sources

Biblical Canon is the sole default. The source selection is enforced by retrieval filters and is not merely included in the model prompt. “All Sources” selects all indexed and eligible library categories; it does not enable external web content.

### Research Depth

- **Quick Answer:** concise grounded explanation.
- **Study:** core passages, context, and major cross-references.
- **Deep Research:** broader relevant library retrieval, structured sections, citations, and uncertainties.
- **Scholar:** original-language and manuscript details only where the local library contains verified records.

Deep Research is the default. Depth changes retrieval limits, eligible source records, response sections, and level of detail.

### Research Modes

The compact toolbar includes:

- What Happened Between?
- Explain a Book
- Compare Accounts
- People & Places
- Original Languages
- Genealogy

Selecting a mode adapts the composer without navigating away. In release one, What Happened Between? supplies FROM and TO event selectors plus **Build Timeline**. Other modes provide focused prompt guidance and query classification using the same grounded engine.

### Result Workspace

Desktop uses an approximate two-thirds/one-third grid. The wide column displays the research response. The inspector column updates from the same response object.

Possible main sections are:

- Overview
- Timeline
- Canonical Account
- Other Relevant Accounts
- Historical Context
- Language Notes
- What We Don't Know
- Related Questions
- Result action bar

Sections render only when supported or when an explicit absence/uncertainty is material. Empty ornamental sections are not shown.

The contextual inspector may render:

- Research Sources
- People
- Places
- Continue Research
- Book Explainer teaser where a verified book record is relevant

Before the first question, the workspace shows compact one-click examples rather than oversized canned-question cards. The Eden-to-Abel example is included.

### Visual Language

- Deep charcoal and black base layers.
- Warm ivory body and heading text.
- Antique gold for selected research and Scripture states.
- Purple for AI actions and synthesis.
- Restrained blue/green accents for later research mode cards.
- Serif typography for editorial headings and readable sans-serif for controls and body copy.
- Subtle 1px borders, soft shadows, 16–24px radii, and minimal glow.
- No bright neon or decorative motion that competes with research content.

### Responsive Ordering

At small widths, the layout becomes one readable column in this order:

1. page title;
2. composer;
3. source and depth controls;
4. mode toolbar;
5. main response;
6. timeline;
7. sources;
8. people;
9. places;
10. continued research.

The desktop inspector is never compressed into an unreadably narrow sidebar.

## 5. Component Boundaries

`ScriptureResearchPage`
: Owns the active research session, selected settings, query lifecycle, research trail, modal state, and page-level error handling.

`ResearchComposer`
: Owns question editing and presents Source Scope, Research Depth, mode-specific controls, microphone affordance, and submission status through explicit props and callbacks.

`ResearchModeToolbar`
: Selects a research mode and announces selection accessibly. It does not navigate.

`BetweenEventsComposer`
: Provides FROM and TO event selection and the Build Timeline action. Event results come from verified library/reference data rather than a hard-coded universal chronology.

`ResearchWorkspace`
: Renders typed response sections. It consumes the response contract and does not perform retrieval.

`ResearchTimeline`
: Renders evidence-backed events. Each event exposes actions for its cited passage, related sources, people, places, and a focused follow-up where those records exist.

`ResearchSection`
: Renders one classified group of claims with inline citations and appropriate source styling.

`ResearchInspector`
: Chooses and arranges contextual inspector cards from the response.

`CitationDrawer`
: Displays source title, relevant passage, provenance, tradition, date/era, original language, translation, relevance, and Open Full Text action when the corresponding data exists. It restores focus to the triggering citation when closed.

`ResearchTrail`
: Displays the active branch and allows a user to return to earlier nodes without losing later branches.

`ResearchLoadingState`
: Displays named retrieval and validation stages without exposing hidden reasoning.

Focused files and components are required. The page must not become another single component that mixes network logic, retrieval contracts, persistence, modal behavior, and rendering.

## 6. Response and Provenance Contracts

The implementation should follow existing JavaScript/Python conventions, but the boundary must express the following information:

```text
ResearchRequest
  question
  sessionId?
  parentNodeId?
  mode
  sourceScopes[]
  depth
  modeParameters?

ResearchClaim
  id
  statement
  classification
  confidence
  sourceIds[]

ResearchSource
  id
  title
  reference
  excerpt
  sourceType
  tradition
  dateOrEra?
  originalLanguage?
  translation?
  relevance?
  openTarget?

ScriptureResearchResponse
  id
  query
  mode
  settings
  summary
  timeline?
  canonicalAccount?
  ancientAccounts[]
  historicalContext?
  languageNotes[]
  unknowns?
  people[]
  places[]
  sources[]
  relatedQuestions[]
  groundingStatus
  provider
  model
  trailNode
```

Allowed claim classifications initially include:

- canonical-scripture
- ethiopian-canon
- ancient-text
- commentary
- tradition
- historical
- scholarship
- ai-synthesis

Every source returned to the browser has a stable source ID. Important generated claims must either reference one or more returned source IDs or be explicitly labeled as synthesis/uncertainty. Unsupported factual claims are removed before the response is returned.

## 7. Grounded Research Pipeline

The server-side coordinator performs:

1. Validate the request, limits, mode, depth, and permitted source scopes.
2. Classify the query and extract any explicit references, entities, books, events, and range intent.
3. Retrieve from enabled local library categories only.
4. Rank records by direct reference match, semantic/keyword relevance, source eligibility, and diversity appropriate to the selected scopes.
5. Extract a compact evidence set with stable IDs.
6. Ask the configured provider for a structured response constrained to that evidence.
7. Parse and validate the response schema.
8. Validate every cited source ID against the retrieved evidence.
9. Remove unsupported claims, downgrade partial claims, and construct uncertainty statements.
10. Derive inspector entities and follow-up suggestions only from validated response data.
11. Persist the research node when the user is authenticated; keep an equivalent local session for guests.
12. Return the structured response and grounding status.

Existing exact-reference retrieval, source records, citation validation, AI provider adapters, studies, commentary endpoints, and library routes must be evaluated and extended before new infrastructure is introduced.

## 8. Conversational Memory and Research Trail

A research session contains nodes rather than only a flat transcript. Each node records:

- question;
- parent node;
- selected source scope, depth, and mode;
- response ID;
- compact validated context needed by later questions;
- creation time.

A follow-up submits its parent node ID. The server resolves the relevant prior query, named entities, citations, and selected settings, then performs a new retrieval. Prior model prose is not treated as evidence.

The trail supports branches such as:

`Eden → Cain and Abel → Land of Nod → Cain's wife`

Returning to an earlier node changes the active view without deleting descendants. Guest sessions may use local storage; authenticated sessions extend the existing study storage and permissions model.

## 9. Citation and Source Behavior

- Inline citations are compact buttons, not inert text.
- Citation labels use human-readable references such as `Genesis 4:1–8`.
- Opening a citation shows the source drawer.
- Open Full Text routes into the existing scripture reader or appropriate library view when a reliable target exists.
- Source classification uses meaningful provenance: Canonical Scripture, Ethiopian Canon, Ancient Text, Manuscript, Historical Source, Early Christian Writing, Jewish Tradition, Church Tradition, Commentary, Scholarship, or AI Synthesis.
- “Primary,” “secondary,” and “tertiary” are not used as substitutes for tradition or canon status.
- AI synthesis has a purple sparkle treatment and is never presented with the Scripture book treatment.

## 10. Loading, Empty, and Failure States

### Loading

Deep Research displays a sequence of honest product stages, selected according to actual operations:

- Searching selected library sources…
- Ranking relevant passages…
- Comparing available evidence…
- Building the timeline…
- Verifying citations…
- Preparing the research summary…

The interface may progressively reveal skeleton sections, but it must not display chain-of-thought or claim that a source category was searched when it was not enabled or indexed.

### Empty

Show the composer and compact examples. Do not pre-populate a result automatically.

### Insufficient Evidence

Preserve the question and explain which selected source categories lacked relevant verified material. Offer narrower questions or an intentional source-scope change. Do not silently fall back to general model knowledge.

### Provider Failure

Return and render the verified evidence set with an evidence-only status, plus Retry. Do not convert provider failure into a fabricated synthesis.

### Network or Server Failure

Keep the entered question and settings, announce the error, and expose Retry. Duplicate submissions are prevented while a request is in flight.

## 11. Accessibility and Interaction Details

- Semantic heading hierarchy and landmark regions.
- All chips and toolbar items are real buttons with selected state announced through `aria-pressed` or equivalent semantics.
- Minimum 44px interactive targets where practical.
- Visible keyboard focus with sufficient contrast.
- Text and meaningful controls meet WCAG AA contrast.
- Timeline semantics do not rely on color or icon alone.
- Accessible dialog/drawer title, description, close control, focus trap, Escape behavior, and focus restoration.
- Status updates use an appropriate live region without excessive announcements.
- Reduced-motion mode disables streaming animation, pulsing glow, and staged entrance effects.
- Loading text remains understandable without animation.

## 12. Performance

- Route remains lazy-loaded through the existing application boundary.
- Deeper inspector content and source excerpts load on demand where appropriate.
- The initial page does not load all potential ancient-text or commentary content.
- Responses render progressively from a stable structured contract where the provider and server transport support it; otherwise staged loading and a single validated response are acceptable for release one.
- Research sessions and deterministic retrieval results may be cached with keys that include query, mode, depth, source scope, and library revision.
- Decorative imagery is minimized and optimized.

## 13. Testing and Verification

### Backend

- Request validation and limits.
- Source-scope enforcement.
- Depth-dependent retrieval behavior.
- Exact-reference and general-query retrieval.
- Citation IDs must belong to the retrieved evidence set.
- Unsupported claim removal or downgrade.
- Provider failure yields evidence-only output.
- Insufficient retrieval yields no invented answer.
- Parent-node follow-up resolves session context but treats only retrieved records as evidence.
- Study permissions and guest/authenticated persistence behavior.

### Frontend

- Empty-first state and example submission.
- Multiline keyboard behavior.
- Source Scope and Research Depth selection.
- Research mode selection without navigation.
- Complete Between Events control flow.
- Structured section rendering with optional sections absent safely.
- Citation drawer keyboard and focus behavior.
- Timeline event actions.
- Follow-up context and research-trail navigation.
- Loading, evidence-only, insufficient-evidence, and retry states.
- Save, Share, Clear/New Research, and route/navigation regression.
- Reduced-motion and screen-reader status behavior.

### End-to-End and Visual

- Eden-to-Abel verified fixture uses Genesis 2–4 and states that elapsed time is not supplied.
- No unrelated Enoch, Jubilees, or ancient source is added when Biblical Canon alone is selected.
- Enabling a source category does not force irrelevant content into the answer.
- Desktop, tablet, and mobile snapshots are reviewed against the supplied composition.
- Final inspection corrects typography, spacing, alignment, border, overflow, and contrast issues.
- Browser console has no new errors or warnings.
- Existing scripture reader, textual comparison, commentary, authentication, library, sharing, and navigation tests continue to pass.

## 14. Implementation Sequence Boundary

The implementation plan should split work into independently verifiable increments:

1. Research contracts and fixtures.
2. Scoped retrieval and response validation.
3. Session/trail persistence.
4. Composer and empty state.
5. Structured workspace and inspector.
6. Citation drawer and reader integration.
7. Between Events workflow.
8. Loading/failure/accessibility behavior.
9. Responsive visual polish and regression verification.

Each increment must include tests before relying on it in the next layer. The current large `AskTheBible.jsx` component should be replaced incrementally, with the `#aistudy` route continuously renderable during the transition.

## 15. Acceptance Criteria

The grounded-core release is accepted when:

- `#aistudy` opens an empty, polished Scripture Research AI workspace.
- Biblical Canon and Deep Research are the defaults.
- A user can ask the Eden-to-Abel example and receive a structured, cited investigation based on verified Genesis 2–4 records.
- The answer differentiates sourced claims, AI synthesis, and unknown information.
- All citation actions resolve to a returned source record.
- A user can perform and revisit contextual follow-up research without restating the full topic.
- What Happened Between? supports explicit FROM/TO events and produces an evidence-backed timeline.
- Other modes function as grounded focused presets without overstating specialist capabilities.
- Provider and retrieval failures are honest and recoverable.
- Save and Share retain existing authenticated and guest behavior.
- The page is usable with keyboard, screen reader, reduced motion, desktop, tablet, and mobile.
- Existing application functionality does not regress.

