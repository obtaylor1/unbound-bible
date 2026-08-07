import { test, expect } from '@playwright/test'

test('keyboard search and honest empty states', async ({ page }) => {
  await page.goto('/#home')
  await page.keyboard.press('ControlOrMeta+K')
  const search = page.getByLabel('Search the library')
  await expect(search).toBeFocused()
  await search.fill('Genesis')
  await expect(page.getByRole('option', { name: /Genesis 1:1/ })).toBeVisible()
  await search.press('ArrowDown'); await search.press('Enter')
  await expect(page).toHaveURL(/#scriptures/)
})

test('community uses the unified session and reveals no email', async ({ page }) => {
  await page.goto('/#community')
  await expect(page.getByRole('heading', { name: 'Study in conversation' })).toBeVisible()
  await expect(page.getByText('Sign in above to participate.')).toBeVisible()
  await expect(page.locator('main')).not.toContainText('@example.com')
})
