import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import StudyAssistantSidebar from './StudyAssistantSidebar'
import { askStudyQuestion } from '../services/studyApi'

vi.mock('../auth/authContext', () => ({
  useAuth: () => ({ status: 'anonymous', user: null }),
}))

vi.mock('../services/studyApi', () => ({
  askStudyQuestion: vi.fn(),
}))

vi.mock('./ShareStudyModal', () => ({
  default: () => null,
}))

function installFetch() {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      cross_references: [],
      translation_biases: [],
      original_words: [],
    }),
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  installFetch()
  HTMLElement.prototype.scrollIntoView = vi.fn()
})

describe('StudyAssistantSidebar', () => {
  it('shows the verified commentary location without invented sources or generated commentary', async () => {
    render(
      <StudyAssistantSidebar
        book="Genesis"
        chapter={1}
        verse={1}
        initialTab="insights"
        initialInsightSubTab="commentary"
        onClose={vi.fn()}
      />,
    )

    const message = await screen.findByText(
      'Verified commentary is available in the Scripture Reader Study Tools.',
    )
    expect(message.closest('.empty-state')).not.toBeNull()
    expect(screen.queryByText('Decolonized Commentary (Axum Studies)')).not.toBeInTheDocument()
    expect(screen.queryByText('Library Commentary (Standard Exegesis)')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Generate Full Commentary Review/i })).not.toBeInTheDocument()
    expect(askStudyQuestion).not.toHaveBeenCalled()
    expect(fetch).toHaveBeenCalledOnce()
    expect(fetch).toHaveBeenCalledWith('/api/v1/texts/Genesis/1/1/details')
  })

  it('keeps the other Passage Insights tabs working', async () => {
    const user = userEvent.setup()
    render(
      <StudyAssistantSidebar
        initialTab="insights"
        initialInsightSubTab="commentary"
        onClose={vi.fn()}
      />,
    )

    await screen.findByText('Verified commentary is available in the Scripture Reader Study Tools.')

    await user.click(screen.getByRole('button', { name: 'Cross-Refs' }))
    expect(screen.getByRole('heading', { name: 'Cross-References & Parallel Texts' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Original Words' }))
    expect(screen.getByRole('heading', { name: "Original Language Words & Strong's Mappings" })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Canon Notes' }))
    expect(screen.getByRole('heading', { name: 'Multi-Canonical & Historical Context' })).toBeInTheDocument()
    await waitFor(() => expect(fetch).toHaveBeenCalledOnce())
    expect(askStudyQuestion).not.toHaveBeenCalled()
  })
})
