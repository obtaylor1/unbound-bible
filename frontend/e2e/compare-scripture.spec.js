import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const edition = (code, name) => ({ code, name, language: 'English' })
const workSource = (sourceLabel, sourceTradition = 'Protestant') => ({
  source_label: sourceLabel,
  source_tradition: sourceTradition,
  verification_status: 'verified',
  canon_scope: 'ethio81',
})
const compositeGenesisSource = {
  source_label: 'World Messianic Bible (archive revision unverified)',
  source_tradition: 'Hebrew Masoretic tradition',
  source_language: 'Hebrew',
  verification_status: 'provisional',
  canon_scope: 'ethio81',
}
const row = (translation, name, text, verse = 1, tradition = 'Protestant') => ({
  book: 'Genesis', chapter: 1, verse, translation, text,
  edition: edition(translation, name),
  work_source: workSource(name, tradition),
})

const rows = [
  {
    ...row('EOTC-COMPOSITE-EN', 'Ethiopian Orthodox Bible — Composite English Edition', 'In the beginning God created the heavens and the earth.'),
    work_source: compositeGenesisSource,
  },
  row('KJV', 'King James Version', 'In the beginning God created the heaven and the earth.'),
  row('ASV', 'American Standard Version', 'In the beginning God created the heavens and the earth.'),
  row('WEB', 'World English Bible', 'In the beginning, God created the heavens and the earth.'),
  row('NLT', 'New Living Translation', 'In the beginning God created the heavens and the earth.'),
  row('KJV', 'King James Version', 'The earth was formless and empty.', 2),
]

async function openComparison(page) {
  await page.route('**/api/biblical-texts/available-books', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ books: ['Genesis', '1 Enoch'] }),
  }))
  await page.route('**/api/biblical-texts/chapter-content**', (route) => {
    const content = route.request().url().includes('book=1%20Enoch')
      ? [{
          book: '1 Enoch', chapter: 1, verse: 1, translation: '1EN_CH',
          edition: edition('1EN_CH', '1 Enoch, R. H. Charles'),
          work_source: workSource('R. H. Charles translation', 'Ethiopian Pseudepigrapha'),
          text: 'The words of the blessing of Enoch.',
        }]
      : rows
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ content }) })
  })
  await page.route('**/api/v1/texts/**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ cross_references: [], commentary: [], original_words: [] }),
  }))
  await page.goto('/#compare')
  await expect(page.getByRole('heading', { name: 'Compare translations' })).toBeVisible()
}

async function openSourcesIfCollapsed(page) {
  const trigger = page.getByRole('button', { name: /Choose translations/ })
  if (await trigger.isVisible()) await trigger.click()
}

async function closeSourcesIfExpanded(page) {
  const close = page.getByRole('button', { name: 'Close translation selector' })
  if (await close.isVisible()) await close.click()
}

async function expectSourceCount(page, count) {
  const trigger = page.getByRole('button', { name: /Choose translations/ })
  if (await trigger.isVisible()) await expect(trigger).toContainText(`${count}/4`)
  else await expect(page.getByText(`Comparing ${count} translations`)).toBeVisible()
}

test('compares the recommended composite edition with the KJV by default', async ({ page }) => {
  await openComparison(page)

  await expectSourceCount(page, 2)
  const composite = page.getByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition' })
  await expect(composite).toContainText('In the beginning God created the heavens and the earth.')
  await expect(composite).toContainText('World Messianic Bible (archive revision unverified)')
  await expect(composite).toContainText('Provisional source')
  await expect(page.getByRole('article', { name: 'King James Version' })).toContainText('In the beginning God created the heaven and the earth.')
  await expect(page.getByRole('dialog', { name: 'Study Tools' })).toBeHidden()
})

test('caps comparison at four sources and aligns the chapter view', async ({ page }) => {
  await openComparison(page)
  await openSourcesIfCollapsed(page)

  await page.getByRole('checkbox', { name: 'American Standard Version, ASV' }).check()
  await page.getByRole('checkbox', { name: 'World English Bible, WEB' }).check()
  await expect(page.getByText('Comparing 4 translations')).toBeVisible()
  await expect(page.getByRole('checkbox', { name: 'New Living Translation, NLT' })).toBeDisabled()
  await closeSourcesIfExpanded(page)

  await page.getByRole('button', { name: 'Chapter view' }).click()
  await expect(page.getByRole('heading', { name: 'Genesis chapter 1 comparison' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Verse 2' })).toBeVisible()
})

test('opens and keyboard-dismisses Study Tools', async ({ page }) => {
  await openComparison(page)

  const trigger = page.getByRole('button', { name: 'Open Study Tools' })
  await trigger.click()
  await expect(page.getByRole('dialog', { name: 'Study Tools' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Close Study Tools' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: 'Study Tools' })).toBeHidden()
  await expect(trigger).toBeFocused()
})

test('fits without horizontal overflow', async ({ page }) => {
  await openComparison(page)

  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }))
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport)
})

test('opens an Ethiopian-canon source from the passage selector', async ({ page }) => {
  await openComparison(page)

  await page.getByRole('combobox', { name: 'Book' }).selectOption('1 Enoch')
  await openSourcesIfCollapsed(page)
  await page.getByRole('checkbox', { name: '1 Enoch, R. H. Charles, 1EN_CH' }).check()
  await closeSourcesIfExpanded(page)
  await expect(page.getByRole('article', { name: '1 Enoch, R. H. Charles' })).toContainText('The words of the blessing of Enoch.')
})

test('has no automated accessibility violations in the workspace', async ({ page }) => {
  await openComparison(page)

  const results = await new AxeBuilder({ page })
    .include('[data-testid="comparison-workspace"]')
    .analyze()
  expect(results.violations).toEqual([])
})
