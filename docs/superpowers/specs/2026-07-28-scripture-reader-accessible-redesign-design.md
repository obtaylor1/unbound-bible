# Accessible Scripture Reader Redesign

Date: 2026-07-28
Status: Approved design; implementation not started

## Purpose

Redesign the Scripture Reader first and use it as the reference implementation for a later app-wide design system. The experience must be immediately understandable and comfortably readable for people from approximately age 13 through age 70, without removing the advanced research capabilities that distinguish The Unbound Bible.

The approved direction is a calm, reading-first interface with the app's existing midnight navy, violet, teal, and gold identity refined through consistent semantic roles and accessible contrast. Both light and dark modes are required.

## Evidence from the current reader

The live review found:

- The desktop view presents three competing regions at once: canon/book navigation, the reader/dashboard, and AI/study panels.
- Major navigation uses 13px text and roughly 35px targets.
- Many controls and filters use 11–12px text with targets as small as 24–37px.
- At a 390px viewport, desktop panels overlap the content instead of becoming mobile navigation or drawers.
- Several important actions rely on icons, abbreviations, or unlabeled window-like controls.
- The reader begins with canon cards, statistics, progress, AI content, and study tools rather than Scripture.
- `AncientTexts.jsx` and `AncientTexts.css` each contain several thousand lines and combine navigation, reading, study, notes, comparison, and assistant responsibilities. The redesign needs bounded components instead of adding more conditions to those files.

## Goals

1. Make Scripture the dominant and default experience.
2. Make every important control understandable without prior product knowledge.
3. Support comfortable long-form reading and user-controlled text size.
4. Preserve advanced comparison, language, context, note, audit, and AI tools through progressive disclosure.
5. Provide equivalent, non-overlapping desktop and mobile experiences.
6. Meet WCAG 2.2 AA requirements for contrast, focus, navigation, labels, and target size.
7. Establish reusable tokens and primitives that can later be adopted by the rest of the app.

## Non-goals

- Redesigning every app page in this phase.
- Changing biblical text, canon membership, authentication, study, or AI backend contracts unless a UI defect exposes a separate API bug.
- Removing advanced study capabilities.
- Introducing decorative animation, gamification, or a new brand identity.

## Visual system

### Color roles

The palette follows a 60–30–10 distribution: neutral reading canvas, structural surfaces, then restrained semantic accents.

| Role | Dark mode | Light mode | Use |
| --- | --- | --- | --- |
| Canvas | `#070A12` | `#F7F5FC` | Primary reading background |
| Surface | `#0E1422` | `#FFFFFF` | Navigation and drawers |
| Elevated surface | `#161D2E` | `#F1EEF8` | Cards, controls, selected verse tools |
| Primary text | `#F5F7FB` | `#171325` | Headings and controls |
| Reading text | `#EDF0F7` | `#272233` | Scripture |
| Secondary text | `#AEB8CA` | `#565064` | Supporting descriptions |
| Primary violet | `#6D3FE0` | `#6D3FE0` | Primary actions and selected navigation |
| Violet accent | `#B49CFF` | `#5426BB` | Focus, verse numbers, links |
| Scholar teal | `#2DD4BF` | `#086F65` | Context, language, and verified evidence |
| Illumination gold | `#F6C453` | `#7A5200` | Highlights, bookmarks, special emphasis |
| Alert rose | `#FB7185` | a contrast-checked dark rose | Errors and destructive warnings only |

Violet must not be applied as a glow to every surface. Teal communicates contextual or scholarly information. Gold communicates user emphasis or a special textual detail. Rose is reserved for failure and destructive actions. No state may rely on color alone.

### Typography

- Scripture: a readable book serif such as Source Serif 4, with local or privacy-safe delivery and suitable fallbacks.
- Interface: Atkinson Hyperlegible or an equivalently tested legible sans-serif.
- Default Scripture size: 21px.
- User-selectable Scripture sizes: 18px, 21px, 24px, 27px, and 30px.
- Scripture line height: approximately 1.75.
- Reading measure: approximately 65–75 characters, normally a 680–760px column.
- Minimum normal interface text: 16px.
- Supporting text may use 14px only when it is not required to operate the interface.
- User theme and reading-size preferences persist locally and should later sync to an account without changing the component API.

