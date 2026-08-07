import AxeBuilder from '@axe-core/playwright'
import { expect, test as base } from '@playwright/test'

const COMPOSITE = 'EOTC-COMPOSITE-EN'
const EDITION = {
  code: COMPOSITE,
  name: 'Ethiopian Orthodox Bible — Composite English Edition',
  language: 'English',
  relationship: 'general_reading',
}

const sources = {
  genesis: {
    source_key: 'world-messianic-bible',
    source_label: 'World Messianic Bible (archive revision unverified)',
    translator: 'World Messianic Bible contributors',
    source_language: 'Hebrew',
    source_tradition: 'Hebrew Masoretic tradition',
    license: 'LicenseRef-Public-Domain',
    attribution: 'Public-domain World Messianic Bible text supplied by the user archive; exact upstream revision is not preserved.',
    fallback: false,
    modified: true,
    modification_note: 'Source chapter identifiers were normalized to numeric order and app work names were standardized.',
    verification_status: 'provisional',
    canon_scope: 'ethio81',
  },
  baruch: {
    source_key: 'kjv-1611-fallback',
    source_label: 'KJV 1611 fallback (archive text)',
    translator: 'King James Version translators',
    source_language: 'Greek and Hebrew',
    source_tradition: 'King James Version Apocrypha',
    published_year: 1611,
    license: 'LicenseRef-Public-Domain',
    attribution: 'Public-domain KJV 1611 fallback supplied by the user archive; this is not a distinct Ethiopian Orthodox English translation.',
    fallback: true,
    modified: false,
    verification_status: 'provisional',
    canon_scope: 'ethio81',
  },
  meqabyan: {
    source_key: 'wikisource-meqabyan-geez',
    source_label: "Wikisource Meqabyan translation from Ge'ez",
    translator: 'Wikisource contributors',
    source_language: "Ge'ez",
    source_tradition: 'Ethiopian Meqabyan',
    license: 'CC-BY-SA-4.0',
    attribution: 'Wikisource contributors, CC BY-SA 4.0. Reuse must give attribution, identify changes, link the license, and preserve ShareAlike terms.',
    provenance_url: 'https://en.wikisource.org/w/index.php?title=Translation:1_Meqabyan&oldid=16044809',
    fallback: false,
    modified: true,
    modification_note: 'Source extraction and JSON formatting were applied without changing scripture prose.',
    verification_status: 'provisional',
    canon_scope: 'ethio81',
  },
  prayer: {
    source_key: 'kjv-1611-fallback',
    source_label: 'KJV 1611 fallback (archive text)',
    translator: 'King James Version translators',
    source_language: 'Greek and Hebrew',
    source_tradition: 'King James Version Apocrypha',
    license: 'LicenseRef-Public-Domain',
    attribution: 'Public-domain KJV 1611 fallback supplied by the user archive.',
    fallback: true,
    modified: false,
    verification_status: 'provisional',
    canon_scope: 'supplemental',
  },
}

const rowsByBook = {
  Genesis: [
    {
      id: 'composite-genesis-1-1', book: 'Genesis', chapter: 1, verse: 1,
      translation: COMPOSITE, edition: EDITION,
      text: 'In the beginning God created the heavens and the earth.',
      work_source: sources.genesis,
    },
    {
      id: 'kjv-genesis-1-1', book: 'Genesis', chapter: 1, verse: 1,
      translation: 'KJV', edition: { code: 'KJV', name: 'King James Version', language: 'English' },
      text: 'In the beginning God created the heaven and the earth.',
      work_source: {
        source_label: 'King James Version', source_tradition: 'Protestant',
        verification_status: 'verified', canon_scope: 'ethio81',
      },
    },
  ],
  Baruch: [{
    id: 'composite-baruch-1-1', book: 'Baruch', chapter: 1, verse: 1,
    translation: COMPOSITE, edition: EDITION,
    text: 'And these are the words of the book.', work_source: sources.baruch,
  }],
  '1 Meqabyan': [{
    id: 'composite-meqabyan-1-1', book: '1 Meqabyan', chapter: 1, verse: 1,
    translation: COMPOSITE, edition: EDITION,
    text: 'In the days of the king, the faithful stood firm.', work_source: sources.meqabyan,
  }],
  'Prayer of Manasseh': [{
    id: 'composite-prayer-1-1', book: 'Prayer of Manasseh', chapter: 1, verse: 1,
    translation: COMPOSITE, edition: EDITION,
    text: 'O Lord, Almighty God of our fathers.', work_source: sources.prayer,
  }],
}

