import { test, expect } from '@playwright/test'

const register = async (page) => {
  await page.goto('/#home')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('button', { name: 'New here? Create an account' }).click()
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`
  await page.getByLabel('Username').fill(`reader-${suffix}`.slice(0, 50))
  await page.getByLabel('Email').fill(`reader-${suffix}@example.com`)
  await page.getByLabel('Password').fill('correct-horse-battery-staple')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('button', { name: new RegExp('reader-') })).toBeVisible()
}

test('account, grounded study, durable save, and immutable sharing', async ({ page, context }) => {
  await register(page)
  await page.goto('/#aistudy')
  const question = 'What does Genesis 1:1 say?'
  await page.getByLabel('Research question').fill(question)
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  await expect(page.getByRole('heading', { name: question, exact: true })).toBeVisible()
  await expect(page.getByLabel('Research result actions')).toBeVisible()
  await page.getByRole('button', { name: 'Save research' }).click()
  await expect(page.getByText('Research saved privately to My Library.')).toBeVisible()
  await page.getByRole('button', { name: 'Share research' }).click()
  await page.getByRole('button', { name: 'Create link' }).click()
  const url = await page.getByLabel('Share link').inputValue()
  const anonymous = await context.newPage()
  await anonymous.goto(url)
  await expect(anonymous.getByRole('heading', { name: 'Sources' })).toBeVisible()
  const sharedReferences = anonymous.getByText('Genesis 1:1', { exact: true })
  expect(await sharedReferences.count()).toBeGreaterThan(0)
})

test('refresh restoration and logout', async ({ page }) => {
  await register(page)
  await page.reload()
  await expect(page.getByRole('button', { name: /reader-/ })).toBeVisible()
  await page.getByRole('button', { name: /reader-/ }).click()
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
})