## Information architecture

### Default reader

The default page contains:

1. Global top navigation.
2. A compact passage toolbar.
3. One centered Scripture column.
4. Previous and Next chapter controls.
5. A mobile bottom navigation bar when applicable.

Canon summaries, reading statistics, AI summaries, and progress dashboards do not appear before the biblical text. They remain available from clearly labeled secondary destinations.

### Top navigation

The top navigation contains only:

- The Unbound Bible brand/home action
- Books
- Current passage, for example “Genesis 1”
- Current translation, for example “KJV”
- Text size
- Theme
- Study Tools
- Account access where space allows

Words accompany meaningful icons. The current fake minimize, maximize, and close controls are removed.

### Book and passage navigation

On desktop, **Books** opens a searchable left drawer. The drawer supports:

- Canon selection with full names
- Search by book
- Testament and collection filtering with full labels
- Book selection followed by a compact chapter grid
- A clear Close button and Escape support

On mobile, Books opens as a full-screen picker. The user completes book and chapter selection without interacting with a desktop sidebar squeezed into the viewport.

The passage toolbar remains near the reading position and provides labeled Previous chapter and Next chapter actions.

### Study tools

Study Tools opens a right drawer on desktop and a bottom sheet on mobile. Its first level contains plainly labeled destinations:

- Context
- Compare translations
- Original languages
- Cross-references
- Add or view notes
- Highlights and bookmarks
- Ask the Bible
- Decolonial audit

Selecting a verse establishes the current study target and makes verse-specific actions available. The reader remains visible when desktop space allows, but study tools never permanently reduce the mobile reading width.

## Responsive behavior

### Desktop, 1024px and wider

- Centered reading column.
- Books and Study Tools are temporary drawers.
- Only one major drawer is open at a time by default.
- The reader remains readable when a drawer is open.

### Tablet, 768–1023px

- Compact top navigation.
- Drawers overlay rather than squeeze the reading column.
- Optional labels may move into a More menu, but essential controls retain text.

### Mobile, below 768px

- No persistent desktop sidebars.
- Compact top bar plus passage toolbar.
- Bottom navigation: Home, Bible, Search, Library, More.
- Books uses a full-screen picker.
- Study Tools uses a bottom sheet with a visible drag handle and Close button.
- Safe-area padding is respected.
- Nothing overlays or obscures Scripture after a sheet or picker closes.

## Component architecture

The implementation should extract responsibilities from the monolithic reader into focused units:

- `ScriptureReaderPage`: route-level orchestration and loading/error boundaries.
- `ReaderHeader`: brand and global reader actions.
- `PassageToolbar`: book, chapter, translation, text size, and chapter navigation.
- `ScripturePane`: chapter heading and verse list only.
- `Verse`: semantic verse content, selection, and focus behavior.
- `BookPicker`: canon, search, book, and chapter selection.
- `StudyToolsLauncher`: entry point and currently selected verse summary.
- `StudyToolsDrawer`: desktop container for study modules.
- `StudyToolsSheet`: mobile container sharing the same module definitions.
- `ReaderPreferences`: theme, text size, line spacing, and optional reading width.
- `ReaderBottomNavigation`: mobile destinations.
- `ReaderStatus`: loading, empty, offline, and recoverable error messages.

Study modules remain separate components and receive a passage/verse reference rather than reading directly from page-wide mutable state.

## State and data flow

1. The route resolves the selected book, chapter, translation, and optional verse from the URL.
2. The page requests chapter content through the existing biblical-text API.
3. `ScriptureReaderPage` owns the request state and passes normalized chapter data to `ScripturePane`.
4. Selecting a verse updates an explicit `selectedVerse` state and, where useful, the URL fragment or query without forcing a full chapter reload.
5. BookPicker changes route state; the route change initiates the next chapter request.
6. A study module receives the selected reference and loads only the data it requires.
7. Theme and reading preferences come from a small preferences provider backed by local storage.

