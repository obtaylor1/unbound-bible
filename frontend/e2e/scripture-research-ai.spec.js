import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const eventsResponse = {
  events: [
    {
      id: 'eden-expulsion', title: 'Expulsion from Eden', description: 'Adam and Eve leave Eden.',
      reference: 'Genesis 3:22–24', source_ids: ['genesis-3'], people: ['Adam', 'Eve'], places: ['Eden'],
      ordering_group: 'genesis-2-4', ordinal: 1,
    },
    {
      id: 'abel-killed', title: 'Abel is killed', description: 'Cain kills Abel.',
      reference: 'Genesis 4:8', source_ids: ['genesis-4'], people: ['Cain', 'Abel'], places: [],
      ordering_group: 'genesis-2-4', ordinal: 2,
    },
  ],
}

const researchResponse = {
  id: '11111111-1111-4111-8111-111111111111',
  query: 'What happened between Eden and Abel?', mode: 'what-happened-between',
  settings: { source_scopes: ['biblical-canon'], depth: 'deep-research', mode_parameters: {} },
  summary: {
    title: 'Overview', narrative: null,
    claims: [{
      id: 'claim-1', statement: 'Genesis records the expulsion, births, offerings, and Abel’s death.',
      classification: 'canonical-scripture', confidence: 'high', source_ids: ['genesis-3'],
    }],
  },
  timeline: [{
    title: 'Expulsion from Eden', description: 'Adam and Eve leave Eden.',
    date_label: 'Early Genesis narrative', source_ids: ['genesis-3'], confidence: 'high',
  }],
  canonical_account: null, ancient_accounts: [], historical_context: null, language_notes: [], unknowns: null,
  related_questions: ['What happened to Cain after Abel’s death?'],
  people: [{ name: 'Adam', description: 'The first man.', role: 'First man', source_ids: ['genesis-3'] }],
  places: [{ name: 'Eden', description: 'The garden in Genesis.', location: null, source_ids: ['genesis-3'] }],
  sources: [{
    id: 'genesis-3', title: 'Genesis', reference: 'Genesis 3:22–24',
    excerpt: 'Therefore the LORD God sent him forth from the garden of Eden.', text: null,
    source_type: 'canonical-scripture', tradition: 'Biblical Canon', date_or_era: null,
    original_language: 'Hebrew', translation: 'KJV', relevance: 'Direct canonical account',
    open_target: '#scriptures?book=Genesis&chapter=3',
  }],
  grounding_status: 'grounded', provider: 'library-provider', model: 'grounded-v1', trail_node: null,
}

async function mockResearchRoutes(page, { delayedQuery = false } = {}) {
  await page.route('**/api/v1/research/events**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(eventsResponse),
  }))
  await page.route('**/api/v1/research/query', async (route) => {
    if (delayedQuery) await new Promise((resolve) => setTimeout(resolve, 5_000))
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(researchResponse) })
  })
}

async function openResearch(page) {
  await mockResearchRoutes(page)
  await page.goto('/#aistudy')
  await expect(page.getByRole('heading', { level: 1, name: /Scripture Research AI/ })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Scripture research composer' })).toBeVisible()
}

for (const viewport of [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
]) {
  test(`${viewport.name} research workspace is readable, accessible, and overflow-free`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await openResearch(page)
    await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1)
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }))
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport)

    const smallestControl = await page.locator('.scripture-research-page button:visible').evaluateAll((buttons) => (
      Math.min(...buttons.map((button) => button.getBoundingClientRect().height))
    ))
    expect(smallestControl).toBeGreaterThanOrEqual(44)
    const pageSurface = await page.locator('.scripture-research-page').evaluate((element) => ({
      background: getComputedStyle(element).backgroundColor,
      maxWidth: getComputedStyle(element).maxWidth,
    }))
    expect(pageSurface.background).not.toBe('rgba(0, 0, 0, 0)')
    expect(pageSurface.maxWidth).toBe('1560px')

    const results = await new AxeBuilder({ page }).include('.scripture-research-page').analyze()
    expect(results.violations.filter(({ impact }) => ['serious', 'critical'].includes(impact))).toEqual([])
  })
}

test('reduced motion loading state has no continuously animated element', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockResearchRoutes(page, { delayedQuery: true })
  await page.goto('/#aistudy')
  await page.getByLabel('Research question').fill('What happened between Eden and Abel?')
  await page.getByRole('button', { name: /Ask/ }).click()
  await expect(page.getByRole('heading', { name: 'Building your grounded research' })).toBeVisible()
  const continuouslyAnimated = await page.locator('.research-loading, .research-loading *').evaluateAll((elements) => (
    elements.some((element) => {
      const style = getComputedStyle(element)
      const iterations = style.animationIterationCount.split(',').map((value) => value.trim())
      return style.animationName !== 'none' && iterations.some((value) => value === 'infinite' || Number(value) > 1)
    })
  ))
  expect(continuouslyAnimated).toBe(false)
})
