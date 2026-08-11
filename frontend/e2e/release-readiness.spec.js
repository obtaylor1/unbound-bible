import AxeBuilder from '@axe-core/playwright'
import { expect, test as base } from '@playwright/test'
import process from 'node:process'

const COMPOSITE = 'EOTC-COMPOSITE-EN'
const GENESIS = 'In the beginning God created the heavens and the earth.'
const KJV = 'In the beginning God created the heaven and the earth.'
const axeTags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

function readerUrl(book = 'Genesis', translation = COMPOSITE) {
  return `/#scriptures?${new URLSearchParams({ book, chapter: '1', translation, canon: 'ETHIO81' })}`
}

const rows = {
  Genesis: [
    { id: 'composite-genesis-1-1', book: 'Genesis', chapter: 1, verse: 1, translation: COMPOSITE, text: GENESIS,
      edition: { code: COMPOSITE, name: 'Ethiopian Orthodox Bible — Composite English Edition', language: 'English' },
      work_source: { source_label: 'World Messianic Bible (archive revision unverified)', source_tradition: 'Hebrew Masoretic tradition', verification_status: 'provisional', canon_scope: 'ethio81', attribution: 'Public-domain source text supplied by the user archive; exact upstream revision is not preserved.' } },
    { id: 'kjv-genesis-1-1', book: 'Genesis', chapter: 1, verse: 1, translation: 'KJV', text: KJV,
      edition: { code: 'KJV', name: 'King James Version', language: 'English' },
      work_source: { source_label: 'King James Version', source_tradition: 'Protestant', verification_status: 'verified', canon_scope: 'ethio81' } },
  ],
  Exodus: [{ id: 'composite-exodus-1-1', book: 'Exodus', chapter: 1, verse: 1, translation: COMPOSITE, text: 'Now these are the names of the children of Israel, who came into Egypt.', edition: { code: COMPOSITE, name: 'Ethiopian Orthodox Bible — Composite English Edition' }, work_source: { source_label: 'World Messianic Bible (archive revision unverified)', verification_status: 'provisional' } }],
}

const test = base.extend({
  diagnostics: async ({ page }, provideFixture) => {
    const errors = []
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
    page.on('console', (message) => { if (message.type() === 'error') errors.push(`console: ${message.text()}`) })
    await provideFixture(errors)
    expect(errors, 'release journey must not emit browser errors').toEqual([])
  },
  requests: async ({ page }, provideFixture) => {
    const requests = []
    page.on('request', (request) => requests.push(request.url()))
    await provideFixture(requests)
  },
})

