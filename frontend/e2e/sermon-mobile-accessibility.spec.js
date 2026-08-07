import { test, expect } from '@playwright/test'

test('keyboard navigation and accessible landmarks', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name.includes('mobile'), 'Touch emulation does not expose hardware Tab focus behavior')
  await page.goto('/#home')
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible()
  await expect(page.getByRole('main')).toBeVisible()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused()
})

test('390px layout has no horizontal overflow', async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.includes('mobile'))
  await page.goto('/#aistudy')
  const dimensions = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }))
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 1)
  await expect(page.getByLabel('Open navigation')).toBeVisible()
})
