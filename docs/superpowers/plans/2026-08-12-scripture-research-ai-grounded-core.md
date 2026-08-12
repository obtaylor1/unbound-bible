# Scripture Research AI Grounded Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `#aistudy` with an accessible, responsive Scripture Research AI workspace that returns structured, library-only investigations with verified citations, contextual follow-ups, and a complete What Happened Between? timeline workflow.

**Architecture:** Add a new `/api/v1/research` boundary beside the existing `/chat/ask` endpoint. A server-side coordinator validates source scope, retrieves verified local evidence, asks the configured provider for a strict JSON response, validates claim-to-source mappings, and returns a stable structured contract; focused React components render that contract and reuse existing study, share, reader, and authentication behavior.

**Tech Stack:** React 19, Vite 7, Vitest, Testing Library, Playwright, FastAPI, Pydantic, SQLAlchemy 2, Alembic, pytest, existing AI provider adapters and library database.

---

## File Structure

### Backend files to create

- `backend/app/research/__init__.py` — package boundary.
- `backend/app/research/schemas.py` — request/response, claim, source, event, entity, and trail contracts.
- `backend/app/research/retrieval.py` — source-scope-aware exact/range/lexical retrieval.
- `backend/app/research/validation.py` — structured-provider parsing and claim/citation validation.
- `backend/app/research/service.py` — query orchestration, evidence-only fallback, and follow-up context.
- `backend/app/research/router.py` — `/research/query`, `/research/events`, and authenticated trail endpoints.
- `backend/app/research/models.py` — persisted research nodes for authenticated users.
- `backend/app/research/event_catalog.py` — reviewed event definitions whose references are resolved against library rows.
- `backend/alembic/versions/0011_research_trail.py` — research-node persistence.
- `backend/tests/research/test_schemas.py` — contract and validation tests.
- `backend/tests/research/test_retrieval.py` — scope, range, and relevance tests.
- `backend/tests/research/test_service.py` — orchestration and failure-state tests.
- `backend/tests/research/test_routes.py` — API, permissions, events, and follow-up tests.

### Backend files to modify

- `backend/app/api/router.py` — mount the research router.
- `backend/app/application.py` — import/register research models if required by the existing metadata initialization pattern.
- `backend/app/studies/models.py` — add the study-to-research-node relationship only if required for ORM navigation.
- `backend/tests/conftest.py` — add reusable verified scripture/event fixtures without changing existing tests.

### Frontend files to create

- `frontend/src/scriptureResearch/researchModel.js` — UI constants and response normalization.
- `frontend/src/scriptureResearch/researchApi.js` — API calls and guest-session serialization.
- `frontend/src/scriptureResearch/ScriptureResearchPage.jsx` — page state and orchestration.
- `frontend/src/scriptureResearch/ScriptureResearchPage.css` — page tokens, layout, responsive, focus, and reduced-motion styles.
- `frontend/src/scriptureResearch/ResearchComposer.jsx` — question, source scope, depth, and submission.
- `frontend/src/scriptureResearch/ResearchModeToolbar.jsx` — six accessible mode tabs.
- `frontend/src/scriptureResearch/BetweenEventsComposer.jsx` — FROM/TO event selection.
- `frontend/src/scriptureResearch/ResearchLoadingState.jsx` — honest operation stages.
- `frontend/src/scriptureResearch/ResearchWorkspace.jsx` — structured main result.
- `frontend/src/scriptureResearch/ResearchTimeline.jsx` — interactive evidence-backed timeline.
- `frontend/src/scriptureResearch/ResearchInspector.jsx` — sources, entities, and follow-ups.
- `frontend/src/scriptureResearch/CitationDrawer.jsx` — accessible provenance dialog.
- `frontend/src/scriptureResearch/ResearchTrail.jsx` — branch navigation.
- `frontend/src/scriptureResearch/ScriptureResearchPage.test.jsx` — page and state integration.
- `frontend/src/scriptureResearch/ResearchComposer.test.jsx` — keyboard and selector behavior.
- `frontend/src/scriptureResearch/ResearchWorkspace.test.jsx` — structured result and citation interactions.
- `frontend/src/scriptureResearch/researchApi.test.js` — request and normalization tests.
- `frontend/e2e/scripture-research-ai.spec.js` — desktop/mobile grounded workflow and accessibility.

### Frontend files to modify

- `frontend/src/components/AskTheBible.jsx` — replace the legacy component body with a compatibility export of `ScriptureResearchPage` after tests pass.
- `frontend/src/components/AskTheBible.css` — remove from runtime imports; retain until the compatibility swap is verified, then delete in a later cleanup commit.
- `frontend/src/routing/pageRoutes.js` — change the visible page title to Scripture Research AI without changing `#aistudy`.
- `frontend/src/routing/pageRoutes.test.js` — verify route compatibility and title.
- `frontend/src/components/Navigation.jsx` — rename Ask the Bible navigation text to Scripture Research AI.
- `frontend/src/components/Navigation.test.jsx` — verify renamed navigation and existing route.
- `frontend/src/reader/studyToolRegistry.js` — rename the reader action while keeping page `chat`.
- `frontend/src/reader/StudyTools.test.jsx` — update the expected accessible label.

