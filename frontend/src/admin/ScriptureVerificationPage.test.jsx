import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { readFileSync } from 'node:fs'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AuthContext } from '../auth/authContext'
import {
  fetchScriptureVerificationInventory,
  normalizeScriptureVerificationInventory,
} from './scriptureVerificationApi'
import ScriptureVerificationPage from './ScriptureVerificationPage'

vi.mock('./scriptureVerificationApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchScriptureVerificationInventory: vi.fn(),
  }
})

const STATUS_LABELS = {
  in_progress: 'Source verification in progress',
  verified_exact: 'Source verified',
  verified_formatting: 'Verified with documented formatting changes',
  verified_rebuilt: 'Rebuilt from verified source',
  review_required: 'Source review required',
}

const FAMILY_FIXTURES = [
  ['world-messianic-bible', 'World Messianic Bible', [
    'genesis', 'exodus', 'leviticus', 'numbers', 'deuteronomy', 'joshua',
    'judges', 'ruth', '1-samuel', '2-samuel', '1-kings', '2-kings',
    '1-chronicles', '2-chronicles', 'ezra', 'nehemiah', 'esther', 'job',
    'psalms', 'proverbs', 'ecclesiastes', 'song-of-solomon', 'isaiah',
    'jeremiah', 'lamentations', 'ezekiel', 'daniel', 'hosea', 'joel', 'amos',
    'obadiah', 'jonah', 'micah', 'nahum', 'habakkuk', 'zephaniah', 'haggai',
    'zechariah', 'malachi',
  ]],
  ['murdock-peshitta-1852', 'Murdock Peshitta', [
    'matthew', 'mark', 'luke', 'john', 'acts', 'romans', '1-corinthians',
    '2-corinthians', 'galatians', 'ephesians', 'philippians', 'colossians',
    '1-thessalonians', '2-thessalonians', '1-timothy', '2-timothy', 'titus',
    'philemon', 'hebrews', 'james', '1-peter', '2-peter', '1-john', '2-john',
    '3-john', 'jude', 'revelation',
  ]],
  ['kjv-1611-fallback', 'KJV 1611 fallback', [
    'baruch', 'letter-of-jeremiah', 'prayer-of-azariah', 'susanna',
    'bel-and-the-dragon', 'prayer-of-manasseh',
  ]],
  ['rh-charles-ethiopic', 'R. H. Charles Jubilees', ['jubilees']],
  ['world-english-bible-apocrypha', 'World English Bible Apocrypha', [
    'ezra-sutuel', 'second-ezra', 'tobit', 'judith', 'wisdom-of-solomon', 'sirach',
  ]],
  ['wikisource-meqabyan-geez', "Wikisource Meqabyan from Ge'ez", [
    '1-meqabyan', '2-meqabyan', '3-meqabyan',
  ]],
  ['rh-charles-ethiopic', 'R. H. Charles 1 Enoch', ['1-enoch']],
]

function work({ sourceKey, sourceLabel, workId, index, verified = false }) {
  const status = verified ? 'verified_exact' : 'in_progress'
  return {
    work_id: workId,
    work_name: workId === 'jubilees' ? 'Jubilees' : `Work ${index + 1}`,
    source_key: sourceKey,
    source_label: sourceLabel,
    source_edition: index === 0 ? 'Reviewed edition' : null,
    source_revision: index === 0 ? '2026-08' : null,
    provenance_url: 'https://example.org/source',
    rights_url: 'https://example.org/rights',
    license: 'Public domain',
    fallback: sourceKey === 'kjv-1611-fallback',
    canon_scope: 'ethio81',
    artifact_sha256: `${index + 1}`.padStart(64, '0'),
    comparison_report_sha256: `${index + 101}`.padStart(64, '0'),
    comparison: { exact: index + 1, formatting: 2, missing: 0, extra: 0, wording: 0 },
    reviewer: verified ? 'Source Review Team' : null,
    reviewed_at: verified ? '2026-08-17T13:00:00Z' : null,
    verification: { status, label: STATUS_LABELS[status], verified_at: verified ? '2026-08-17T13:00:00Z' : null },
  }
}

