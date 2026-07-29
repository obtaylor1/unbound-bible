import AxeBuilder from '@axe-core/playwright'
import { expect, test as base } from '@playwright/test'

const READER_URL = '/#scriptures?book=Genesis&chapter=1&translation=KJV&canon=ETHIO81'
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

const chapters = {
  1: [
    { id: 'kjv-1-1', chapter: 1, verse: 1, translation: 'KJV', text: 'In the beginning God created the heaven and the earth.' },
    { id: 'eth-1-1', chapter: 1, verse: 1, translation: 'ETH81', text: 'In the beginning God made heaven and earth.' },
    { id: 'kjv-1-2', chapter: 1, verse: 2, translation: 'KJV', text: 'And the earth was without form, and void.' },
    { id: 'eth-1-2', chapter: 1, verse: 2, translation: 'ETH81', text: 'The earth was formless and empty.' },
    { id: 'kjv-1-3', chapter: 1, verse: 3, translation: 'KJV', text: 'And God said, Let there be light: and there was light.' },
    { id: 'eth-1-3', chapter: 1, verse: 3, translation: 'ETH81', text: 'God said, Let light be, and light came to be.' },
  ],
  2: [
    { id: 'kjv-2-1', chapter: 2, verse: 1, translation: 'KJV', text: 'Thus the heavens and the earth were finished.' },
    { id: 'eth-2-1', chapter: 2, verse: 1, translation: 'ETH81', text: 'So heaven and earth were completed.' },
  ],
}

const verseDetails = {
  book: 'Genesis',
  chapter: 1,
  verse: 1,
  historical_context: 'Genesis opens within the ancient Near Eastern world while making its own theological claims.',
  translations: [
    { translation: 'KJV', text: chapters[1][0].text },
    { translation: 'ETH81', text: chapters[1][1].text },
  ],
  original_language_insights: [
    { word: 'bereshit', language: 'Hebrew', meaning: 'in the beginning' },
  ],
  cross_references: [
    { reference: 'John 1:1', description: 'A related opening about creation and the Word.' },
  ],
}

const test = base.extend({
  browserDiagnostics: async ({ page }, runTest) => {
    const errors = []
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(`console: ${message.text()}`)
    })
    await runTest(errors)
    expect(errors, 'reader must not emit browser console or page errors').toEqual([])
  },
})

test.beforeEach(async ({ page, browserDiagnostics }) => {
  void browserDiagnostics
  await page.route('**/api/v1/books?**', (route) => route.fulfill({
    json: { books: [{ name: 'Genesis' }, { name: 'Exodus' }] },
  }))
  await page.route('**/api/biblical-texts/book-content?**', (route) => route.fulfill({
    json: { content: [{ chapter: 1 }, { chapter: 2 }] },
  }))
  await page.route('**/api/biblical-texts/chapter-content?**', (route) => {
    const chapter = Number(new URL(route.request().url()).searchParams.get('chapter'))
    return route.fulfill({ json: { content: chapters[chapter] ?? [] } })
  })
  await page.route('**/api/v1/texts/Genesis/1/*/details', (route) => {
    const verse = Number(new URL(route.request().url()).pathname.split('/').at(-2))
    return route.fulfill({
      json: { ...verseDetails, verse },
    })
  })
  await page.route('**/api/v1/race-misuse', (route) => route.fulfill({
    json: [],
  }))
  await page.route('**/api/v1/search?**', (route) => route.fulfill({
    json: {
      results: [{
        group: 'scripture',
        id: 'genesis-1-1',
        title: 'Genesis 1:1',
        excerpt: chapters[1][0].text,
        url: READER_URL,
      }],
    },
  }))
})

async function openReader(page) {
  await page.goto(READER_URL)
  await expect(page.getByRole('heading', { level: 1, name: 'Genesis 1' })).toBeVisible()
  await expect(page.getByText(chapters[1][0].text, { exact: true })).toBeVisible()
}