test.beforeEach(async ({ page, diagnostics }) => {
  void diagnostics
  await page.route('https://fonts.googleapis.com/**', (route) => route.fulfill({
    contentType: 'text/css',
    body: '',
  }))
  await page.route('**/api/v1/books?**', (route) => route.fulfill({ json: { books: [
    { id: 'genesis', name: 'Genesis', testament: 'Old Testament', collection: 'Pentateuch', recommended_edition: COMPOSITE, unavailable_reason: null },
    { id: 'exodus', name: 'Exodus', testament: 'Old Testament', collection: 'Pentateuch', recommended_edition: COMPOSITE, unavailable_reason: null },
    { id: 'tegsats', name: 'Tegsats', testament: 'Old Testament', collection: 'Ethiopian broader canon', recommended_edition: null, unavailable_reason: 'English text not yet available' },
  ] } }))
  await page.route('**/api/biblical-texts/book-content?**', (route) => route.fulfill({ json: { content: [{ chapter: 1 }, { chapter: 2 }] } }))
  await page.route('**/api/biblical-texts/chapter-content?**', (route) => {
    const book = new URL(route.request().url()).searchParams.get('book')
    return route.fulfill({ json: { content: rows[book] ?? [] } })
  })
  await page.route('**/api/v1/texts/*/*/*/details', (route) => {
    const match = new URL(route.request().url()).pathname.match(/\/texts\/([^/]+)\/(\d+)\/(\d+)\/details$/u)
    const book = match ? decodeURIComponent(match[1]) : null
    const chapter = match ? Number(match[2]) : null
    const verse = match ? Number(match[3]) : null
    if (!rows[book] || chapter !== 1 || verse !== 1) {
      return route.fulfill({ status: 400, json: { detail: 'Unexpected release fixture reference' } })
    }
    return route.fulfill({ json: {
      book, chapter, verse,
      translations: rows[book].map(({ translation, text }) => ({ translation, text })),
      historical_context: `${book} opens within its ancient setting.`,
      original_language_insights: [{ word: book === 'Genesis' ? 'bereshit' : 'shemot', language: 'Hebrew', meaning: book === 'Genesis' ? 'in the beginning' : 'names' }],
      cross_references: [{ reference: book === 'Genesis' ? 'John 1:1' : 'Genesis 46:8', description: `A related reference for ${book}.` }],
    } })
  })
  await page.route('**/api/v1/commentaries/sources', (route) => route.fulfill({ json: { sources: [{ id: 'gill', title: 'John Gill’s Exposition', abbreviation: 'Gill', author: 'John Gill', attribution: 'Public-domain edition prepared by HelloAO' }] } }))
  await page.route('**/api/v1/commentaries/entries?**', (route) => {
    const params = new URL(route.request().url()).searchParams
    const book = params.get('book')
    const chapter = Number(params.get('chapter'))
    const verse = Number(params.get('verse')) || undefined
    if (!rows[book] || chapter !== 1 || (verse !== undefined && verse !== 1)) {
      return route.fulfill({ status: 400, json: { detail: 'Unexpected commentary reference' } })
    }
    const label = `${book} ${chapter}${verse ? `:${verse}` : ''}`
    return route.fulfill({ json: {
      reference: { book, chapter, ...(verse ? { verse } : {}) },
      availability: 'available',
      truncated: false,
      source: { id: 'gill', title: 'John Gill’s Exposition', author: 'John Gill' },
      entries: [{ body: `${book}-specific commentary for ${label}.`, citation: `John Gill, Commentary on ${label}`, entry_type: verse ? 'verse' : 'chapter_intro', scope: verse ? { verse_start: verse, verse_end: verse } : { verse_start: null, verse_end: null } }],
    } })
  })
  await page.route('**/api/v1/search?**', (route) => route.fulfill({ json: { results: [{ group: 'scripture', id: 'genesis-1-1', title: 'Genesis 1:1', excerpt: GENESIS, url: readerUrl() }] } }))
  await page.route('**/api/**/login**', (route) => route.fulfill({ status: 401, json: { detail: 'Invalid email or password' } }))
  await page.route('**/api/**/auth/**', (route) => route.fulfill({ status: 401, json: { detail: 'Sign-in unavailable for this release check' } }))
  await page.route('**/auth/login', (route) => route.fulfill({ status: 401, json: { detail: 'Invalid email or password' } }))
  const savedNotes = []
  await page.route('**/api/v1/notes**', async (route) => {
    const request = route.request()
    if (request.method() === 'GET') return route.fulfill({ json: savedNotes })
    if (request.method() === 'POST') {
      const note = { id: `note-${savedNotes.length + 1}`, ...request.postDataJSON(), updated_at: '2026-08-10T12:00:00Z' }
      savedNotes.unshift(note)
      return route.fulfill({ status: 201, json: note })
    }
    if (request.method() === 'DELETE') return route.fulfill({ status: 204 })
    return route.fulfill({ status: 405, json: { detail: 'Unexpected notes method' } })
  })
})

function skipUnless(testInfo, names, reason) {
  test.skip(!names.includes(testInfo.project.name), reason)
}

async function openReader(page) {
  await page.goto(readerUrl())
  await expect(page.getByRole('heading', { level: 1, name: 'Genesis 1' })).toBeVisible()
  await expect(page.getByText(GENESIS, { exact: true })).toBeVisible()
}

