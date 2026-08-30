import AxeBuilder from '@axe-core/playwright'
import { expect, test as base } from '@playwright/test'

const COMPOSITE = 'EOTC-COMPOSITE-EN'
const READER = (book) => `/#scriptures?book=${encodeURIComponent(book)}&chapter=1&translation=${COMPOSITE}&canon=ETHIO81`
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

const edition = {
  code: COMPOSITE,
  name: 'Ethiopian Canon Research Collection — Mixed-source English',
  language: 'English',
  relationship: 'general_reading',
}

function source({ key, label, status, attribution, sourceEdition, fallback = false }) {
  const verified = status.startsWith('verified_')
  return {
    source_key: key,
    source_label: label,
    translator: 'Reviewed public-source translator',
    source_language: 'Source language disclosed',
    source_tradition: 'Source tradition disclosed',
    license: key === 'wikisource-meqabyan-geez' ? 'CC-BY-SA-4.0' : 'LicenseRef-Public-Domain',
    attribution,
    source_edition: sourceEdition,
    source_revision: 'Locked reviewed revision',
    rights_jurisdiction: 'Rights jurisdiction disclosed',
    provenance_url: 'https://example.org/source-record',
    rights_url: 'https://example.org/rights-record',
    fallback,
    modified: verified,
    modification_note: verified ? 'Rebuilt only through documented source transformations.' : null,
    transformations: verified ? ['Deterministic container conversion; scripture wording preserved.'] : [],
    verification: {
      status,
      verified_at: verified ? '2026-08-30T08:55:00Z' : null,
    },
    canon_scope: 'ethio81',
  }
}

const workSources = {
  Genesis: source({
    key: 'world-messianic-bible',
    label: 'World Messianic Bible',
    status: 'verified_rebuilt',
    sourceEdition: 'World Messianic Bible, August 2022 stable text',
    attribution: 'Official public-domain eBible text; the World Messianic Bible naming condition applies.',
  }),
  Matthew: source({
    key: 'murdock-peshitta-1852',
    label: "James Murdock's Translation of the Syriac Peshitta",
    status: 'verified_rebuilt',
    sourceEdition: 'Murdock Peshitta translation (published 1852); historical witness: ninth edition (1915)',
    attribution: "James Murdock's public-domain English translation of the Syriac Peshitta.",
  }),
  Baruch: source({
    key: 'kjv-1611-fallback',
    label: 'KJV 1611 fallback (reviewed electronic transcription)',
    status: 'verified_rebuilt',
    sourceEdition: 'King James Version Apocrypha (1611 Great HE family)',
    attribution: 'Public-domain KJV fallback; this is not a distinct Ethiopian Orthodox English translation.',
    fallback: true,
  }),
  Jubilees: source({
    key: 'rh-charles-ethiopic',
    label: 'R. H. Charles, The Book of Jubilees (1902 translation)',
    status: 'verified_rebuilt',
    sourceEdition: 'R. H. Charles, The Book of Jubilees (London: A. and C. Black, 1902)',
    attribution: "R. H. Charles's public-domain 1902 English translation.",
  }),
  '1 Meqabyan': source({
    key: 'wikisource-meqabyan-geez',
    label: "Wikisource Meqabyan translation from Ge'ez",
    status: 'in_progress',
    sourceEdition: null,
    attribution: 'Wikisource contributors, CC BY-SA 4.0; attribution and ShareAlike terms apply.',
  }),
}

const verseText = {
  Genesis: 'In the beginning God created the heavens and the earth.',
  Matthew: 'The book of the genealogy of Yeshua the Messiah.',
  Baruch: 'And these are the words of the book.',
  Jubilees: 'And it came to pass in the first year of the exodus.',
  '1 Meqabyan': 'The supplied Meqabyan research text remains readable while review continues.',
}