## Task 1: Lock the Research Contracts

**Files:**
- Create: `backend/app/research/__init__.py`
- Create: `backend/app/research/schemas.py`
- Create: `backend/tests/research/test_schemas.py`

- [ ] **Step 1: Write failing contract tests**

```python
from pydantic import ValidationError
import pytest

from app.research.schemas import ResearchQueryRequest, ResearchResponse


def test_query_defaults_to_biblical_canon_and_deep_research():
    payload = ResearchQueryRequest(question='What happened between Eden and Abel?')
    assert payload.source_scopes == ['biblical-canon']
    assert payload.depth == 'deep-research'
    assert payload.mode == 'what-happened-between'


def test_query_rejects_unknown_scope():
    with pytest.raises(ValidationError):
        ResearchQueryRequest(question='Explain Genesis', source_scopes=['the-web'])


def test_claim_sources_must_be_returned_by_response():
    with pytest.raises(ValueError, match='unknown source ID'):
        ResearchResponse.model_validate({
            'id': 'response-1', 'query': 'Question', 'mode': 'general',
            'settings': {'source_scopes': ['biblical-canon'], 'depth': 'deep-research'},
            'summary': {'title': 'Overview', 'claims': [{
                'id': 'claim-1', 'statement': 'A claim', 'classification': 'canonical-scripture',
                'confidence': 'high', 'source_ids': ['scripture:404'],
            }]},
            'ancient_accounts': [], 'language_notes': [], 'people': [], 'places': [],
            'sources': [], 'related_questions': [], 'grounding_status': 'grounded',
            'provider': 'test', 'model': 'test',
        })
```

- [ ] **Step 2: Run the tests and confirm the missing package failure**

Run: `cd backend && pytest tests/research/test_schemas.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.research'`.

- [ ] **Step 3: Implement strict Pydantic contracts**

Define string enums for source scopes, depth, mode, classification, confidence, and grounding status. Define `ResearchSettings`, `ResearchSource`, `ResearchClaim`, `ResearchSection`, `TimelineEvent`, `PersonReference`, `PlaceReference`, `TrailNode`, `ResearchQueryRequest`, and `ResearchResponse`. Add an `after` model validator on `ResearchResponse` that rejects any claim or timeline `source_ids` not present in `sources`.

The exact request fields are:

```python
class ResearchQueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=10_000)
    session_id: uuid.UUID | None = None
    parent_node_id: uuid.UUID | None = None
    mode: ResearchMode = ResearchMode.BETWEEN
    source_scopes: list[SourceScope] = [SourceScope.BIBLICAL_CANON]
    depth: ResearchDepth = ResearchDepth.DEEP
    mode_parameters: dict[str, str] = {}
```

Use `Field(default_factory=...)` for list and dictionary defaults. Restrict `source_scopes` to one through eight unique values and reject `all-sources` when mixed with another value.

- [ ] **Step 4: Run the contract tests**

Run: `cd backend && pytest tests/research/test_schemas.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the contract boundary**

```bash
git add backend/app/research backend/tests/research/test_schemas.py
git commit -m "feat: define scripture research contracts"
```

## Task 2: Add Scope-Aware Verified Retrieval

**Files:**
- Create: `backend/app/research/retrieval.py`
- Create: `backend/tests/research/test_retrieval.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Add failing retrieval tests**

Seed Genesis 2–4 in KJV plus one Ethiopian edition row and commentary record. Test:

```python
def test_biblical_canon_scope_excludes_ethiopian_and_commentary(session):
    result = retrieve_research_evidence(
        session, question='Adam Eve Eden Abel Cain',
        source_scopes=[SourceScope.BIBLICAL_CANON], depth=ResearchDepth.DEEP,
    )
    assert result
    assert {item.source_type for item in result} == {'canonical-scripture'}
    assert all(item.tradition == 'Protestant' for item in result)


def test_ethiopian_scope_does_not_force_irrelevant_rows(session):
    result = retrieve_research_evidence(
        session, question='Cain and Abel',
        source_scopes=[SourceScope.ETHIOPIAN_TRADITION], depth=ResearchDepth.DEEP,
    )
    assert all('unrelated' not in item.text.lower() for item in result)


def test_depth_changes_evidence_limit(session):
    quick = retrieve_research_evidence(session, 'Genesis 4', [SourceScope.BIBLICAL_CANON], ResearchDepth.QUICK)
    deep = retrieve_research_evidence(session, 'Genesis 4', [SourceScope.BIBLICAL_CANON], ResearchDepth.DEEP)
    assert len(quick) < len(deep)
```

