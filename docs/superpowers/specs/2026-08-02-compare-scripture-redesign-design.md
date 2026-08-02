# Compare Scripture Redesign

## Goal

Redesign the existing **Compare Scripture** page to match the approved dark comparison-workspace mockup while retaining the app's current global navigation. The page must make side-by-side scripture comparison the dominant task and remain understandable and readable for users from approximately age 13 through age 70.

## Scope

This redesign applies only to the `textual` / `#compare` destination. The existing Scripture Reader and the app-wide navigation remain unchanged.

The redesign preserves the current Compare Scripture capabilities:

- passage selection by book, chapter, and verse;
- single-verse and aligned-chapter views;
- translation selection and base-reference selection;
- difference highlighting;
- bookmarks, notes, sharing, and Study Tools;
- live data from the existing biblical-text APIs.

## Visual Direction

The workspace uses a refined, scholarly dark theme inspired by illuminated manuscripts and research desks rather than a generic dashboard.

- Gold represents primary actions and active navigation within the workspace.
- Purple identifies translations and AI-assisted tools.
- Cyan identifies textual differences.
- Amber identifies unavailable or incomplete source text.
- Red is reserved for actual errors.
- Neutral slate surfaces and high-contrast ivory text support long reading sessions.

Scripture uses a readable serif face at 24–28 pixels with generous line height. Interface text uses a clear humanist sans-serif face. Supporting information remains at least 13–14 pixels with comfortable contrast.

## Desktop Layout

Below the existing app navigation, the page contains:

1. A compact page introduction and grouped passage toolbar.
2. A three-area workspace:
   - a 260–280 pixel translation selector;
   - a flexible, visually dominant comparison area;
   - an optional 360 pixel Study Tools drawer.
3. A compact source/difference note beneath the comparison workspace.

The Study Tools drawer is closed by default. Opening it must not permanently compress the comparison view; it appears as a right-side overlay drawer on narrower desktops and may occupy the third grid column only when sufficient width is available.

## Passage Toolbar

Controls are grouped by task:

- **Passage:** book, chapter, and verse.
- **View:** Verse or Chapter.
- **Comparison:** base reference and Highlight Differences.
- **Action:** Open Study Tools.

The Study Tools close control lives inside its drawer. All labels remain visible rather than depending on icons or tooltips.

## Translation Selector

The selector uses compact checkbox rows instead of large filled cards. Each row shows:

- selection state;
- short code;
- full translation name;
- tradition and date or language where available.

Filters include All, Ethiopian, Protestant, Catholic, and Original Languages. Search filters by code, name, tradition, and language.

The initial comparison contains exactly two sources:

1. Ethiopian Orthodox Critical Text (`ETH81`)
2. King James Version (`KJV`)

Users may add up to two more sources, for a maximum of four. The selector states the current count and remaining capacity. At least one translation must remain selected. If the base translation is removed, the first remaining translation becomes the base.

## Comparison Area

The comparison area begins with a beginner-friendly summary for the selected reference. It states the comparison count and offers three clear actions:

- Show Differences;
- Explain This Verse;
- View Original Words.

Translation cards share a consistent structure:

1. sticky header with code, name, and source tradition;
2. passage reference;
3. scripture text or a compact status state;
4. difference count and notes action;
5. concise source/tradition footer.

Verse cards display in a responsive grid. Chapter mode displays aligned verse rows by translation. Cards scroll internally only when required, and card headers remain visible.

## Availability and Error States

The UI distinguishes four states:

- **Not part of selected canon:** the book does not belong to that tradition.
- **Translation unavailable:** the selected source does not provide the passage.
- **Database text missing:** the source belongs to the canon, but the local record has not been added.
- **Loading or network error:** the request failed or connectivity is unavailable.

Missing Ethiopian text uses a compact amber notice:

> Text unavailable
> This passage has not yet been added to the Ethiopian Critical Text database.

It offers **Learn more** and **Choose another source**. Red styling is used only for genuine request or application errors.

## Study Tools

Study Tools uses one primary tool row:

- Insights;
- Cross-References;
- Words;
- Notes.

The drawer has a visible title and close button. Empty states are concise and always offer a useful next action. A single persistent **Ask Study Assistant** button appears at the bottom. Existing note persistence, sharing, bookmark behavior, and authenticated study features remain connected.

## Responsive Behavior

- At large desktop widths, the translation selector and comparison area remain visible; Study Tools can occupy a third column when space permits.
- At laptop and tablet widths, Study Tools overlays from the right and the translation selector becomes a dismissible drawer.
- On phones, passage controls stack, translation cards become a single vertical reading stream, and both auxiliary panels open as full-height sheets.
- Interactive targets are at least 44 by 44 pixels. No essential action relies on hover.

## Component Boundaries

The current large workspace will be divided into focused components:

- `ComparisonToolbar`: passage, view, base-reference, and difference controls.
- `TranslationSelector`: search, filters, compact rows, and selection limit.
- `ComparisonSummary`: beginner summary and primary study actions.
- `TranslationComparisonCard`: consistent source header, scripture/status body, and footer.
- `ComparisonStudyDrawer`: simplified Study Tools shell and tabs.
- `TextualComparisonWorkspace`: data orchestration, selection state, notes, and layout composition.

Shared metadata and pure comparison helpers move into small modules so behavior can be tested without rendering the entire page.

## Data Flow

1. Load available books from `/api/biblical-texts/available-books`.
2. Load the selected chapter from `/api/biblical-texts/chapter-content`.
3. Derive available verses and source availability from the returned rows.
4. Load verse details only when a study tool requires them.
5. Derive comparison highlighting and summary data from the selected rows and base translation.
6. Preserve local note and bookmark storage under the existing keys.

Requests must ignore stale responses when the user changes passages quickly. Loading, empty, offline, and error states remain explicit.

## Accessibility

- Every input has a visible label and programmatic accessible name.
- Drawers trap focus, close with Escape, restore focus to their trigger, and expose modal semantics where appropriate.
- Active tabs and toggles expose their selected or pressed state.
- Color is never the only indicator of selection, differences, warnings, or errors.
- Scripture, secondary text, borders, and focus rings meet comfortable contrast targets in dark mode.
- Keyboard order follows passage controls, translations, comparison cards, then Study Tools.
- Motion respects `prefers-reduced-motion`.

## Testing and Acceptance

Unit and component tests must cover:

- two default translations and a four-translation maximum;
- removing a base translation;
- translation search and category filters;
- accurate canon, unavailable, missing-record, loading, and error messages;
- verse/chapter switching and stale-request protection;
- Study Tools closed by default, focus management, and keyboard dismissal;
- note, bookmark, and sharing regression behavior.

Browser tests must verify desktop, tablet, and phone layouts; keyboard-only use; readable zoom behavior; no unintended horizontal page scrolling; visible focus; Ethiopian and KJV data; and automated accessibility checks.

The redesign is complete when the `#compare` page visually follows the approved mockup, retains its existing working capabilities, and passes the current test suite plus the new comparison-page tests.