async function expectNoHorizontalOverflow(page) {
  const dimensions = await page.evaluate(() => ({
    documentClient: document.documentElement.clientWidth,
    documentScroll: document.documentElement.scrollWidth,
    bodyClient: document.body.clientWidth,
    bodyScroll: document.body.scrollWidth,
  }))
  expect(dimensions.documentScroll).toBeLessThanOrEqual(dimensions.documentClient)
  expect(dimensions.bodyScroll).toBeLessThanOrEqual(dimensions.bodyClient)
}

async function expectAxeClean(page, label) {
  const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
  expect(results.violations, `${label}: WCAG 2/2.1 A/AA violations`).toEqual([])
}

async function expectMinimumTarget(locator, {
  width = 48,
  height = 48,
  label,
} = {}) {
  const box = await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect()
    return { width: rect.width, height: rect.height }
  })
  expect(box.width, `${label ?? 'control'} target width`).toBeGreaterThanOrEqual(width)
  expect(box.height, `${label ?? 'control'} target height`).toBeGreaterThanOrEqual(height)
}

async function expectIntersectsViewport(locator, label) {
  const geometry = await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect()
    return {
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      left: rect.left,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
    }
  })
  expect(geometry.right, `${label} right edge`).toBeGreaterThan(0)
  expect(geometry.left, `${label} left edge`).toBeLessThan(geometry.viewportWidth)
  expect(geometry.bottom, `${label} bottom edge`).toBeGreaterThan(0)
  expect(geometry.top, `${label} top edge`).toBeLessThan(geometry.viewportHeight)
}

test('renders Scripture first with labelled reader structure and no overflow', async ({ page }) => {
  await openReader(page)

  await expect(page.getByRole('banner')).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Scripture reader actions' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Passage controls' })).toBeVisible()
  await expect(page.getByRole('main')).toHaveCount(1)
  await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Choose a book' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open study tools' })).toBeVisible()
  await expectNoHorizontalOverflow(page)

  const skipLink = page.getByRole('link', { name: 'Skip to main content' })
  await skipLink.focus()
  await skipLink.press('Enter')
  await expect(page.locator('#main-content')).toBeFocused()

  const lastVerse = page.getByRole('button', { name: /Genesis 1 verse 3/ })
  await lastVerse.scrollIntoViewIfNeeded()
  const navigation = page.getByRole('navigation', { name: 'Mobile reader navigation' })
  if (await navigation.isVisible()) {
    const geometry = await lastVerse.evaluate((verse) => {
      const navigationElement = document.querySelector('.reader-bottom-navigation')
      const verseRect = verse.getBoundingClientRect()
      const navigationRect = navigationElement.getBoundingClientRect()
      return {
        verseBottom: verseRect.bottom,
        navigationTop: navigationRect.top,
        navigationPosition: getComputedStyle(navigationElement).position,
      }
    })
    expect(Number.isFinite(geometry.verseBottom)).toBe(true)
    expect(Number.isFinite(geometry.navigationTop)).toBe(true)
    expect(geometry.navigationPosition).toBe('fixed')
    expect(geometry.verseBottom).toBeLessThanOrEqual(geometry.navigationTop)
  }
})