async function expectNoOverflow(page) {
  const size = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }))
  expect(size.scroll).toBeLessThanOrEqual(size.client)
}

async function expectAxe(page, state) {
  const results = await new AxeBuilder({ page }).withTags(axeTags).analyze()
  expect(results.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical'), `${state}: serious or critical WCAG 2/2.1 A/AA issues`).toEqual([])
}

async function expectShellFitsViewport(locator, label) {
  const geometry = await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect()
    return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: innerWidth, height: innerHeight }
  })
  expect(geometry.left, `${label} left edge`).toBeGreaterThanOrEqual(0)
  expect(geometry.top, `${label} top edge`).toBeGreaterThanOrEqual(0)
  expect(geometry.right, `${label} right edge`).toBeLessThanOrEqual(geometry.width)
  expect(geometry.bottom, `${label} bottom edge`).toBeLessThanOrEqual(geometry.height)
}

async function expectReachable(locator, label) {
  await locator.scrollIntoViewIfNeeded()
  await expect(locator).toBeVisible()
  const geometry = await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect()
    return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: innerWidth, height: innerHeight }
  })
  expect(geometry.right, `${label} right edge`).toBeGreaterThan(0)
  expect(geometry.left, `${label} left edge`).toBeLessThan(geometry.width)
  expect(geometry.bottom, `${label} bottom edge`).toBeGreaterThan(0)
  expect(geometry.top, `${label} top edge`).toBeLessThan(geometry.height)
}

async function expectTranslationContentReachable(dialog, label) {
  const content = dialog.locator('.translation-overview__content')
  const scrolling = await content.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
    overflowY: getComputedStyle(element).overflowY,
  }))
  if (scrolling.scrollHeight > scrolling.clientHeight) {
    expect(scrolling.overflowY, `${label} overflowing content has an inner scroll area`).toMatch(/auto|scroll/u)
  }
  await expectReachable(dialog.getByRole('link', { name: /Read the detailed source audit/ }), `${label} final source-audit link`)
  await expectReachable(dialog.getByRole('button', { name: 'Close translation information' }), `${label} close control`)
}

async function openTranslationOverview(page, { keyboard = false } = {}) {
  const trigger = page.getByRole('button', { name: 'About this translation' })
  if (keyboard) {
    await trigger.focus()
    await expect(trigger).toBeFocused()
    await trigger.press('Enter')
  } else {
    await trigger.click()
  }
  const dialog = page.getByRole('dialog', { name: 'About the Ethiopian Composite English edition' })
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('not one uniform Ethiopian Orthodox translation')
  await expect(dialog).toContainText('source records remain provisional')
  if (keyboard) await expect(dialog.getByRole('button', { name: 'Close translation information' })).toBeFocused()
  return dialog
}

