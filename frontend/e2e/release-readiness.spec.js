import AxeBuilder from '@axe-core/playwright'
import { expect, test as base } from '@playwright/test'

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
  diagnostics: async ({ page }, use) => {
    const errors = []
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
    page.on('console', (message) => { if (message.type() === 'error') errors.push(`console: ${message.text()}`) })
    await use(errors)
    expect(errors, 'release journey must not emit browser errors').toEqual([])
  },
  requests: async ({ page }, use) => {
    const requests = []
    page.on('request', (request) => requests.push(request.url()))
    await use(requests)
  },
})

test.beforeEach(async ({ page, diagnostics }) => {
  void diagnostics
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
  await page.route('**/api/v1/texts/*/*/*/details', (route) => route.fulfill({ json: {
    book: 'Genesis', chapter: 1, verse: 1, translations: rows.Genesis.map(({ translation, text }) => ({ translation, text })),
    historical_context: 'Genesis opens with an account of creation.',
    original_language_insights: [{ word: 'bereshit', language: 'Hebrew', meaning: 'in the beginning' }],
    cross_references: [{ reference: 'John 1:1', description: 'A related opening about creation.' }],
  } }))
  await page.route('**/api/v1/commentaries/sources', (route) => route.fulfill({ json: { sources: [{ id: 'gill', title: 'John Gill’s Exposition', abbreviation: 'Gill', author: 'John Gill', attribution: 'Public-domain edition prepared by HelloAO' }] } }))
  await page.route('**/api/v1/commentaries/entries?**', (route) => route.fulfill({ json: { reference: { book: 'Genesis', chapter: 1, verse: 1 }, availability: 'available', truncated: false, source: { id: 'gill', title: 'John Gill’s Exposition', author: 'John Gill' }, entries: [{ body: 'Commentary notes for Genesis 1:1.', citation: 'John Gill, Commentary on Genesis 1:1', entry_type: 'verse', scope: { verse_start: 1, verse_end: 1 } }] } }))
  await page.route('**/api/v1/search?**', (route) => route.fulfill({ json: { results: [{ group: 'scripture', id: 'genesis-1-1', title: 'Genesis 1:1', excerpt: GENESIS, url: readerUrl() }] } }))
  await page.route('**/api/**/login**', (route) => route.fulfill({ status: 401, json: { detail: 'Invalid email or password' } }))
  await page.route('**/api/**/auth/**', (route) => route.fulfill({ status: 401, json: { detail: 'Sign-in unavailable for this release check' } }))
  await page.route('**/auth/login', (route) => route.fulfill({ status: 401, json: { detail: 'Invalid email or password' } }))
  await page.route('**/api/**/notes**', (route) => route.fulfill({ json: { notes: [] } }))
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

async function expectFitsOrScrolls(locator, label) {
  const geometry = await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect()
    return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: innerWidth, height: innerHeight, scrollable: element.scrollHeight > element.clientHeight || element.scrollWidth > element.clientWidth }
  })
  expect(geometry.left, `${label} left edge`).toBeGreaterThanOrEqual(0)
  expect(geometry.right, `${label} right edge`).toBeLessThanOrEqual(geometry.width)
  expect(geometry.scrollable || (geometry.top >= 0 && geometry.bottom <= geometry.height), `${label} fits viewport or has an inner scroll area`).toBe(true)
}

async function openTranslationOverview(page) {
  await page.getByRole('button', { name: 'About this translation' }).click()
  const dialog = page.getByRole('dialog', { name: 'About the Ethiopian Composite English edition' })
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('not one uniform Ethiopian Orthodox translation')
  await expect(dialog).toContainText('source records remain provisional')
  return dialog
}