const ethioBooks = [
  { id: 'genesis', name: 'Genesis', testament: 'Old Testament', collection: 'Pentateuch', recommended_edition: COMPOSITE, unavailable_reason: null },
  { id: 'baruch', name: 'Baruch', testament: 'Old Testament', collection: 'Deuterocanon', recommended_edition: COMPOSITE, unavailable_reason: null },
  { id: '1-meqabyan', name: '1 Meqabyan', testament: 'Old Testament', collection: 'Meqabyan', recommended_edition: COMPOSITE, unavailable_reason: null },
  { id: 'tegsats', name: 'Tegsats', testament: 'Old Testament', collection: 'Ethiopian broader canon', recommended_edition: null, unavailable_reason: 'English text not yet available' },
]

function readerUrl(book, canon = 'ETHIO81') {
  const params = new URLSearchParams({ book, chapter: '1', translation: COMPOSITE, canon })
  return `/#scriptures?${params}`
}

function compareRows(book) {
  if (book !== 'Genesis') return rowsByBook[book] ?? []
  return [
    { ...rowsByBook.Genesis[0], text: '   ' },
    rowsByBook.Genesis[1],
  ]
}

const test = base.extend({
  requests: async ({ page }, provideFixture) => {
    const requests = []
    page.on('request', (request) => requests.push(request.url()))
    await provideFixture(requests)
  },
})

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/books?**', (route) => {
    const canon = new URL(route.request().url()).searchParams.get('canon')
    const books = canon === 'LIBRARY'
      ? [...ethioBooks, { id: 'prayer-of-manasseh', name: 'Prayer of Manasseh', recommended_edition: COMPOSITE, unavailable_reason: null }]
      : ethioBooks
    return route.fulfill({ json: { books } })
  })
  await page.route('**/api/biblical-texts/book-content?**', (route) => route.fulfill({
    json: { content: [{ chapter: 1 }] },
  }))
  await page.route('**/api/biblical-texts/chapter-content?**', (route) => {
    const url = new URL(route.request().url())
    const book = url.searchParams.get('book')
    const isCompare = page.url().includes('#compare')
    return route.fulfill({ json: { content: isCompare ? compareRows(book) : (rowsByBook[book] ?? []) } })
  })
  await page.route('**/api/biblical-texts/available-books', (route) => route.fulfill({
    json: { books: ethioBooks.map(({ name }) => name) },
  }))
})

test('loads the recommended Genesis composite edition and discloses its source by keyboard', async ({ page }) => {
  await page.goto(readerUrl('Genesis'))

  await expect(page.getByRole('heading', { level: 1, name: 'Genesis 1' })).toBeVisible()
  await expect(page.getByText(rowsByBook.Genesis[0].text, { exact: true })).toBeVisible()
  await expect(page.getByLabel('Change translation')).toHaveValue(COMPOSITE)
  await expect(page.getByText(sources.genesis.source_label, { exact: true })).toBeVisible()

  const disclosure = page.getByText('About this text', { exact: true })
  await disclosure.focus()
  await disclosure.press('Enter')
  await expect(page.getByText(sources.genesis.attribution, { exact: true })).toBeVisible()
  await disclosure.press('Enter')
  await expect(page.getByText(sources.genesis.attribution, { exact: true })).toBeHidden()

  const sourcePicker = page.getByLabel('Change translation')
  await sourcePicker.focus()
  await sourcePicker.press('Home')
  await sourcePicker.press('Enter')
  await expect(sourcePicker).toBeFocused()
})

test('labels Baruch as a literal KJV fallback instead of implying an Ethiopian translation', async ({ page }) => {
  await page.goto(readerUrl('Baruch'))

  await expect(page.getByText(rowsByBook.Baruch[0].text, { exact: true })).toBeVisible()
  await expect(page.getByText('KJV fallback', { exact: true })).toBeVisible()
  await expect(page.getByText(sources.baruch.source_label, { exact: true })).toBeVisible()
  await page.getByText('About this text', { exact: true }).click()
  await expect(page.getByText(/not a distinct Ethiopian Orthodox English translation/i)).toBeVisible()
})