- [ ] **Step 2: Run the retrieval tests and confirm failure**

Run: `cd backend && pytest tests/research/test_retrieval.py -q`

Expected: FAIL because `retrieve_research_evidence` does not exist.

- [ ] **Step 3: Implement the normalized retrieval record**

```python
@dataclass(frozen=True)
class ResearchEvidence:
    id: str
    title: str
    reference: str
    text: str
    source_type: str
    tradition: str
    translation: str | None = None
    date_or_era: str | None = None
    original_language: str | None = None
    open_target: str | None = None
    score: float = 0.0
```

Implement `retrieve_research_evidence` using parameterized SQL only. First reuse `parse_reference` and `retrieve_exact_reference` for explicit references. For general questions, normalize meaningful tokens of at least three characters, search `biblical_texts` with bounded `LIKE` predicates, apply source-scope filters from available edition/work metadata, and rank direct book/reference matches above token matches. Use limits `quick=6`, `study=12`, `deep=24`, `scholar=32`.

When required metadata tables are absent in a test or older database, classify known Western translations as `canonical-scripture`/`Protestant` and do not broaden into other scopes. Commentary retrieval must call the existing commentary service instead of reading unpublished records.

- [ ] **Step 4: Run retrieval and legacy grounding tests**

Run: `cd backend && pytest tests/research/test_retrieval.py tests/ai/test_grounded_answer.py -q`

Expected: PASS.

- [ ] **Step 5: Commit verified retrieval**

```bash
git add backend/app/research/retrieval.py backend/tests/research/test_retrieval.py backend/tests/conftest.py
git commit -m "feat: retrieve scoped research evidence"
```

## Task 3: Validate Structured Provider Output

**Files:**
- Create: `backend/app/research/validation.py`
- Create: `backend/tests/research/test_validation.py`

- [ ] **Step 1: Write failing validation tests**

```python
def test_validation_removes_claim_with_unknown_source(evidence):
    raw = {'summary': {'title': 'Overview', 'claims': [
        claim('supported', ['scripture:1']), claim('invented', ['scripture:999'])
    ]}}
    validated = validate_provider_document(raw, evidence)
    assert [item.statement for item in validated.summary.claims] == ['supported']
    assert 'unsupported claim removed' in validated.validation_warnings


def test_validation_downgrades_uncited_synthesis(evidence):
    raw = {'summary': {'title': 'Overview', 'claims': [
        claim('Interpretive bridge', [], classification='ai-synthesis', confidence='high')
    ]}}
    validated = validate_provider_document(raw, evidence)
    assert validated.summary.claims[0].confidence == 'low'
```

- [ ] **Step 2: Run the tests and confirm failure**

Run: `cd backend && pytest tests/research/test_validation.py -q`

Expected: FAIL because the validation module is missing.

- [ ] **Step 3: Implement strict JSON parsing and sanitization**

Implement `parse_provider_json(content: str) -> dict` with no Markdown fallback beyond removing one outer JSON code fence. Implement `validate_provider_document(document, evidence)` to:

- create the available source-ID set;
- remove factual claims that cite unknown or empty source sets;
- allow uncited `ai-synthesis` and uncertainty statements only at low confidence;
- remove unsupported timeline events;
- discard entities whose source IDs are invalid;
- deduplicate related questions;
- return validation warnings used for operation auditing.

Do not repair a malformed provider response by inventing content.

- [ ] **Step 4: Run validation tests**

Run: `cd backend && pytest tests/research/test_validation.py -q`

Expected: PASS.

- [ ] **Step 5: Commit structured validation**

```bash
git add backend/app/research/validation.py backend/tests/research/test_validation.py
git commit -m "feat: validate structured research claims"
```

## Task 4: Build the Grounded Research Coordinator

**Files:**
- Create: `backend/app/research/service.py`
- Create: `backend/tests/research/test_service.py`

- [ ] **Step 1: Write failing orchestration tests**

Use stub retrievers and providers to assert:

```python
@pytest.mark.asyncio
async def test_no_evidence_returns_insufficient_without_calling_provider():
    provider = RecordingProvider()
    result = await ResearchService(retriever=lambda *_: [], provider=provider).query(request)
    assert result.grounding_status == 'insufficient'
    assert result.sources == []
    assert provider.calls == []


@pytest.mark.asyncio
async def test_provider_failure_returns_evidence_only(evidence):
    result = await ResearchService(
        retriever=lambda *_: evidence, provider=FailingProvider()
    ).query(request)
    assert result.grounding_status == 'evidence-only'
    assert {source.id for source in result.sources} == {'scripture:1'}


@pytest.mark.asyncio
async def test_grounded_response_contains_only_validated_claims(evidence):
    result = await service_with_document(provider_document_with_one_invalid_claim).query(request)
    assert result.grounding_status == 'grounded'
    assert all(set(claim.source_ids) <= {'scripture:1'} for claim in result.all_claims())
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend && pytest tests/research/test_service.py -q`