function completeInventory() {
  let index = 0
  const works = FAMILY_FIXTURES.flatMap(([sourceKey, sourceLabel, workIds], familyIndex) => (
    workIds.map((workId) => {
      const row = work({
        sourceKey,
        sourceLabel,
        workId,
        index,
        verified: familyIndex >= 4,
      })
      index += 1
      return row
    })
  ))
  return {
    edition_code: 'EOTC-COMPOSITE-EN',
    total_works: 83,
    family_totals: [
      { source_key: 'kjv-1611-fallback', count: 6 },
      { source_key: 'murdock-peshitta-1852', count: 27 },
      { source_key: 'rh-charles-ethiopic', count: 2 },
      { source_key: 'wikisource-meqabyan-geez', count: 3 },
      { source_key: 'world-english-bible-apocrypha', count: 6 },
      { source_key: 'world-messianic-bible', count: 39 },
    ],
    status_totals: [
      { status: 'in_progress', label: STATUS_LABELS.in_progress, count: 73 },
      { status: 'verified_exact', label: STATUS_LABELS.verified_exact, count: 10 },
      { status: 'verified_formatting', label: STATUS_LABELS.verified_formatting, count: 0 },
      { status: 'verified_rebuilt', label: STATUS_LABELS.verified_rebuilt, count: 0 },
      { status: 'review_required', label: STATUS_LABELS.review_required, count: 0 },
    ],
    works,
  }
}

const authValue = {
  status: 'authenticated',
  user: { id: 'admin-1', email: 'admin@example.com', username: 'admin', role: 'admin' },
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}

function renderPage() {
  return render(
    <AuthContext.Provider value={authValue}>
      <ScriptureVerificationPage />
    </AuthContext.Provider>,
  )
}

function synchronizeStatusTotals(payload) {
  payload.status_totals = Object.entries(STATUS_LABELS).map(([status, label]) => ({
    status,
    label,
    count: payload.works.filter((row) => row.verification.status === status).length,
  }))
  return payload
}

function AuthenticationHarness({ role = 'admin' }) {
  const [auth, setAuth] = useState({ status: 'anonymous', user: null })
  const login = async () => {
    const user = { id: `${role}-1`, email: `${role}@example.com`, username: role, role }
    setAuth({ status: 'authenticated', user })
    return user
  }
  return (
    <AuthContext.Provider value={{ ...auth, login, register: vi.fn(), logout: vi.fn() }}>
      <ScriptureVerificationPage />
    </AuthContext.Provider>
  )
}