test('keeps primary controls visible at narrow and 200% zoom-equivalent layouts', async ({ page }, testInfo) => {
  test.skip(!['mobile-320', 'mobile-390'].includes(testInfo.project.name), 'narrow-layout coverage')
  await openReader(page)

  for (const name of ['Choose a book', 'Open study tools', 'Previous chapter', 'Next chapter', 'Change text size']) {
    await expect(page.getByRole('button', { name: new RegExp(name) })).toBeVisible()
  }
  await expect(page.getByLabel('Change translation')).toBeVisible()
  await expectNoHorizontalOverflow(page)

  if (testInfo.project.name === 'mobile-320') {
    await page.locator('.scripture-reader').evaluate((element) => { element.style.zoom = '2' })
    await expectNoHorizontalOverflow(page)
    for (const [locator, label] of [
      [page.getByRole('button', { name: 'Choose a book' }), 'book chooser'],
      [page.getByRole('button', { name: 'Open study tools' }), 'study tools'],
    ]) {
      await expect(locator).toBeVisible()
      await expectIntersectsViewport(locator, label)
    }

    const firstVerse = page.getByRole('button', { name: /Genesis 1 verse 1/ })
    await firstVerse.scrollIntoViewIfNeeded()
    await expect(firstVerse).toBeVisible()
    await expectIntersectsViewport(firstVerse, 'vertically reachable first verse')
    const verseAndNavigation = await firstVerse.evaluate((verse) => {
      const verseRect = verse.getBoundingClientRect()
      const navigationRect = document.querySelector('.reader-bottom-navigation')
        .getBoundingClientRect()
      return {
        verseTop: verseRect.top,
        verseBottom: verseRect.bottom,
        navigationTop: navigationRect.top,
      }
    })
    expect(verseAndNavigation.verseTop).toBeLessThan(verseAndNavigation.navigationTop)
    expect(verseAndNavigation.verseBottom).toBeGreaterThan(0)

    const textSize = page.getByRole('button', { name: /Change text size/ })
    await textSize.evaluate((element) => element.scrollIntoView({
      block: 'nearest',
      inline: 'center',
    }))
    await expect(textSize).toBeVisible()
    await expectIntersectsViewport(textSize, 'horizontally reachable text-size control')
  }
})

test('meets computed primary control target sizes in reader and modal states', async ({ page }) => {
  await openReader(page)

  const readerTargets = [
    ['Choose a book', page.getByRole('button', { name: 'Choose a book' })],
    ['Open study tools', page.getByRole('button', { name: 'Open study tools' })],
    ['Previous chapter', page.getByRole('button', { name: 'Previous chapter' })],
    ['Next chapter', page.getByRole('button', { name: 'Next chapter' })],
    ['Change text size', page.getByRole('button', { name: /Change text size/ })],
    ['Theme', page.getByRole('button', { name: /Use (light|dark) mode/ })],
    ['Translation selector', page.getByLabel('Change translation')],
  ]
  for (const [label, locator] of readerTargets) {
    await expectMinimumTarget(locator, { label })
  }

  const bottomNavigation = page.getByRole('navigation', { name: 'Mobile reader navigation' })
  if (await bottomNavigation.isVisible()) {
    for (const button of await bottomNavigation.getByRole('button').all()) {
      await expectMinimumTarget(button, { height: 52, label: 'bottom navigation' })
    }
  }

  await page.getByRole('button', { name: 'Choose a book' }).click()
  await expectMinimumTarget(page.getByRole('button', { name: 'Close book picker' }), {
    label: 'book picker close',
  })
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Open study tools' }).click()
  await expectMinimumTarget(page.getByRole('button', { name: 'Close study tools' }), {
    label: 'study tools close',
  })
})

test('persists real theme and text-size changes across reload', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'one persistent browser context is sufficient')
  await openReader(page)

  const reader = page.getByTestId('scripture-reader')
  const verse = page.locator('.scripture-pane').first()
  const before = await reader.evaluate((element) => getComputedStyle(element).backgroundColor)
  const beforeFontSize = await verse.evaluate((element) => getComputedStyle(element).fontSize)

  await page.getByRole('button', { name: 'Use light mode' }).click()
  await page.getByRole('button', { name: /Change text size/ }).click()
  const after = await reader.evaluate((element) => getComputedStyle(element).backgroundColor)
  const afterFontSize = await verse.evaluate((element) => getComputedStyle(element).fontSize)
  expect(after).not.toBe(before)
  expect(afterFontSize).not.toBe(beforeFontSize)
  await expect(page.locator('html')).toHaveAttribute('data-reader-theme', 'light')

  await page.reload()
  await expect(page.getByRole('heading', { level: 1, name: 'Genesis 1' })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-reader-theme', 'light')
  await expect(page.getByRole('button', { name: 'Use dark mode' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Current size: Large/ })).toBeVisible()
  expect(await page.getByTestId('scripture-reader').evaluate((element) => getComputedStyle(element).backgroundColor)).toBe(after)
  expect(await page.locator('.scripture-pane').evaluate((element) => getComputedStyle(element).fontSize)).toBe(afterFontSize)
})