Expected: FAIL because `ResearchService` is missing.

- [ ] **Step 3: Implement the orchestration service**

`ResearchService.query` must retrieve first, build a provider prompt containing only compact evidence records and the strict response schema, parse/validate the JSON, attach normalized source records, and record an `AIOperation`. Use the configured provider adapter through a constructor dependency so tests do not patch module globals.

The system instruction must include:

```text
Use only the supplied evidence. Return one JSON object matching the schema.
Every factual claim and event must cite source_ids from the evidence.
Do not treat prior AI text as evidence. State uncertainty when evidence is silent.
Do not add a source merely because its scope was enabled.
```

Insufficient evidence returns a structured response with a `What We Don't Know` section. Provider failure returns the retrieved source list, `evidence-only`, and a recoverable message. Malformed JSON is also evidence-only and is audited as `invalid_structured_response`.

- [ ] **Step 4: Run service, retrieval, validation, and existing AI tests**

Run: `cd backend && pytest tests/research tests/ai/test_grounded_answer.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the coordinator**

```bash
git add backend/app/research/service.py backend/tests/research/test_service.py
git commit -m "feat: orchestrate grounded scripture research"
```

## Task 5: Add the Reviewed Event Catalog and Between-Events Resolution

**Files:**
- Create: `backend/app/research/event_catalog.py`
- Create: `backend/tests/research/test_events.py`

- [ ] **Step 1: Write failing event tests**

```python
def test_catalog_events_resolve_to_existing_library_passages(session):
    events = list_events(session, query='Eden')
    assert events[0].id == 'eden-expulsion'
    assert events[0].source_ids


def test_between_events_builds_only_verified_ordered_events(session):
    timeline = resolve_between_events(session, 'eden-expulsion', 'abel-killed')
    assert [event.id for event in timeline] == [
        'eden-expulsion', 'cain-born', 'abel-born', 'offerings', 'abel-killed'
    ]
    assert all(event.source_ids for event in timeline)
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend && pytest tests/research/test_events.py -q`

Expected: FAIL because the catalog is missing.

- [ ] **Step 3: Implement reviewed event definitions**

Create immutable definitions for the release-one event ranges, including Eden, Expulsion, Cain Born, Abel Born, Offerings, and Abel Killed. Each definition contains ID, title, description, canonical book/chapter/verse range, people keys, place keys, and ordering group. At runtime, resolve every definition against `biblical_texts`; omit any definition with no verified passage rows. This is a reviewed index over library evidence, not an alternate scripture store.

Implement search by title/aliases and range validation that rejects FROM occurring after TO or events from incompatible ordering groups.

- [ ] **Step 4: Run event and retrieval tests**

Run: `cd backend && pytest tests/research/test_events.py tests/research/test_retrieval.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the verified event index**

```bash
git add backend/app/research/event_catalog.py backend/tests/research/test_events.py
git commit -m "feat: add verified biblical event index"
```

## Task 6: Persist Authenticated Research Trails

**Files:**
- Create: `backend/app/research/models.py`
- Create: `backend/alembic/versions/0011_research_trail.py`
- Create: `backend/tests/research/test_trail.py`
- Modify: `backend/app/application.py`

- [ ] **Step 1: Write failing model and permission tests**

Test that an authenticated user can create a root node and child node, that a child references the same owner/session, and that another user receives 404 for the node. Test that stored settings and response snapshots round-trip as JSON.

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend && pytest tests/research/test_trail.py -q`

Expected: FAIL because the research-node table is missing.

- [ ] **Step 3: Add the model and migration**

Create `ResearchNode` with UUID ID, owner ID, optional study ID, optional parent ID, question, mode, source scopes JSON, depth, response snapshot JSON, created/updated timestamps, and indexes on owner/updated and parent. Use `ondelete='CASCADE'` for owner and parent, and `ondelete='SET NULL'` for optional study linkage.

The migration revision is `0011_research_trail` and `down_revision = '0010_merge_platform_composite'`. Import the model before `Base.metadata.create_all` in application startup following existing model-registration patterns.

- [ ] **Step 4: Run migration and model tests**

Run: `cd backend && alembic upgrade head && pytest tests/research/test_trail.py -q`

Expected: migration succeeds and tests PASS.

- [ ] **Step 5: Commit trail persistence**

```bash
git add backend/app/research/models.py backend/alembic/versions/0011_research_trail.py backend/app/application.py backend/tests/research/test_trail.py
git commit -m "feat: persist scripture research trails"
```

## Task 7: Expose Research API Routes

**Files:**
- Create: `backend/app/research/router.py`
- Create: `backend/tests/research/test_routes.py`
- Modify: `backend/app/api/router.py`

- [ ] **Step 1: Write failing route tests**

Cover:

```python
def test_query_defaults_are_returned(client):
    data = client.post('/api/v1/research/query', json={'question': 'Genesis 4:1'}).json()
    assert data['settings'] == {
        'source_scopes': ['biblical-canon'], 'depth': 'deep-research'
    }