const books = Object.keys(workSources).map((name) => ({
  id: name.toLocaleLowerCase().replace(/[^a-z0-9]+/gu, '-'),
  name,
  testament: name === 'Matthew' ? 'New Testament' : 'Old Testament',
  collection: name === 'Matthew' ? 'Gospels' : 'Ethiopian Canon Research Collection',
  recommended_edition: COMPOSITE,
  unavailable_reason: null,
}))

function rows(book) {
  return [{
    id: `${book}-1-1`,
    book,
    chapter: 1,
    verse: 1,
    translation: COMPOSITE,
    edition,
    text: verseText[book],
    work_source: workSources[book],
  }]
}

const commentarySource = {
  id: 'john-gill',
  title: 'John Gill’s Exposition',
  abbreviation: 'Gill',
  author: 'John Gill',
  publication_period: '1746–1763',
  tradition: 'Reformed Baptist',
  language: 'English',
  attribution: 'Public-domain source.',
}

const test = base.extend({
  browserDiagnostics: async ({ page }, provideFixture) => {
    const errors = []
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().startsWith('Failed to load resource:')) {
        errors.push(`console: ${message.text()}`)
      }
    })
    await provideFixture(errors)
    expect(errors, 'release-contract pages must not emit browser errors').toEqual([])
  },
})

test.beforeEach(async ({ page, browserDiagnostics }) => {
  void browserDiagnostics
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ status: 401, json: { detail: 'Not authenticated' } }))
  await page.route('**/api/v1/library/admin/scripture-verification', (route) => route.fulfill({ status: 401, json: { detail: 'Not authenticated' } }))
  await page.route('**/api/v1/books?**', (route) => route.fulfill({ json: { books } }))
  await page.route('**/api/biblical-texts/book-content?**', (route) => route.fulfill({ json: { content: [{ chapter: 1 }] } }))
  await page.route('**/api/biblical-texts/chapter-content?**', (route) => {
    const book = new URL(route.request().url()).searchParams.get('book')
    return route.fulfill({ json: { content: rows(book) } })
  })
  await page.route('**/api/biblical-texts/available-books', (route) => route.fulfill({ json: { books: Object.keys(workSources) } }))
  await page.route('**/api/v1/race-misuse', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/v1/texts/*/*/*/details', (route) => route.fulfill({ json: {
    book: 'Genesis', chapter: 1, verse: 1,
    historical_context: 'Locally published contextual details.',
    translations: [{ translation: COMPOSITE, text: verseText.Genesis }],
    original_language_insights: [],
    cross_references: [],
  } }))
  await page.route('**/api/v1/search?**', (route) => route.fulfill({ json: { results: [{
    group: 'scripture',
    id: 'genesis-1-1',
    title: 'Genesis 1:1',
    excerpt: verseText.Genesis,
    url: READER('Genesis'),
  }] } }))
  await page.route('**/api/v1/commentaries/sources', (route) => route.fulfill({ json: { sources: [commentarySource] } }))
  await page.route('**/api/v1/commentaries/entries?**', (route) => route.fulfill({ json: {
    reference: { book: 'Genesis', chapter: 1, verse: 1 },
    availability: 'available',
    truncated: false,
    source: commentarySource,
    entries: [{
      body: 'A locally published commentary entry for Genesis 1:1.',
      citation: 'John Gill, Commentary on Genesis 1:1',
      entry_type: 'verse',
      scope: { verse_start: 1, verse_end: 1 },
    }],
  } }))
})

async function openReader(page, book) {
  await page.goto(READER(book))
  await expect(page.getByRole('heading', { level: 1, name: `${book} 1` })).toBeVisible()
  await expect(page.getByText(verseText[book], { exact: true })).toBeVisible()
}

async function expectNoOverflow(page) {
  const width = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }))
  expect(width.scroll).toBeLessThanOrEqual(width.client)
}