describe('ScriptureVerificationPage', () => {
  beforeEach(() => {
    fetchScriptureVerificationInventory.mockResolvedValue(
      normalizeScriptureVerificationInventory(completeInventory()),
    )
  })

  afterEach(() => {
    vi.clearAllMocks()
    window.location.hash = ''
  })

  it('summarizes the supplied works without a false completion claim', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Scripture source verification' })).toBeVisible()
    expect(screen.getByText('83 supplied works')).toBeVisible()
    expect(screen.getByText('73 awaiting exact provenance')).toBeVisible()
    expect(screen.queryByText(/complete ethiopian bible/i)).not.toBeInTheDocument()
  })

  it('groups the four affected families before already-provenanced works', async () => {
    renderPage()
    await screen.findByText('83 supplied works')

    const groupNames = screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent)
    expect(groupNames).toEqual([
      'World Messianic Bible',
      'Murdock Peshitta',
      'KJV fallback works',
      'R. H. Charles Jubilees',
      'Already-provenanced works',
    ])
    expect(screen.getByText('39 works')).toBeVisible()
    expect(screen.getByText('27 works')).toBeVisible()
    expect(screen.getByText('6 works')).toBeVisible()
    expect(screen.getByText('1 work')).toBeVisible()
    expect(screen.getByText('10 works')).toBeVisible()
  })

  it('filters by status, source family, and search with a clear result count', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Showing 83 of 83 works')

    await user.selectOptions(screen.getByLabelText('Filter by verification status'), 'verified_exact')
    expect(screen.getByText('Showing 10 of 83 works')).toBeVisible()

    await user.selectOptions(screen.getByLabelText('Filter by source family'), 'already-provenanced')
    expect(screen.getByText('Showing 10 of 83 works')).toBeVisible()

    await user.type(screen.getByRole('searchbox', { name: 'Search supplied works' }), '1 Enoch')
    expect(screen.getByText('Showing 1 of 83 works')).toBeVisible()
    expect(screen.getByRole('rowheader', { name: /Work 83/ })).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getByText('Showing 83 of 83 works')).toBeVisible()
  })

  it('uses keyboard-reachable semantic disclosure for safe review evidence', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('83 supplied works')

    const firstTable = screen.getAllByRole('table')[0]
    expect(within(firstTable).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
      'Work', 'Verification', 'Source', 'Evidence',
    ])
    const disclosure = within(firstTable).getAllByText('Review evidence')[0]
    disclosure.focus()
    expect(disclosure).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(disclosure.closest('details')).toHaveAttribute('open')
    expect(within(disclosure.closest('details')).getByText('Artifact checksum')).toBeVisible()
    expect(within(disclosure.closest('details')).getByRole('link', { name: 'Source record' })).toHaveAttribute('href', 'https://example.org/source')
  })

  it('renders partial evidence and empty filtered results meaningfully', async () => {
    const payload = completeInventory()
    payload.works[0] = {
      ...payload.works[0],
      artifact_sha256: null,
      comparison_report_sha256: null,
      reviewer: null,
      reviewed_at: null,
      provenance_url: null,
      rights_url: null,
      comparison: { exact: 0, formatting: 0, missing: 0, extra: 0, wording: 0 },
    }
    fetchScriptureVerificationInventory.mockResolvedValue(
      normalizeScriptureVerificationInventory(payload),
    )
    const user = userEvent.setup()
    renderPage()

    await user.type(await screen.findByRole('searchbox', { name: 'Search supplied works' }), 'genesis')
    expect(await screen.findByText('Evidence pending')).toBeVisible()
    await user.clear(screen.getByRole('searchbox', { name: 'Search supplied works' }))
    await user.type(screen.getByRole('searchbox', { name: 'Search supplied works' }), 'not present')
    expect(screen.getByRole('status')).toHaveTextContent('No supplied works match these filters.')
  })

  it('offers sign-in after 401 and explains administrator access after 403', async () => {
    const user = userEvent.setup()
    const unauthorized = Object.assign(new Error('Unauthorized'), { status: 401 })
    fetchScriptureVerificationInventory.mockRejectedValueOnce(unauthorized)
    const { unmount } = renderPage()

    expect(await screen.findByRole('heading', { name: 'Sign in to review sources' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByRole('dialog', { name: 'Welcome back' })).toBeVisible()
    unmount()

    const forbidden = Object.assign(new Error('Forbidden'), { status: 403 })
    fetchScriptureVerificationInventory.mockRejectedValueOnce(forbidden)
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Administrator access required' })).toBeVisible()
  })

  it('opens sign-in after an anonymous 401 and reloads the inventory after an administrator signs in', async () => {
    const user = userEvent.setup()
    fetchScriptureVerificationInventory
      .mockRejectedValueOnce(Object.assign(new Error('Unauthorized'), { status: 401 }))
      .mockResolvedValueOnce(normalizeScriptureVerificationInventory(completeInventory()))

    render(<AuthenticationHarness />)

    expect(await screen.findByRole('dialog', { name: 'Welcome back' })).toBeVisible()
    await user.type(screen.getByLabelText('Email'), 'admin@example.com')
    await user.type(screen.getByLabelText('Password'), 'long-enough-password')
    await user.click(within(screen.getByRole('dialog', { name: 'Welcome back' })).getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('83 supplied works')).toBeVisible()
    expect(screen.queryByRole('dialog', { name: 'Welcome back' })).not.toBeInTheDocument()
    expect(fetchScriptureVerificationInventory).toHaveBeenCalledTimes(2)
  })

  it('shows the backend permission state when a newly signed-in member receives 403', async () => {
    const user = userEvent.setup()
    fetchScriptureVerificationInventory
      .mockRejectedValueOnce(Object.assign(new Error('Unauthorized'), { status: 401 }))
      .mockRejectedValueOnce(Object.assign(new Error('Forbidden'), { status: 403 }))

    render(<AuthenticationHarness role="member" />)

    await user.type(await screen.findByLabelText('Email'), 'member@example.com')
    await user.type(screen.getByLabelText('Password'), 'long-enough-password')
    await user.click(within(screen.getByRole('dialog', { name: 'Welcome back' })).getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Administrator access required' })).toBeVisible()
    expect(screen.queryByRole('dialog', { name: 'Welcome back' })).not.toBeInTheDocument()
    expect(fetchScriptureVerificationInventory).toHaveBeenCalledTimes(2)
  })

  it('derives current, mixed, and completed family status copy from work statuses', async () => {
    const { unmount } = renderPage()
    await screen.findByText('83 supplied works')
    let family = screen.getByRole('heading', { name: 'World Messianic Bible' }).closest('section')
    expect(within(family).getByText('Awaiting review')).toBeVisible()
    expect(family.querySelector('.verification-family__kicker')).toHaveTextContent('Awaiting source review')
    unmount()

    const mixed = completeInventory()
    mixed.works.slice(0, 2).forEach((row) => {
      row.verification = { ...row.verification, status: 'verified_exact', label: STATUS_LABELS.verified_exact }
    })
    synchronizeStatusTotals(mixed)
    fetchScriptureVerificationInventory.mockResolvedValueOnce(normalizeScriptureVerificationInventory(mixed))
    const mixedView = renderPage()
    await screen.findByText('71 awaiting exact provenance')
    family = screen.getByRole('heading', { name: 'World Messianic Bible' }).closest('section')
    expect(within(family).getByText('2 of 39 verified')).toBeVisible()
    expect(family.querySelector('.verification-family__kicker')).toHaveTextContent('Source verification in progress')
    await userEvent.setup().type(screen.getByRole('searchbox', { name: 'Search supplied works' }), 'genesis')
    family = screen.getByRole('heading', { name: 'World Messianic Bible' }).closest('section')
    expect(within(family).getByText('2 of 39 verified')).toBeVisible()
    mixedView.unmount()

    const complete = completeInventory()
    complete.works.slice(0, 39).forEach((row) => {
      row.verification = { ...row.verification, status: 'verified_exact', label: STATUS_LABELS.verified_exact }
    })
    synchronizeStatusTotals(complete)
    fetchScriptureVerificationInventory.mockResolvedValueOnce(normalizeScriptureVerificationInventory(complete))
    renderPage()
    await screen.findByText('34 awaiting exact provenance')
    family = screen.getByRole('heading', { name: 'World Messianic Bible' }).closest('section')
    expect(within(family).getByText('39 of 39 verified')).toBeVisible()
    expect(family.querySelector('.verification-family__kicker')).toHaveTextContent('Source verification complete for this family')
  })

  it('surfaces family rows requiring review without describing them as active provenance review', async () => {
    const payload = completeInventory()
    payload.works[0].verification = {
      ...payload.works[0].verification,
      status: 'review_required',
      label: STATUS_LABELS.review_required,
    }
    synchronizeStatusTotals(payload)
    fetchScriptureVerificationInventory.mockResolvedValueOnce(normalizeScriptureVerificationInventory(payload))
    renderPage()

    await screen.findByText('73 awaiting exact provenance')
    const family = screen.getByRole('heading', { name: 'World Messianic Bible' }).closest('section')
    expect(within(family).getByText('1 source review requires attention')).toBeVisible()
    expect(within(family).queryByText('Active provenance review')).not.toBeInTheDocument()
  })

  it('distinguishes loading, network error, retry, and an incomplete inventory', async () => {
    const user = userEvent.setup()
    let rejectRequest
    fetchScriptureVerificationInventory.mockReturnValueOnce(new Promise((_, reject) => { rejectRequest = reject }))
    const { unmount } = renderPage()
    expect(screen.getByRole('status')).toHaveTextContent('Loading scripture source verification…')
    rejectRequest(new Error('offline'))
    expect(await screen.findByRole('alert')).toHaveTextContent('The verification inventory is temporarily unavailable.')
    fetchScriptureVerificationInventory.mockResolvedValueOnce(
      normalizeScriptureVerificationInventory(completeInventory()),
    )
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('83 supplied works')).toBeVisible()
    unmount()

    fetchScriptureVerificationInventory.mockResolvedValueOnce(
      normalizeScriptureVerificationInventory({ ...completeInventory(), total_works: 0, works: [] }),
    )
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Inventory integrity check failed' })).toBeVisible()
    expect(screen.queryByText('83 supplied works')).not.toBeInTheDocument()
  })

  it('loads through the protected lazy route', async () => {
    window.location.hash = '#admin-scripture-verification'
    render(<AuthContext.Provider value={authValue}><App /></AuthContext.Provider>)

    expect(await screen.findByRole('heading', { name: 'Scripture source verification' })).toBeVisible()
    expect(document.title).toBe('Scripture source verification · The Unbound Bible')
  })
})