def test_events_endpoint_returns_only_resolved_events(client):
    data = client.get('/api/v1/research/events', params={'q': 'Eden'}).json()
    assert data['events'][0]['source_ids']


def test_follow_up_cannot_use_another_users_parent(client, users):
    response = client.post('/api/v1/research/query', headers=users.second,
        json={'question': 'Compare it', 'parent_node_id': str(users.first_node)})
    assert response.status_code == 404
```

- [ ] **Step 2: Run and confirm 404 failures**

Run: `cd backend && pytest tests/research/test_routes.py -q`

Expected: FAIL because `/api/v1/research` is not mounted.

- [ ] **Step 3: Implement and mount routes**

Add:

- `POST /research/query` with the existing AI rate-limit dependency and optional authentication;
- `GET /research/events?q=` with bounded query length;
- `GET /research/trail/{node_id}` requiring authentication and ownership.

When authenticated, persist the validated response and return `trail_node`. For guest requests, accept no server parent ID and let the frontend provide a compact `conversation_context` field restricted to prior validated entity names and source references; never accept prior prose as evidence.

- [ ] **Step 4: Run route, security, and legacy AI tests**

Run: `cd backend && pytest tests/research/test_routes.py tests/security/test_security_controls.py tests/ai/test_grounded_answer.py -q`

Expected: PASS; `/chat/ask` remains compatible.

- [ ] **Step 5: Commit the API boundary**

```bash
git add backend/app/research/router.py backend/app/api/router.py backend/tests/research/test_routes.py
git commit -m "feat: expose grounded research api"
```

## Task 8: Add the Frontend API and Response Model

**Files:**
- Create: `frontend/src/scriptureResearch/researchModel.js`
- Create: `frontend/src/scriptureResearch/researchApi.js`
- Create: `frontend/src/scriptureResearch/researchApi.test.js`

- [ ] **Step 1: Write failing API/model tests**

```javascript
it('sends the approved defaults', async () => {
  fetch.mockResolvedValue(jsonResponse(validResponse))
  await runResearch({ question: 'What happened between Eden and Abel?' })
  expect(fetch).toHaveBeenCalledWith('/api/v1/research/query', expect.objectContaining({
    method: 'POST',
    body: JSON.stringify(expect.objectContaining({
      source_scopes: ['biblical-canon'], depth: 'deep-research',
    })),
  }))
})

it('rejects a response whose claim references a missing source', () => {
  expect(() => normalizeResearchResponse(responseWithMissingSource)).toThrow(/unknown source/i)
})
```

- [ ] **Step 2: Run and confirm module failure**

Run: `cd frontend && npm test -- --run src/scriptureResearch/researchApi.test.js`

Expected: FAIL because the files do not exist.

- [ ] **Step 3: Implement constants, normalization, and API calls**

Export immutable `SOURCE_SCOPES`, `RESEARCH_DEPTHS`, `RESEARCH_MODES`, `DEFAULT_RESEARCH_SETTINGS`, and `EMPTY_RESEARCH_SESSION`. Normalize snake_case API fields once at the boundary while keeping stable source IDs. Validate required arrays and all claim/event source IDs before returning data to components.

Use the shared API client rather than direct `fetch`:

```javascript
export function runResearch(input, { signal } = {}) {
  return api.post('/research/query', toApiRequest(input), { signal })
    .then(normalizeResearchResponse)
}

