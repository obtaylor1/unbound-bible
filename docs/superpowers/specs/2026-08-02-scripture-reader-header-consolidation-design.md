# Scripture Reader Header Consolidation

## Goal

Give the Scripture Reader one clear site header and one compact passage-control area. The page must remain readable and understandable for users from approximately age 13 through age 70, without duplicate branding, navigation, or account actions.

## Approved Direction

Use Option A: the existing gold-and-charcoal global navigation remains the only site header. The reader-specific actions move into the existing passage toolbar, creating one contextual control area beneath the global navigation.

## Page Structure

The page will contain, in order:

1. The global application navigation, including branding, primary destinations, search, theme access, and account/sign-in controls.
2. One reader passage toolbar containing the current passage, chapter navigation, translation selection, text-size control, theme control, “Choose a book,” and “Open study tools.”
3. One main Scripture reading landmark.
4. The existing mobile reader navigation at small viewports.

The reader-specific header will no longer render its own Unbound Bible brand or account controls. This removes the visually competing second header and duplicate sign-in action.

## Component Responsibilities

### Global Navigation

The existing `Navigation` component remains responsible for application branding, site-level destinations, account state, and sign-in. Its reader route stays highlighted through the existing Scriptures navigation state.

### Passage Toolbar

`PassageToolbar` becomes the single reader context and control surface. It receives callbacks for opening the book picker and study tools in addition to its existing passage, translation, text-size, theme, and chapter-navigation behavior.

Controls will use explicit text labels rather than icon-only actions. Desktop layouts may place related controls in groups, while narrow layouts may wrap or stack them without changing their order or accessible names.

### Scripture Reader Page

`ScriptureReaderPage` continues to own the book picker, study-tools panel, route state, passage data, and reader preferences. It passes the existing open callbacks to `PassageToolbar` and stops rendering the redundant reader header.

The main landmark, skip link, loading skeleton, reading pane, dialogs, and mobile bottom navigation remain owned by the reader page.

## Data and Interaction Flow

No Scripture API or route behavior changes are required.

- “Choose a book” opens the existing book-and-chapter picker.
- “Open study tools” opens the existing study-tools panel for the current selection.
- Translation, text size, theme, and chapter controls keep their existing state flows.
- The global sign-in action continues to use the existing application authentication flow.

## Loading and Error States

The reader retains its current loading, empty, offline, error, and retry states. The Genesis loading state observed during review was verified to resolve successfully after a fresh load, and both the canon catalog and Genesis chapter endpoints returned successful responses. This design does not alter data fetching.

## Accessibility and Responsive Behavior

- Exactly one primary navigation landmark remains.
- Exactly one main content landmark remains.
- Exactly one “Skip to main content” link targets the reader main area.
- Site-level sign-in appears only in the global navigation.
- Book and study-tool actions retain clear text labels and minimum touch-target sizing.
- Keyboard focus, dialogs, and mobile bottom navigation retain their current behavior.
- At narrow widths, the passage toolbar may stack control groups to avoid horizontal overflow.

## Testing

Implementation will add or update tests to verify:

- The Scripture Reader renders the global primary navigation.
- The duplicate reader header and duplicate sign-in action are absent.
- “Choose a book” still opens the book picker.
- “Open study tools” still opens the study-tools panel.
- The page keeps one main landmark and one skip link.
- Passage-toolbar behavior remains correct at component level.
- Existing reader, navigation, lint, and production-build checks continue to pass.

## Out of Scope

- Scripture API changes or ingestion work.
- Changes to the visual design of other pages.
- A redesign of the global navigation.
- New reader features or account behavior.