test('desktop reader release journey', async ({ page }, testInfo) => {
  skipUnless(testInfo, ['desktop-chromium'], 'desktop release journey')
  await openReader(page)
  const skip = page.getByRole('link', { name: 'Skip to main content' })
  await skip.focus(); await skip.press('Enter')
  await expect(page.locator('#main-content')).toBeFocused()
  await expect(page.getByRole('navigation')).toBeVisible()
  const home = page.getByRole('button', { name: 'Home', exact: true })
  await home.focus()
  await expect(home).toBeFocused()
  await home.press('Enter')
  const scripturesMenu = page.getByRole('button', { name: 'Scriptures' })
  await scripturesMenu.focus()
  await scripturesMenu.press('Enter')
  await expect(scripturesMenu).toHaveAttribute('aria-expanded', 'true')
  const scriptureReader = page.getByRole('button', { name: 'Scripture Reader' })
  await scriptureReader.focus()
  await expect(scriptureReader).toBeFocused()
  await scriptureReader.press('Enter')
  await expect(page.getByRole('heading', { level: 1, name: 'Genesis 1' })).toBeVisible()

  const bookOpener = page.getByRole('button', { name: 'Choose a book' })
  await bookOpener.focus()
  await bookOpener.press('Enter')
  const picker = page.getByRole('dialog', { name: 'Choose a book and chapter' })
  await expect(picker.getByRole('searchbox', { name: 'Search Bible books' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(picker).toBeHidden()
  await expect(bookOpener).toBeFocused()
  await bookOpener.press('Enter')
  const exodus = picker.getByRole('button', { name: 'Exodus', exact: true })
  await exodus.focus()
  await exodus.press('Enter')
  const exodusChapter = picker.getByRole('button', { name: 'Chapter 1' })
  await expect(exodusChapter).toBeFocused()
  await exodusChapter.press('Enter')
  await expect(page.getByRole('heading', { name: 'Exodus 1' })).toBeVisible()
  await bookOpener.focus()
  await bookOpener.press('Enter')
  const genesis = picker.getByRole('button', { name: 'Genesis', exact: true })
  await genesis.focus()
  await genesis.press('Enter')
  const genesisChapter = picker.getByRole('button', { name: 'Chapter 1' })
  await expect(genesisChapter).toBeFocused()
  await genesisChapter.press('Enter')
  await expect(page.getByText(GENESIS, { exact: true })).toBeVisible()

  const translation = page.getByLabel('Change translation')
  await translation.focus()
  await translation.press('k')
  await expect(translation).toHaveValue('KJV')
  await expect(page.getByText(KJV, { exact: true })).toBeVisible()
  await translation.selectOption(COMPOSITE)
  await expect(translation).toHaveValue(COMPOSITE)
  const translationTrigger = page.getByRole('button', { name: 'About this translation' })
  const translationDialog = await openTranslationOverview(page, { keyboard: true })
  await expectShellFitsViewport(translationDialog, 'desktop translation information')
  await expectTranslationContentReachable(translationDialog, 'desktop translation information')
  await page.keyboard.press('Escape')
  await expect(translationDialog).toBeHidden()
  await expect(translationTrigger).toBeFocused()
  const textDisclosure = page.getByText('About this text', { exact: true })
  await textDisclosure.focus()
  await textDisclosure.press('Enter')
  await expect(page.getByText(/Public-domain source text/i)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Current size: Medium' })).toBeVisible()
  await page.getByRole('button', { name: /Change text size/ }).press('Space')
  await expect(page.getByRole('button', { name: 'Current size: Large' })).toBeVisible()
  await page.getByRole('button', { name: 'Use light mode' }).press('Enter')
  await expect(page.locator('html')).toHaveAttribute('data-reader-theme', 'light')

  await page.getByRole('button', { name: /Genesis 1 verse 1/ }).press('Enter')
  const toolsOpener = page.getByRole('button', { name: 'Open study tools' })
  await toolsOpener.focus()
  await toolsOpener.press('Enter')
  const dialog = page.getByRole('dialog', { name: 'Genesis 1:1' })
  await expect(dialog.getByRole('button', { name: 'Close study tools' })).toBeFocused()
  await dialog.getByRole('button', { name: 'Commentary' }).focus()
  await dialog.getByRole('button', { name: 'Commentary' }).press('Enter')
  const commentary = page.getByRole('complementary', { name: 'Genesis 1' })
  await expect(commentary).toContainText('Commentary')
  await expect(commentary).toContainText('Genesis-specific commentary for Genesis 1:1.')
  await commentary.getByRole('button', { name: 'Highlights and bookmarks' }).focus()
  await commentary.getByRole('button', { name: 'Highlights and bookmarks' }).press('Enter')
  const tools = page.getByRole('dialog', { name: 'Genesis 1:1', exact: true })
  await expect(tools).toBeVisible()
  const highlight = tools.getByRole('button', { name: 'Highlight Genesis 1:1' })
  const bookmark = tools.getByRole('button', { name: 'Bookmark Genesis 1:1' })
  await highlight.focus()
  await highlight.press('Space')
  await expect(highlight).toHaveAttribute('aria-pressed', 'true')
  await expect(tools.getByRole('status')).toContainText('Highlighted Genesis 1:1')
  await bookmark.focus()
  await bookmark.press('Space')
  await expect(bookmark).toHaveAttribute('aria-pressed', 'true')
  await expect(tools.getByRole('status')).toContainText('Bookmarked Genesis 1:1')
  await page.keyboard.press(process.platform === 'darwin' ? 'Meta+K' : 'Control+K')
  await expect(tools).toBeVisible()
  await tools.getByRole('button', { name: 'Add or view notes' }).focus()
  await tools.getByRole('button', { name: 'Add or view notes' }).press('Enter')
  await expect(page.getByRole('heading', { name: 'Notes & saved studies' })).toBeVisible()
  const noteText = 'Remember that creation begins with God.'
  const noteEditor = page.getByRole('textbox', { name: 'Note for Genesis 1:1' })
  await noteEditor.focus()
  await noteEditor.fill(noteText)
  await page.getByRole('button', { name: 'Save note' }).focus()
  await page.getByRole('button', { name: 'Save note' }).press('Enter')
  await expect(page.getByRole('status')).toContainText('Note saved for Genesis 1:1')
  await expect(page.getByText(noteText, { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Notes & saved studies' })).toBeVisible()
  await expect(page.getByText(noteText, { exact: true })).toBeVisible()
  await expectAxe(page, 'desktop selected-verse state')
})

test('desktop sign-in failure has a safe reading recovery', async ({ page, diagnostics }, testInfo) => {
  skipUnless(testInfo, ['desktop-chromium'], 'desktop authentication recovery journey')
  await openReader(page)
  const signIn = page.getByRole('button', { name: 'Sign in' })
  await signIn.focus()
  await signIn.press('Enter')
  const dialog = page.getByRole('dialog', { name: 'Welcome back' })
  await expect(dialog).toBeVisible()
  await page.keyboard.press('Tab')
  await expect(dialog.getByRole('button', { name: 'Close' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(dialog.getByRole('textbox', { name: 'Email' })).toBeFocused()
  await dialog.getByLabel('Email').fill('release-check@example.invalid')
  await dialog.getByLabel('Password').fill('wrong-password')
  await dialog.getByRole('button', { name: 'Sign in' }).focus()
  await dialog.getByRole('button', { name: 'Sign in' }).press('Enter')
  await expect(dialog.getByRole('alert')).toContainText(/invalid|unable|failed|incorrect/i)
  await expect.poll(
    () => diagnostics.filter((error) => error.includes('Failed to load resource') && error.includes('401')).length,
  ).toBe(1)
  const expected401 = (error) => error.includes('Failed to load resource') && error.includes('401')
  expect(diagnostics.filter(expected401), 'only the intentional rejected login is consumed').toHaveLength(1)
  diagnostics.splice(0, diagnostics.length, ...diagnostics.filter((error) => !expected401(error)))
  await dialog.getByRole('button', { name: 'Close' }).focus()
  await dialog.getByRole('button', { name: 'Close' }).press('Enter')
  await expect(dialog).toBeHidden()
  await expect(page.getByText(GENESIS, { exact: true })).toBeVisible()
  await expectAxe(page, 'desktop sign-in recovery')
})

test('mobile reader release journey', async ({ page }, testInfo) => {
  skipUnless(testInfo, ['mobile-chromium'], '390px mobile release journey')
  await page.setViewportSize({ width: 390, height: 844 })
  await openReader(page)
  await expectNoOverflow(page)
  for (const control of [page.getByRole('button', { name: 'Choose a book' }), page.getByRole('button', { name: 'Open study tools' }), page.getByRole('button', { name: /Change text size/ })]) {
    const box = await control.boundingBox()
    expect(box?.height, 'mobile primary target height').toBeGreaterThanOrEqual(44)
  }
  await page.getByRole('button', { name: 'Choose a book' }).click()
  const bookPicker = page.getByRole('dialog', { name: 'Choose a book and chapter' })
  await expectShellFitsViewport(bookPicker, 'mobile book picker')
  await expectReachable(bookPicker.getByRole('button', { name: 'Close book picker' }), 'mobile book picker close')
  await bookPicker.getByRole('button', { name: 'Exodus', exact: true }).click()
  await expectReachable(bookPicker.getByRole('button', { name: 'Chapter 1' }), 'mobile final chapter choice')
  await bookPicker.getByRole('button', { name: 'Chapter 1' }).click()
  await expect(page.getByRole('heading', { name: 'Exodus 1' })).toBeVisible()
  const translationDialog = await openTranslationOverview(page)
  await expectShellFitsViewport(translationDialog, 'mobile translation information')
  await expectTranslationContentReachable(translationDialog, 'mobile translation information')
  await translationDialog.getByRole('button', { name: 'Close translation information' }).click()
  await expect(page.getByRole('button', { name: 'Current size: Medium' })).toBeVisible()
  await page.getByRole('button', { name: /Change text size/ }).click()
  await expect(page.getByRole('button', { name: 'Current size: Large' })).toBeVisible()
  await page.getByRole('button', { name: 'Use light mode' }).click()
  await page.getByRole('button', { name: 'Open study tools' }).click()
  await page.getByRole('button', { name: 'Commentary' }).click()
  const commentary = page.getByRole('complementary', { name: 'Exodus 1' })
  await expect(commentary).toBeVisible()
  await expect(commentary).toContainText('Exodus-specific commentary for Exodus 1.')
  await expectNoOverflow(page)
  await expectAxe(page, 'mobile commentary state')
})

test('desktop 200% zoom keeps reader and modal usable', async ({ page }, testInfo) => {
  skipUnless(testInfo, ['desktop-chromium'], 'desktop zoom release journey')
  await openReader(page)
  // The desktop project starts at 1440px; 720px is this suite's established
  // 200%-browser-zoom equivalent layout viewport.
  await page.setViewportSize({ width: 720, height: 900 })
  const translationDialog = await openTranslationOverview(page)
  await expectNoOverflow(page)
  const reader = page.getByTestId('scripture-reader')
  const font = await reader.evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))
  expect(font, 'rendered reader font size at zoom').toBeGreaterThanOrEqual(16)
  await expectShellFitsViewport(translationDialog, 'zoomed translation information')
  await expectTranslationContentReachable(translationDialog, 'zoomed translation information')
  await expect(translationDialog).toContainText('not one uniform Ethiopian Orthodox translation')
  const close = translationDialog.getByRole('button', { name: 'Close translation information' })
  await expectReachable(close, 'zoomed translation information close control')
  await close.click()
  await expect(translationDialog).toBeHidden()
  await expect(page.getByRole('button', { name: 'About this translation' })).toBeVisible()
  const verse = page.getByRole('button', { name: /Genesis 1 verse 1/ })
  await expectReachable(verse, 'zoom-equivalent reader verse')
  const disclosure = page.getByText('About this text', { exact: true })
  await expectReachable(disclosure, 'zoom-equivalent source disclosure')
  await disclosure.click()
  await expectAxe(page, 'desktop 200% zoom state')
})

test('unavailable Tegsats never fabricates chapters and recovery works', async ({ page, requests }, testInfo) => {
  skipUnless(testInfo, ['desktop-chromium', 'mobile-chromium'], 'unavailable-book release journey')
  await page.goto(readerUrl('Tegsats'))
  await expect(page.getByRole('heading', { name: 'English text not yet available for Tegsats' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Tegsats 1 verse/i })).toHaveCount(0)
  expect(requests.some((url) => url.includes('/chapter-content') && url.includes('book=Tegsats'))).toBe(false)
  await page.getByRole('button', { name: 'Choose a book' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Genesis', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Chapter 1' }).click()
  await expect(page.getByText(GENESIS, { exact: true })).toBeVisible()
  await expectAxe(page, 'unavailable Tegsats recovery')
})