export function searchResearchEvents(query, { signal } = {}) {
  return api.get(`/research/events?q=${encodeURIComponent(query)}`, { signal })
}
```

Guest trail storage uses one versioned local-storage key and stores only validated normalized responses.

- [ ] **Step 4: Run the API/model tests**

Run: `cd frontend && npm test -- --run src/scriptureResearch/researchApi.test.js src/api/client.test.js`

Expected: PASS.

- [ ] **Step 5: Commit the frontend boundary**

```bash
git add frontend/src/scriptureResearch/researchModel.js frontend/src/scriptureResearch/researchApi.js frontend/src/scriptureResearch/researchApi.test.js
git commit -m "feat: add scripture research client model"
```

## Task 9: Build the Composer, Mode Toolbar, and Empty State

**Files:**
- Create: `frontend/src/scriptureResearch/ResearchComposer.jsx`
- Create: `frontend/src/scriptureResearch/ResearchModeToolbar.jsx`
- Create: `frontend/src/scriptureResearch/BetweenEventsComposer.jsx`
- Create: `frontend/src/scriptureResearch/ResearchComposer.test.jsx`

- [ ] **Step 1: Write failing interaction tests**

Test that Biblical Canon and Deep Research start selected, source chips are multi-select, All Sources is exclusive, Enter submits, Shift+Enter does not submit, the mode toolbar does not navigate, and Between Events requires distinct ordered FROM/TO selections.

```javascript
await user.type(screen.getByLabelText(/research question/i), 'Genesis 4{Enter}')
expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
  question: 'Genesis 4', sourceScopes: ['biblical-canon'], depth: 'deep-research',
}))
```

- [ ] **Step 2: Run and confirm component failures**

Run: `cd frontend && npm test -- --run src/scriptureResearch/ResearchComposer.test.jsx`

Expected: FAIL because the components are missing.

- [ ] **Step 3: Implement accessible controls**

Use native `<textarea>`, `<button aria-pressed>`, and a toolbar-labelled group. The microphone button is present but disabled with accessible text “Voice research is unavailable” when provider health reports no transcription provider. Do not simulate recording.

BetweenEventsComposer uses two labelled comboboxes backed by `searchResearchEvents`; it exposes Build Timeline only when valid choices exist. Compact examples call `onExample(question, settings)`.

- [ ] **Step 4: Run composer tests**

Run: `cd frontend && npm test -- --run src/scriptureResearch/ResearchComposer.test.jsx`

Expected: PASS.

- [ ] **Step 5: Commit composer controls**

```bash
git add frontend/src/scriptureResearch/ResearchComposer.jsx frontend/src/scriptureResearch/ResearchModeToolbar.jsx frontend/src/scriptureResearch/BetweenEventsComposer.jsx frontend/src/scriptureResearch/ResearchComposer.test.jsx
git commit -m "feat: build research composer controls"
```

## Task 10: Render the Structured Workspace and Citation Drawer

**Files:**
- Create: `frontend/src/scriptureResearch/ResearchWorkspace.jsx`
- Create: `frontend/src/scriptureResearch/ResearchTimeline.jsx`
- Create: `frontend/src/scriptureResearch/ResearchInspector.jsx`
- Create: `frontend/src/scriptureResearch/CitationDrawer.jsx`
- Create: `frontend/src/scriptureResearch/ResearchTrail.jsx`
- Create: `frontend/src/scriptureResearch/ResearchWorkspace.test.jsx`

- [ ] **Step 1: Write failing rendering and dialog tests**

Use one normalized Eden-to-Abel fixture. Assert Overview, Timeline, Canonical Account, What We Don't Know, Sources, and People render; absent ancient accounts do not create an empty heading; all citation buttons open a dialog containing provenance; Escape closes it and focus returns to the citation; clicking a trail node calls `onSelectNode`.

- [ ] **Step 2: Run and confirm failures**

Run: `cd frontend && npm test -- --run src/scriptureResearch/ResearchWorkspace.test.jsx`

Expected: FAIL because the components are missing.

- [ ] **Step 3: Implement focused renderers**

`ResearchWorkspace` selects sections from typed response fields and passes source lookup to child components. `ResearchTimeline` uses an ordered list and buttons for events. `ResearchInspector` renders cards only for non-empty data. `CitationDrawer` uses `<dialog>` where supported, a labelled title, Escape/close behavior, focus restoration, and `onOpenTarget` for reader navigation. `ResearchTrail` renders the active ancestry plus available child branches.

Never parse Markdown into HTML. Render the validated claim strings as text.

- [ ] **Step 4: Run workspace tests**

Run: `cd frontend && npm test -- --run src/scriptureResearch/ResearchWorkspace.test.jsx`

Expected: PASS.

- [ ] **Step 5: Commit the result workspace**

```bash
git add frontend/src/scriptureResearch/ResearchWorkspace.jsx frontend/src/scriptureResearch/ResearchTimeline.jsx frontend/src/scriptureResearch/ResearchInspector.jsx frontend/src/scriptureResearch/CitationDrawer.jsx frontend/src/scriptureResearch/ResearchTrail.jsx frontend/src/scriptureResearch/ResearchWorkspace.test.jsx
git commit -m "feat: render grounded research workspace"
```

## Task 11: Integrate Page State, Loading, Save, Share, and Follow-Ups

**Files:**
- Create: `frontend/src/scriptureResearch/ScriptureResearchPage.jsx`
- Create: `frontend/src/scriptureResearch/ResearchLoadingState.jsx`
- Create: `frontend/src/scriptureResearch/ScriptureResearchPage.test.jsx`
- Modify: `frontend/src/components/AskTheBible.jsx`

- [ ] **Step 1: Write failing page integration tests**

Mock `runResearch` and authentication. Test empty-first behavior, compact example submission, loading stage announcements, successful rendering, retry preserving the question/settings, evidence-only rendering, insufficient-evidence rendering, follow-up parent context, guest trail restoration, authenticated Save through existing `/studies`, Share modal payload, and New Research reset.

- [ ] **Step 2: Run and confirm failure**

Run: `cd frontend && npm test -- --run src/scriptureResearch/ScriptureResearchPage.test.jsx`

Expected: FAIL because the page is missing.

- [ ] **Step 3: Implement page orchestration**

Use an abort controller per query. Keep state transitions explicit: `empty`, `loading`, `success`, `insufficient`, `evidence-only`, and `error`. Loading stage text advances only through operations the client knows were requested; it must not claim external searching. Follow-ups submit `parentNodeId` for authenticated sessions and compact validated context for guests.

Reuse `ShareStudyModal`, `api.post('/studies')`, message/source persistence, `useAuth`, and `onPageChange`. Export the new page through the compatibility file:

```javascript
export { default } from '../scriptureResearch/ScriptureResearchPage'
```

Keep the legacy `AskTheBible.css` file unmodified and unimported until final cleanup.

- [ ] **Step 4: Run page, share, saved-study, and route tests**

Run: `cd frontend && npm test -- --run src/scriptureResearch/ScriptureResearchPage.test.jsx src/components/ShareStudyModal.test.jsx src/components/SavedStudies.test.jsx src/routing/pageRoutes.test.js`

Expected: PASS.

- [ ] **Step 5: Commit the page integration**

```bash
git add frontend/src/scriptureResearch/ScriptureResearchPage.jsx frontend/src/scriptureResearch/ResearchLoadingState.jsx frontend/src/scriptureResearch/ScriptureResearchPage.test.jsx frontend/src/components/AskTheBible.jsx
git commit -m "feat: integrate scripture research page"
```

## Task 12: Apply the Approved Visual System and Responsive Behavior

**Files:**
- Create: `frontend/src/scriptureResearch/ScriptureResearchPage.css`
- Modify: `frontend/src/scriptureResearch/ScriptureResearchPage.jsx`
- Modify: `frontend/src/scriptureResearch/ResearchComposer.jsx`
- Modify: `frontend/src/scriptureResearch/ResearchWorkspace.jsx`

- [ ] **Step 1: Add a failing responsive accessibility E2E test**

In `frontend/e2e/scripture-research-ai.spec.js`, mock `/api/v1/research/query`, open `/#aistudy`, verify one `h1`, visible composer, and no horizontal overflow at 1440×1000 and 390×844. Run Axe and assert no serious/critical violations. Verify `prefers-reduced-motion: reduce` produces no continuously animated loading element.

