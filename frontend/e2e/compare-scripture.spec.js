import { expect, test } from '@playwright/test'

const rows = [
  { book: 'Genesis', chapter: 1, verse: 1, translation: 'KJV', text: 'In the beginning God created the heaven and the earth.' },
  { book: 'Genesis', chapter: 1, verse: 1, translation: 'ASV', text: 'In the beginning God created the heavens and the earth.' },
  { book: 'Genesis', chapter: 1, verse: 1, translation: 'WEB', text: 'In the beginning, God created the heavens and the earth.' },
  { book: 'Genesis', chapter: 1, verse: 2, translation: 'KJV', text: 'The earth was formless and empty.' },
]

async function openComparison(page) {
  await page.route('**/api/biblical-texts/available-books', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ books: ['Genesis', '1 Enoch'] }),
  }))
  await page.route('**/api/biblical-texts/chapter-content**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ content: rows }),
  }))
  await page.route('**/api/v1/texts/**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ cross_references: [], commentary: [], original_words: [] }),
  }))
  await page.goto('/#compare')
  await expect(page.getByRole('heading', { name: 'Compare translations' })).toBeVisible()
}

test('compares two default sources and keeps unavailable text accurate', async ({ page }) => {
  await openComparison(page)

  await expect(page.getByText('Comparing 2 translations')).toBeVisible()
  await expect(page.getByRole('article', { name: 'Ethiopian Orthodox Critical Text' })).toContainText('Text unavailable')
  await expect(page.getByRole('article', { name: 'King James Version' })).toContainText('In the beginning God created the heaven and the earth.')
  await expect(page.getByRole('dialog', { name: 'Study Tools' })).toBeHidden()
})

test('caps comparison at four sources and aligns the chapter view', async ({ page }) => {
  await openComparison(page)

  await page.getByRole('checkbox', { name: 'American Standard Version, ASV' }).check()
  await page.getByRole('checkbox', { name: 'World English Bible, WEB' }).check()
  await expect(page.getByText('Comparing 4 translations')).toBeVisible()
  await expect(page.getByRole('checkbox', { name: 'New Living Translation, NLT' })).toBeDisabled()

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