test('book picker traps focus, supports Escape, restores its exact opener, and fits the viewport', async ({ page }) => {
  await openReader(page)
  const opener = page.getByRole('button', { name: 'Choose a book' })
  await opener.click()

  const dialog = page.getByRole('dialog', { name: 'Choose a book and chapter' })
  await expect(dialog).toBeVisible()
  await expect(dialog.locator(':focus')).toHaveCount(1)
  expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true)
  const box = await dialog.boundingBox()
  expect(box?.width).toBeLessThanOrEqual(page.viewportSize()?.width ?? 0)
  expect(box?.height).toBeLessThanOrEqual(page.viewportSize()?.height ?? 0)

  await page.getByLabel('Search Bible books').press('Shift+Tab')
  expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true)
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(opener).toBeFocused()
})

test('selected verse Study Tools expose all seven truthful destinations and restore focus', async ({ page }) => {
  await openReader(page)
  await page.getByRole('button', { name: /Genesis 1 verse 1/ }).click()
  await expect(page).toHaveURL(/verse=1/)

  const opener = page.getByRole('button', { name: 'Open study tools' })
  await opener.click()
  const dialog = page.getByRole('dialog', { name: 'Genesis 1:1' })
  await expect(dialog).toBeVisible()
  await expect(page.getByRole('heading', { level: 2, name: 'Genesis 1:1' })).toBeVisible()
  const close = dialog.getByRole('button', { name: 'Close study tools' })
  const last = dialog.getByRole('button', { name: 'Decolonial audit' })
  await expect(close).toBeFocused()
  await close.press('Shift+Tab')
  await expect(last).toBeFocused()
  await last.press('Tab')
  await expect(close).toBeFocused()

  for (const name of [
    'Context',
    'Compare translations',
    'Original languages',
    'Cross-references',
    'Notes',
    'Ask the Bible',
    'Decolonial audit',
  ]) {
    await expect(dialog.getByRole('button', { name })).toBeVisible()
    await expect(dialog.getByRole('button', { name })).toBeEnabled()
  }
  await expect(dialog.getByText(verseDetails.historical_context)).toBeVisible()
  await dialog.getByRole('button', { name: 'Compare translations' }).click()
  await expect(dialog.getByRole('heading', { level: 3, name: 'Compare translations' })).toBeVisible()
  await expect(dialog.getByText(chapters[1][1].text, { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: 'Original languages' }).click()
  await expect(dialog.getByText('bereshit', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: 'Cross-references' }).click()
  await expect(dialog.getByText('John 1:1', { exact: true })).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(opener).toBeFocused()
})

test('route Study Tools activate their real destinations from selected Genesis 1:2', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'route semantics do not vary by viewport')
  // Unit coverage verifies the selected reference object handed to onNavigate.
  // The browser boundary verifies each destination URL from the selected reader state.
  const destinations = [
    ['Notes', '#library'],
    ['Ask the Bible', '#aistudy'],
    ['Decolonial audit', '#race-misuse'],
  ]

  for (const [tool, hash] of destinations) {
    await openReader(page)
    await page.getByRole('button', { name: /Genesis 1 verse 2/ }).click()
    await expect(page).toHaveURL(/verse=2/)
    await page.getByRole('button', { name: 'Open study tools' }).click()
    await expect(page.getByRole('dialog', { name: 'Genesis 1:2' })).toBeVisible()
    await page.getByRole('button', { name: tool }).click()
    await expect(page).toHaveURL(new RegExp(`${hash}$`))
  }
})

test('search follows the real keyboard combobox flow and restores its opener', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-390', 'the search opener is the mobile word-labelled navigation')
  await openReader(page)
  const opener = page.getByRole('button', { name: 'Search' })
  await opener.click()
  const dialog = page.getByRole('dialog', { name: 'Search' })
  const input = page.getByRole('combobox', { name: 'Search the library' })
  await expect(input).toBeFocused()
  await input.fill('Genesis')
  await expect(page.getByRole('option', { name: /Genesis 1:1/ })).toBeVisible()
  await input.press('ArrowDown')
  await expect(input).toHaveAttribute('aria-activedescendant', /option-0$/)
  await expect(page.getByRole('option', { name: /Genesis 1:1/ })).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(opener).toBeFocused()
})