- [ ] **Step 2: Run and confirm visual/layout failure**

Run: `cd frontend && npx playwright test e2e/scripture-research-ai.spec.js --project=chromium`

Expected: FAIL because the stylesheet and test route mock are incomplete.

- [ ] **Step 3: Implement the approved CSS**

Use page-scoped custom properties for charcoal layers, ivory text, antique gold, purple AI, muted text, borders, focus, and status colors. Implement:

- centered `max-width: 1560px`;
- composer as the primary focal surface;
- compact wrap-safe chips;
- six-item toolbar that becomes a horizontally scrollable tablist only between tablet breakpoints and a 2-column grid on narrow mobile;
- desktop `minmax(0, 2fr) minmax(20rem, 1fr)` workspace;
- single-column mobile order from the approved design;
- 44px targets, high-contrast `:focus-visible`, readable line lengths, and no clipped text;
- `@media (prefers-reduced-motion: reduce)` disabling shimmer, pulse, smooth scroll, and staged entrances.

Use the existing application font stack and tokens where they meet contrast; introduce page-local values only where necessary to match the approved reference.

- [ ] **Step 4: Run E2E and component tests**

Run: `cd frontend && npx playwright test e2e/scripture-research-ai.spec.js --project=chromium && npm test -- --run src/scriptureResearch`

Expected: PASS.

- [ ] **Step 5: Commit the visual system**

```bash
git add frontend/src/scriptureResearch/ScriptureResearchPage.css frontend/src/scriptureResearch/*.jsx frontend/e2e/scripture-research-ai.spec.js
git commit -m "feat: style responsive scripture research workspace"
```

## Task 13: Rename Navigation Without Breaking the Route

**Files:**
- Modify: `frontend/src/routing/pageRoutes.js`
- Modify: `frontend/src/routing/pageRoutes.test.js`
- Modify: `frontend/src/components/Navigation.jsx`
- Modify: `frontend/src/components/Navigation.test.jsx`
- Modify: `frontend/src/reader/studyToolRegistry.js`
- Modify: `frontend/src/reader/StudyTools.test.jsx`