test('keeps all reviewed families and an in-progress Meqabyan source truthful and readable', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'one canonical desktop source-contract audit')

  for (const [book, expected] of [
    ['Genesis', ['World Messianic Bible', 'Rebuilt from verified source']],
    ['Matthew', ["James Murdock's Translation of the Syriac Peshitta", 'Rebuilt from verified source']],
    ['Baruch', ['KJV 1611 fallback (reviewed electronic transcription)', 'KJV fallback', 'Rebuilt from verified source']],
    ['Jubilees', ['R. H. Charles, The Book of Jubilees (1902 translation)', 'Rebuilt from verified source']],
    ['1 Meqabyan', ["Wikisource Meqabyan translation from Ge'ez", 'Source verification in progress']],
  ]) {
    await openReader(page, book)
    const sourceRegion = page.getByRole('region', { name: 'Text source' })
    for (const text of expected) await expect(sourceRegion.getByText(text, { exact: true })).toBeVisible()
    const disclosure = sourceRegion.getByText('About this text', { exact: true })
    await disclosure.focus()
    await expect(disclosure).toBeFocused()
    await disclosure.press('Enter')
    await expect(sourceRegion.getByText(workSources[book].attribution, { exact: true })).toBeVisible()
  }
})

test('preserves source disclosure, themes, accessible names, and reflow at 200% zoom equivalent', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'desktop zoom and theme audit')
  await openReader(page, 'Baruch')

  await expect(page.getByRole('button', { name: 'Choose a book' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open study tools' })).toBeVisible()
  await expect(page.getByLabel('Change translation')).toHaveValue(COMPOSITE)

  for (const theme of ['dark', 'light']) {
    if (theme === 'light') await page.getByRole('button', { name: 'Use light mode' }).click()
    await expect(page.locator('html')).toHaveAttribute('data-reader-theme', theme)
    const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
    expect(results.violations, `${theme} source-disclosure accessibility violations`).toEqual([])
  }

  await page.setViewportSize({ width: 720, height: 900 })
  await page.getByRole('region', { name: 'Text source' }).scrollIntoViewIfNeeded()
  await expect(page.getByText('KJV fallback', { exact: true })).toBeVisible()
  await expectNoOverflow(page)
})

test('keeps source controls readable on the narrowest supported mobile viewport', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-320', '320px source disclosure audit')
  await openReader(page, 'Jubilees')
  await page.getByRole('region', { name: 'Text source' }).scrollIntoViewIfNeeded()
  await expect(page.getByText('About this text', { exact: true })).toBeVisible()
  await expectNoOverflow(page)
})

test('keeps search, comparison, commentary, and research routes reachable', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'one canonical route-health audit')
  await openReader(page, 'Genesis')

  await page.getByRole('button', { name: /Genesis 1 verse 1/ }).click()
  await page.getByRole('button', { name: 'Open study tools' }).click()
  await page.getByRole('button', { name: 'Commentary' }).click()
  await expect(page.getByText('A locally published commentary entry for Genesis 1:1.')).toBeVisible()

  await page.goto('/#compare?book=Genesis&chapter=1&verse=1&translation=EOTC-COMPOSITE-EN&canon=ETHIO81')
  await expect(page.getByRole('heading', { name: 'Compare translations' })).toBeVisible()

  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await page.getByRole('combobox', { name: 'Search the library' }).fill('Genesis')
  await expect(page.getByRole('option', { name: /Genesis 1:1/ })).toBeVisible()

  await page.goto('/#research')
  await expect(page.getByRole('main', { name: 'Research' })).toBeVisible()
  await expect(page.getByText(/Research topics are not loaded|Biblical Research Hub/)).toBeVisible()
})

test('does not expose administrator evidence to an anonymous reader', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'one canonical authorization audit')
  await page.goto('/#admin-scripture-verification')

  const accessState = page.getByRole('heading', { name: 'Sign in to review sources' }).locator('..')
  await expect(accessState).toBeVisible()
  await expect(accessState.getByRole('button', { name: 'Sign in' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Scripture source verification' })).toHaveCount(0)
})