test('chapter bounds, translations, hashes, and browser history remain deterministic', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'history semantics do not vary by viewport')
  await openReader(page)
  await expect(page.getByRole('button', { name: 'Previous chapter' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Next chapter' })).toBeEnabled()

  await page.getByLabel('Change translation').selectOption('ETH81')
  await expect(page.getByText(chapters[1][1].text, { exact: true })).toBeVisible()
  await expect(page).toHaveURL(/translation=ETH81/)
  await page.getByRole('button', { name: 'Next chapter' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Genesis 2' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Next chapter' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Previous chapter' })).toBeEnabled()

  await page.goBack()
  await expect(page.getByRole('heading', { level: 1, name: 'Genesis 1' })).toBeVisible()
  await expect(page.getByText(chapters[1][1].text, { exact: true })).toBeVisible()
  await page.goForward()
  await expect(page.getByRole('heading', { level: 1, name: 'Genesis 2' })).toBeVisible()
})

test('an intercepted chapter error preserves selection and offers a working recovery action', async ({ page, browserDiagnostics }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'one browser recovery journey is sufficient')
  let attempts = 0
  await page.route('**/api/biblical-texts/chapter-content?**', (route) => {
    attempts += 1
    if (attempts === 1) return route.fulfill({ status: 503, json: { detail: 'fixture outage' } })
    return route.fulfill({ json: { content: chapters[1] } })
  })

  await page.goto(READER_URL)
  await expect(page.getByRole('heading', { name: 'Could not open Genesis 1' })).toBeVisible()
  const expectedFixtureError = browserDiagnostics.findIndex(
    (message) => message === 'console: Failed to load resource: the server responded with a status of 503 (Service Unavailable)',
  )
  expect(expectedFixtureError, 'the deterministic 503 should reach the browser').toBeGreaterThanOrEqual(0)
  browserDiagnostics.splice(expectedFixtureError, 1)
  await expect(page).toHaveURL(/book=Genesis.*chapter=1.*translation=KJV/)
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Genesis 1' })).toBeVisible()
  expect(attempts).toBe(2)
})

test('axe finds no WCAG A/AA violations in ready light and dark reader states', async ({ page }) => {
  await openReader(page)
  await expectAxeClean(page, 'dark reader')
  await page.getByRole('button', { name: 'Use light mode' }).click()
  await expectAxeClean(page, 'light reader')
})

test('axe finds no WCAG A/AA violations in book picker and Study Tools', async ({ page }) => {
  await openReader(page)
  await page.getByRole('button', { name: 'Choose a book' }).click()
  await expectAxeClean(page, 'book picker')
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: /Genesis 1 verse 1/ }).click()
  await page.getByRole('button', { name: 'Open study tools' }).click()
  await expect(page.getByRole('dialog', { name: 'Genesis 1:1' })).toBeVisible()
  await expectAxeClean(page, 'study tools')
})

test('axe finds no WCAG A/AA violations in the keyboard search dialog', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-390', 'search is exposed in the mobile navigation')
  await openReader(page)
  await page.getByRole('button', { name: 'Search' }).click()
  await page.getByRole('combobox', { name: 'Search the library' }).fill('Genesis')
  await expect(page.getByRole('option', { name: /Genesis 1:1/ })).toBeVisible()
  await expectAxeClean(page, 'search dialog')
})

test('reduced motion keeps the complete reader and all primary actions available', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'media preference behavior is viewport-independent')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await openReader(page)
  await expect(page.getByRole('button', { name: 'Choose a book' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Open study tools' })).toBeEnabled()
  await expect(page.getByRole('button', { name: /Genesis 1 verse 1/ })).toBeEnabled()
})