- [ ] **Step 1: Update tests first**

Change expected visible labels from Ask the Bible to Scripture Research AI while keeping:

```javascript
expect(pageFromHash('#aistudy')).toBe('chat')
expect(hashForPage('chat')).toBe('#aistudy')
```

- [ ] **Step 2: Run and confirm label failures**

Run: `cd frontend && npm test -- --run src/routing/pageRoutes.test.js src/components/Navigation.test.jsx src/reader/StudyTools.test.jsx`

Expected: FAIL on the old label.

- [ ] **Step 3: Update visible labels only**

Rename the navigation item, route title, and reader tool label. Do not rename the internal page key or hash in this release.

- [ ] **Step 4: Run the navigation tests**

Run: `cd frontend && npm test -- --run src/routing/pageRoutes.test.js src/components/Navigation.test.jsx src/reader/StudyTools.test.jsx`

Expected: PASS.

- [ ] **Step 5: Commit route-compatible naming**

```bash
git add frontend/src/routing frontend/src/components/Navigation.jsx frontend/src/components/Navigation.test.jsx frontend/src/reader/studyToolRegistry.js frontend/src/reader/StudyTools.test.jsx
git commit -m "feat: rename ai study navigation"
```

## Task 14: Full Verification, Visual Review, and Cleanup

**Files:**
- Delete: `frontend/src/components/AskTheBible.css` only after `rg` confirms no imports.
- Modify: any files from Tasks 1–13 only when a verification failure requires a focused correction.

- [ ] **Step 1: Run backend focused and full tests**

Run: `cd backend && pytest tests/research tests/ai tests/studies tests/security -q`

Expected: PASS.

Run: `cd backend && pytest -q`

Expected: PASS, or record pre-existing unrelated failures before changing feature code.

- [ ] **Step 2: Run frontend unit, lint, and build checks**

Run: `cd frontend && npm test -- --run`

Expected: PASS.

Run: `cd frontend && npm run lint && npm run build`

Expected: PASS with no new warnings.

- [ ] **Step 3: Run relevant end-to-end suites**

Run: `cd frontend && npx playwright test e2e/scripture-research-ai.spec.js e2e/auth-study-sharing.spec.js e2e/scripture-reader-accessibility.spec.js e2e/compare-scripture.spec.js --project=chromium`

Expected: PASS.

- [ ] **Step 4: Run the app and inspect the actual page**

Start the configured local stack using the repository’s documented command. Inspect `http://localhost:5001/#aistudy` at 1440×1000, 1024×900, and 390×844. Compare with the supplied reference and correct only concrete issues in hierarchy, spacing, typography, alignment, border contrast, overflow, focus, and modal positioning. Verify the browser console has no new errors or warnings.

- [ ] **Step 5: Exercise the acceptance flow manually**

Verify:

1. empty-first state;
2. Eden-to-Abel example;
3. Biblical Canon-only response contains Genesis 2–4 and no forced ancient source;
4. scope and depth changes reach the API;
5. What Happened Between? FROM/TO flow;
6. citation drawer and Open Full Text;
7. follow-up context and trail return;
8. insufficient evidence;
9. provider failure/evidence-only response;
10. Retry, Save, Share, and New Research;
11. keyboard-only use and reduced motion;
12. mobile reading order.

- [ ] **Step 6: Remove the unused legacy stylesheet**

Run: `rg -n "AskTheBible.css" frontend/src`

Expected: no matches. Then delete only `frontend/src/components/AskTheBible.css` and rerun `npm run build`.

- [ ] **Step 7: Commit verified cleanup**

```bash
git add -A frontend/src/components/AskTheBible.css frontend/src/scriptureResearch backend/app/research frontend/e2e/scripture-research-ai.spec.js
git commit -m "test: verify scripture research grounded core"
```

## Plan Self-Review Results

- **Spec coverage:** Contracts, scoped retrieval, claim validation, source labeling, evidence-only fallback, insufficient evidence, event workflow, research trail, follow-up memory, save/share reuse, responsive design, accessibility, loading, tests, and visual inspection each map to an explicit task.
- **Scope control:** External retrieval and five dedicated specialist modes remain deferred. Their visible release-one behavior is explicitly limited to grounded presets.
- **Type consistency:** Request fields use `question`, `session_id`, `parent_node_id`, `mode`, `source_scopes`, `depth`, and `mode_parameters` on the API; the frontend converts them at one boundary. Source IDs are stable strings throughout.
- **Placeholder scan:** The plan contains no TBD/TODO/FIXME instructions. Deferred work is deliberately excluded rather than left incomplete inside a task.
- **Safety:** The legacy `/chat/ask` endpoint and `#aistudy` hash remain intact until the new API and page pass focused tests. Existing dirty workspace files are outside every planned commit.

