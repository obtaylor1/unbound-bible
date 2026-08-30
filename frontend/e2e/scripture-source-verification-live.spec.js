import { expect, test } from '@playwright/test'
import process from 'node:process'

const LIVE = process.env.LIVE_SOURCE_E2E === '1'
const READER = '/#scriptures?book=Genesis&chapter=1&translation=EOTC-COMPOSITE-EN&canon=ETHIO81'

test.describe('isolated published scripture release', () => {
  test.skip(!LIVE, 'requires the documented isolated published API rehearsal')

  test('serves real reader, search, comparison, commentary, research, and authorization flows', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop-chromium', 'one canonical live release audit')
    await page.goto(READER)
    await expect(page.getByRole('heading', { level: 1, name: 'Genesis 1' })).toBeVisible()
    await expect(page.getByText('In the beginning, God created the heavens and the earth.', { exact: true })).toBeVisible()
    const source = page.getByRole('region', { name: 'Text source' })
    await expect(source.getByText('World Messianic Bible', { exact: true })).toBeVisible()
    await expect(source.getByText('Rebuilt from verified source', { exact: true })).toBeVisible()

    await page.getByRole('button', { name: 'Search', exact: true }).click()
    await page.getByRole('combobox', { name: 'Search the library' }).fill('Genesis')
    await expect(page.getByRole('option', { name: /Genesis 1:1/ })).toBeVisible()

    await page.goto('/#compare?book=Genesis&chapter=1&verse=1&translation=EOTC-COMPOSITE-EN&canon=ETHIO81')
    await expect(page.getByRole('heading', { name: 'Compare translations' })).toBeVisible()
    await expect(page.getByRole('article', {
      name: 'Ethiopian Canon Research Collection — Mixed-source English',
    })).toContainText('In the beginning, God created the heavens and the earth.')

    await page.goto(READER)
    await page.getByRole('button', { name: /^Genesis 1 verse 1\b/ }).click()
    await page.getByRole('button', { name: 'Open study tools' }).click()
    await page.getByRole('button', { name: 'Commentary' }).click()
    await expect(page.getByRole('heading', { name: 'No commentary sources are installed.' })).toBeVisible()

    // Research is presently a local frontend route with no backend research
    // router; its scripture discovery boundary is the real search API above.
    await page.goto('/#research')
    await expect(page.getByRole('main', { name: 'Research' })).toBeVisible()

    await page.goto('/#admin-scripture-verification')
    await expect(page.getByRole('heading', { name: 'Sign in to review sources' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Scripture source verification' })).toHaveCount(0)
  })

  test('keeps authenticated saving and immutable sharing inside the isolated rehearsal', async ({ page, context }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop-chromium', 'one canonical live release audit')
    const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    await page.goto('/#home')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await page.getByRole('button', { name: 'New here? Create an account' }).click()
    await page.getByLabel('Username').fill(`release-${suffix}`.slice(0, 50))
    await page.getByLabel('Email').fill(`release-${suffix}@example.com`)
    await page.getByLabel('Password').fill('correct-horse-battery-staple')
    await page.getByRole('button', { name: 'Create account' }).click()

    await page.goto('/#aistudy')
    await page.getByLabel('Ask a biblical study question').fill('What does Genesis 1:1 say?')
    await page.getByRole('button', { name: '⌕ Search' }).click()
    await page.getByRole('button', { name: '💾 Save Study Session' }).click()
    await expect(page.getByText('Study session saved privately to My Library.')).toBeVisible()
    await page.getByRole('button', { name: '🔗 Share Study Session' }).click()
    await page.getByRole('button', { name: 'Create link' }).click()
    const shareUrl = await page.getByLabel('Share link').inputValue()
    const anonymous = await context.newPage()
    await anonymous.goto(shareUrl)
    await expect(anonymous.getByRole('heading', { name: 'Sources' })).toBeVisible()
  })
})