The page must not encode every book and chapter as hundreds of options in one always-mounted select. Book and chapter navigation should render the focused list or grid needed by the picker.

## Interaction and accessibility rules

- Interactive targets are at least 44 by 44 CSS pixels, with 48px preferred.
- Every control has a visible label or an unambiguous accessible name.
- Abbreviations are expanded in primary navigation: “Old Testament,” not only “OT”; “Apocrypha,” not “Apoc.”
- Logical heading order and landmarks are preserved.
- Keyboard focus is visible in light and dark modes.
- Drawers and sheets move focus inside on open, restore focus on close, close with Escape, and do not trap users after dismissal.
- Verse selection is available by keyboard and announced to assistive technology.
- Hover never reveals the only path to an action.
- Motion is brief and functional and respects `prefers-reduced-motion`.
- Contrast is verified against WCAG 2.2 AA in both themes.
- The interface works at 200% browser zoom without horizontal page scrolling or obscured controls.
- A short, dismissible first-use guide may explain: Choose a book, Read, Select a verse for study tools.

## Loading, empty, offline, and error states

- Initial chapter loading uses a reading-shaped skeleton and a clear “Loading Genesis 1…” status.
- Empty chapter results explain that no text is currently available and offer a return to Books.
- Network errors say the passage could not be loaded, preserve the selected reference, and provide Retry.
- Offline state distinguishes cached available text from unavailable remote study tools.
- Study-module failures remain within the drawer or sheet and never replace or erase loaded Scripture.
- AI and analysis tools must state when evidence or provider access is unavailable; they must not display fabricated fallback findings.
- Lazy route failures are caught by a route-level error boundary with Reload and Return Home actions instead of a blank page.

## Testing and acceptance criteria

### Automated component and integration tests

- Book and chapter selection updates the route and loads the expected chapter.
- Text-size and theme preferences persist.
- Opening and closing desktop drawers restores focus.
- Mobile picker and study sheet have correct labels and focus behavior.
- Loading, empty, offline, request-error, and lazy-import-error states render actionable messages.
- Verse selection makes study actions available without losing the reading position.
- Existing notes, comparison, context, sharing, and AI entry points remain reachable.

### Accessibility checks

- Automated axe checks on the default reader, Books picker, and Study Tools in both themes.
- Keyboard-only completion of book selection, chapter navigation, verse selection, note entry, and drawer dismissal.
- Screen-reader spot checks for landmarks, headings, verse labels, status announcements, and dialogs.
- Contrast validation for all semantic token pairs.
- 200% zoom and large-text checks.

### Responsive browser checks

Test at minimum:

- 1440 × 900 desktop
- 1024 × 768 tablet/compact desktop
- 768 × 1024 tablet portrait
- 390 × 844 phone
- 320 × 568 small phone

At every size:

- No horizontal page overflow.
- No overlapping navigation, reader, drawer, or assistant surfaces.
- Scripture remains readable.
- Essential actions remain labeled and reachable.
- Targets meet minimum size.

## Delivery sequence

1. Introduce semantic design tokens, typography, theme, and preferences without changing feature behavior.
2. Extract the reader shell, passage toolbar, Scripture pane, and verse components.
3. Replace the permanent library sidebar with BookPicker.
4. Replace the permanent right panel with desktop drawer and mobile sheet.
5. Connect existing study modules through the selected-reference interface.
6. Add responsive bottom navigation and full-screen mobile picker.
7. Add error boundaries and explicit system states.
8. Complete automated accessibility, responsive, regression, and browser verification.
9. Use the validated Scripture Reader primitives as the template for a later app-wide redesign.

## Definition of done

The phase is complete when a new user can open the reader, choose a book and chapter, read comfortably, change text size/theme, select a verse, use every existing study entry point, and recover from loading failures on desktop and mobile without unexplained controls, overlapping panels, inaccessible focus, or loss of content.