test('desktop reader release journey', async ({ page }, testInfo) => {
  skipUnless(testInfo, ['desktop-chromium'], 'desktop release journey')
  await openReader(page)
  const skip = page.getByRole('link', { name: 'Skip to main content' })
  await skip.focus(); await skip.press('Enter')
  await expect(page.locator('#main-content')).toBeFocused()
  await expect(page.getByRole('navigation')).toBeVisible()

  await page.getByRole('button', { name: 'Choose a book' }).click()
  const picker = page.getByRole('dialog', { name: 'Choose a book and chapter' })
  await picker.getByRole('button', { name: 'Exodus', exact: true }).click()
  await picker.getByRole('button', { name: 'Chapter 1' }).click()
  await expect(page.getByRole('heading', { name: 'Exodus 1' })).toBeVisible()
  await page.getByRole('button', { name: 'Choose a book' }).click()
  await picker.getByRole('button', { name: 'Genesis', exact: true }).click()
  await picker.getByRole('button', { name: 'Chapter 1' }).click()
  await expect(page.getByText(GENESIS, { exact: true })).toBeVisible()

  const translation = page.getByLabel('Change translation')
  await translation.selectOption('KJV')
  await expect(page.getByText(KJV, { exact: true })).toBeVisible()
  await translation.selectOption(COMPOSITE)
  const translationDialog = await openTranslationOverview(page)
  await translationDialog.getByRole('button', { name: 'Close translation information' }).click()
  await expect(translationDialog).toBeHidden()
  await page.getByText('About this text', { exact: true }).click()
  await expect(page.getByText(/Public-domain source text/i)).toBeVisible()
  await page.getByRole('button', { name: /Change text size/ }).click()
  await page.getByRole('button', { name: 'Use light mode' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-reader-theme', 'light')

  await page.getByRole('button', { name: /Genesis 1 verse 1/ }).click()
  await page.getByRole('button', { name: 'Open study tools' }).click()
  const dialog = page.getByRole('dialog', { name: 'Genesis 1:1' })
  await dialog.getByRole('button', { name: 'Commentary' }).click()
  const commentary = page.getByRole('complementary', { name: 'Genesis 1' })
  await expect(commentary).toContainText('Commentary')
  await commentary.getByRole('button', { name: 'Highlights and bookmarks' }).click()
  const tools = page.getByRole('dialog', { name: 'Genesis 1:1', exact: true })
  await expect(tools).toBeVisible()
  await tools.getByRole('button', { name: 'Highlight Genesis 1:1' }).click()
  await tools.getByRole('button', { name: 'Bookmark Genesis 1:1' }).click()
  await expect(tools.getByRole('status')).toContainText('Bookmarked Genesis 1:1')
  await page.keyboard.press(process.platform === 'darwin' ? 'Meta+K' : 'Control+K')
  await expect(tools).toBeVisible()
  await tools.getByRole('button', { name: 'Add or view notes' }).click()
  await expect(page.getByRole('heading', { name: 'Notes & saved studies' })).toBeVisible()
  await expectAxe(page, 'desktop selected-verse state')
})

test('desktop sign-in failure has a safe reading recovery', async ({ page, diagnostics }, testInfo) => {
  skipUnless(testInfo, ['desktop-chromium'], 'desktop authentication recovery journey')
  await openReader(page)
  await page.getByRole('button', { name: 'Sign in' }).click()
  const dialog = page.getByRole('dialog', { name: 'Welcome back' })
  await expect(dialog).toBeVisible()
  await dialog.getByLabel('Email').fill('release-check@example.invalid')
  await dialog.getByLabel('Password').fill('wrong-password')
  await dialog.getByRole('button', { name: 'Sign in' }).click()
  await expect(dialog.getByRole('alert')).toContainText(/invalid|unable|failed|incorrect/i)
  await expect.poll(
    () => diagnostics.filter((error) => error.includes('Failed to load resource') && error.includes('401')).length,
  ).toBe(1)
  const expected401 = (error) => error.includes('Failed to load resource') && error.includes('401')
  expect(diagnostics.filter(expected401), 'only the intentional rejected login is consumed').toHaveLength(1)
  diagnostics.splice(0, diagnostics.length, ...diagnostics.filter((error) => !expected401(error)))
  await dialog.getByRole('button', { name: 'Close' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByText(GENESIS, { exact: true })).toBeVisible()
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
  await expectFitsOrScrolls(page.getByRole('dialog', { name: 'Choose a book and chapter' }), 'book picker')
  await page.getByRole('dialog').getByRole('button', { name: 'Exodus', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Chapter 1' }).click()
  await expect(page.getByRole('heading', { name: 'Exodus 1' })).toBeVisible()
  const translationDialog = await openTranslationOverview(page)
  await translationDialog.getByRole('button', { name: 'Close translation information' }).click()
  await page.getByRole('button', { name: /Change text size/ }).click()
  await page.getByRole('button', { name: 'Use light mode' }).click()
  await page.getByRole('button', { name: 'Open study tools' }).click()
  await page.getByRole('button', { name: 'Commentary' }).click()
  await expect(page.getByRole('complementary', { name: 'Exodus 1' })).toBeVisible()
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
  await expectFitsOrScrolls(translationDialog, 'zoomed translation information')
  await expect(translationDialog).toContainText('not one uniform Ethiopian Orthodox translation')
  const close = translationDialog.getByRole('button', { name: 'Close translation information' })
  await expectFitsOrScrolls(close, 'zoomed translation information close control')
  await close.click()
  await expect(translationDialog).toBeHidden()
  await expect(page.getByRole('button', { name: 'About this translation' })).toBeVisible()
  const verse = page.getByRole('button', { name: /Genesis 1 verse 1/ })
  await verse.scrollIntoViewIfNeeded()
  await expect(verse).toBeVisible()
  await expectFitsOrScrolls(verse, 'zoom-equivalent reader verse')
  const disclosure = page.getByText('About this text', { exact: true })
  await disclosure.scrollIntoViewIfNeeded()
  await expect(disclosure).toBeVisible()
  await expectFitsOrScrolls(disclosure, 'zoom-equivalent source disclosure')
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
})