describe('scripture verification response normalization', () => {
  it('removes unsafe URLs, paths, secret-like text, invalid checksums, and untrusted labels', () => {
    const raw = completeInventory()
    raw.works = [{
      ...raw.works[0],
      work_name: '/Users/admin/private/Genesis.txt',
      source_label: 'access_token=very-secret',
      source_edition: 'file:///private/edition.txt',
      reviewer: 'Bearer top-secret-token',
      provenance_url: 'javascript:alert(1)',
      rights_url: 'https://example.org/rights?token=secret',
      artifact_sha256: 'not-a-checksum',
      comparison_report_sha256: '../../report',
      verification: { status: 'invented', label: 'Trusted anyway', verified_at: '/tmp/date' },
    }]

    const normalized = normalizeScriptureVerificationInventory(raw)
    expect(normalized.works[0]).toMatchObject({
      workName: 'Not disclosed',
      sourceLabel: 'Not disclosed',
      sourceEdition: null,
      reviewer: null,
      provenanceUrl: null,
      rightsUrl: null,
      artifactSha256: null,
      comparisonReportSha256: null,
      status: 'unknown',
      statusLabel: 'Source status unavailable',
    })
    expect(JSON.stringify(normalized)).not.toMatch(/users|token|secret|javascript|private|\.\.\//i)
  })

  it('bounds malformed and partial server data without throwing', () => {
    expect(normalizeScriptureVerificationInventory(null)).toMatchObject({
      editionCode: null,
      totalWorks: null,
      works: [],
      integrity: { valid: false },
    })
    const normalized = normalizeScriptureVerificationInventory({
      edition_code: 'EOTC-COMPOSITE-EN',
      total_works: 83,
      works: [null, { work_id: 'genesis', verification: null, comparison: null }],
    })
    expect(normalized.works).toHaveLength(1)
    expect(normalized.works[0].comparison).toEqual({ exact: 0, formatting: 0, missing: 0, extra: 0, wording: 0 })
    expect(normalized.integrity.valid).toBe(false)
  })

  it.each([
    ['duplicate work ID', (payload) => { payload.works[1].work_id = payload.works[0].work_id }],
    ['missing work', (payload) => { payload.works.pop(); payload.total_works = 82 }],
    ['unknown work', (payload) => { payload.works[0].work_id = 'invented-work' }],
    ['wrong source family', (payload) => { payload.works[0].source_key = 'murdock-peshitta-1852' }],
    ['wrong declared total', (payload) => { payload.total_works = 82 }],
    ['wrong family totals', (payload) => { payload.family_totals[0].count = 7 }],
    ['wrong status totals', (payload) => { payload.status_totals[0].count = 72 }],
    ['malformed zero status total', (payload) => { payload.status_totals[2].count = '0' }],
  ])('fails closed for %s', (_name, mutate) => {
    const payload = completeInventory()
    mutate(payload)
    const normalized = normalizeScriptureVerificationInventory(payload)
    expect(normalized.integrity.valid).toBe(false)
    expect(normalized.integrity.issues.length).toBeGreaterThan(0)
  })

  it('retains consistent server totals for the approved 83-work contract', () => {
    const normalized = normalizeScriptureVerificationInventory(completeInventory())
    expect(normalized).toMatchObject({
      totalWorks: 83,
      integrity: { valid: true, issues: [] },
    })
    expect(normalized.familyTotals).toHaveLength(6)
    expect(normalized.statusTotals).toHaveLength(5)
  })
})

describe('inventory integrity presentation', () => {
  it('does not present authoritative totals when the server inventory is inconsistent', async () => {
    const payload = completeInventory()
    payload.works[1].work_id = payload.works[0].work_id
    fetchScriptureVerificationInventory.mockResolvedValueOnce(
      normalizeScriptureVerificationInventory(payload),
    )
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Inventory integrity check failed' })).toBeVisible()
    expect(screen.getByText(/could not be matched to the approved 83-work source contract/i)).toBeVisible()
    expect(screen.queryByText('83 supplied works')).not.toBeInTheDocument()
    expect(screen.queryByText('73 awaiting exact provenance')).not.toBeInTheDocument()
  })
})

describe('scripture verification readability contract', () => {
  function channel(value) {
    const normalized = value / 255
    return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4
  }

  function luminance(hex) {
    const channels = hex.match(/[a-f\d]{2}/gi).map((part) => channel(Number.parseInt(part, 16)))
    return (0.2126 * channels[0]) + (0.7152 * channels[1]) + (0.0722 * channels[2])
  }

  function contrast(foreground, background) {
    const values = [luminance(foreground), luminance(background)].sort((left, right) => right - left)
    return (values[0] + 0.05) / (values[1] + 0.05)
  }

  it('uses a page-specific muted token with strong contrast on every dark page surface', () => {
    const stylesheet = readFileSync('src/admin/ScriptureVerificationPage.css', 'utf8')
    const muted = stylesheet.match(/--verification-muted:\s*(#[a-f\d]{6})/i)?.[1]
    expect(muted).toBeTruthy()
    ;['#0c1118', '#0d131b', '#10151c', '#11171f'].forEach((background) => {
      expect(contrast(muted, background)).toBeGreaterThanOrEqual(7)
    })
    expect(stylesheet).not.toMatch(/color:\s*var\(--text-muted\)/)
  })

  it('keeps essential verification metadata at 0.8rem or larger', () => {
    const stylesheet = readFileSync('src/admin/ScriptureVerificationPage.css', 'utf8')
    const selectors = [
      '.verification-family thead th',
      '.verification-work__id',
      '.verification-evidence__facts dt',
      '.verification-evidence__facts dd',
      '.verification-comparison span',
    ]
    selectors.forEach((selector) => {
      const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      expect(stylesheet).toMatch(new RegExp(`${escaped}\\s*\\{[^}]*font(?:-size|):\\s*0\\.[89]rem`, 's'))
    })
  })
})