test('shows Meqabyan attribution, ShareAlike terms, and a safe permanent revision link', async ({ page }) => {
  await page.goto(readerUrl('1 Meqabyan'))
  await page.getByText('About this text', { exact: true }).click()

  await expect(page.getByText('CC-BY-SA-4.0', { exact: true })).toBeVisible()
  await expect(page.getByText(/preserve ShareAlike terms/i)).toBeVisible()
  const sourceLink = page.getByRole('link', { name: /View source record/ })
  await expect(sourceLink).toHaveAttribute('href', /oldid=16044809$/)
  await expect(sourceLink).toHaveAttribute('target', '_blank')
  await expect(sourceLink).toHaveAttribute('rel', /noopener/)
  await expect(sourceLink).toHaveAttribute('rel', /noreferrer/)
})

test('reports Tegsats as unavailable without fabricating text or requesting a chapter', async ({ page, requests }) => {
  await page.goto(readerUrl('Tegsats'))

  await expect(page.getByRole('heading', { name: 'English text not yet available for Tegsats' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Tegsats 1 verse/i })).toHaveCount(0)
  expect(requests.some((url) => url.includes('/chapter-content') && url.includes('book=Tegsats'))).toBe(false)
})

test('keeps the supplemental Prayer of Manasseh behind the LIBRARY catalog', async ({ page }) => {
  const catalogCanons = []
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/books?')) {
      catalogCanons.push(new URL(request.url()).searchParams.get('canon'))
    }
  })

  await page.goto(readerUrl('Prayer of Manasseh', 'LIBRARY'))
  await expect(page.getByText(rowsByBook['Prayer of Manasseh'][0].text, { exact: true })).toBeVisible()
  await page.getByText('About this text', { exact: true }).click()
  await expect(page.getByText('Supplemental text', { exact: true })).toBeVisible()
  expect(catalogCanons).toContain('LIBRARY')
})

test('excludes missing text from differences and labels the effective available base', async ({ page }) => {
  await page.goto('/#compare?book=Genesis&chapter=1&verse=1&translation=EOTC-COMPOSITE-EN&canon=ETHIO81')

  await expect(page.getByRole('heading', { name: 'Compare translations' })).toBeVisible()
  await expect(page.getByRole('article', { name: EDITION.name })).toContainText('Text unavailable')
  await expect(page.getByRole('article', { name: 'King James Version' })).toContainText('Base reference')
  await expect(page.getByRole('combobox', { name: 'Base reference' })).toHaveValue('kjv')
  await expect(page.getByText('One source is available. Add another source to compare wording.')).toBeVisible()
  await expect(page.getByText('0 wording differences found')).toBeVisible()
  await expect(page.getByText(/Differences are highlighted against King James Version/)).toBeVisible()
})

test('is accessible in both themes and reflows at a 200%-equivalent layout without losing source controls', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'desktop theme, axe, and zoom-equivalent audit')
  await page.goto(readerUrl('Genesis'))

  for (const theme of ['dark', 'light']) {
    if (theme === 'light') await page.getByRole('button', { name: 'Use light mode' }).click()
    await expect(page.locator('html')).toHaveAttribute('data-reader-theme', theme)
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    expect(results.violations, `${theme} theme accessibility violations`).toEqual([])
  }

  // At the desktop project's 1440px baseline, 200% browser zoom exposes a
  // 720-CSS-pixel layout viewport. Playwright cannot set Chrome's toolbar zoom,
  // so use the suite's exact zoom-equivalent reflow convention.
  await page.setViewportSize({ width: 720, height: 900 })
  const sourcePicker = page.getByLabel('Change translation')
  await sourcePicker.scrollIntoViewIfNeeded()
  await expect(sourcePicker).toBeVisible()
  await expect(page.getByText('About this text', { exact: true })).toBeVisible()
  const widths = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }))
  expect(widths.scroll).toBeLessThanOrEqual(widths.client)
})

test('keeps the reader usable at 320px with no document overflow', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-320', '320px responsive audit')
  await page.goto(readerUrl('Genesis'))

  for (const control of [
    page.getByLabel('Change translation'),
    page.getByText('About this text', { exact: true }),
    page.getByRole('button', { name: 'Choose a book' }),
    page.getByRole('button', { name: 'Open study tools' }),
  ]) {
    await control.scrollIntoViewIfNeeded()
    await expect(control).toBeVisible()
  }
  const widths = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }))
  expect(widths.scroll).toBeLessThanOrEqual(widths.client)
})
