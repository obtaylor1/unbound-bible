import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import PublicStudyPage from './PublicStudyPage'
import { getShare } from '../services/sharingApi'

vi.mock('../services/sharingApi', () => ({ getShare: vi.fn() }))

describe('PublicStudyPage', () => {
  it('renders an immutable shared study without owner private data', async () => {
    getShare.mockResolvedValue({ title: 'Grace', messages: [{ role: 'assistant', content: 'Gift, not wages.' }], sources: [{ title: 'Romans', citation: 'Romans 6:23' }] })
    render(<PublicStudyPage shareId="abc" />)
    expect(await screen.findByRole('heading', { name: 'Grace' })).toBeInTheDocument()
    expect(screen.getByText('Romans 6:23')).toBeInTheDocument()
  })

  it('announces revoked shares as unavailable', async () => {
    getShare.mockRejectedValue(Object.assign(new Error('gone'), { status: 410 }))
    render(<PublicStudyPage shareId="revoked" />)
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('no longer available'))
  })
})
