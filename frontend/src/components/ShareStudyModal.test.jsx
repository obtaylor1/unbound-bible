import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ShareStudyModal from './ShareStudyModal'
import { createShare } from '../services/sharingApi'

vi.mock('../services/sharingApi', () => ({ createShare: vi.fn(), updateShare: vi.fn() }))

describe('ShareStudyModal', () => {
  it('renders a named dialog and closes with Escape', () => {
    const onClose = vi.fn()
    render(<ShareStudyModal isOpen onClose={onClose} shareData={{ type: 'Q&A', title: 'Study', verses: [] }} />)

    expect(screen.getByRole('dialog', { name: 'Share study session' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close sharing dialog' })).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('persists a share before copying or exposing external intents', async () => {
    createShare.mockResolvedValue({ share_id: 'safe-id', visibility: 'unlisted' })
    const writeText = vi.fn().mockResolvedValue()
    Object.assign(navigator, { clipboard: { writeText } })
    render(<ShareStudyModal isOpen onClose={vi.fn()} shareData={{ studyId: 'study-1', type: 'Q&A', title: 'Grace & Hope', verses: [] }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
    await waitFor(() => expect(createShare).toHaveBeenCalledWith(expect.objectContaining({ study_id: 'study-1', visibility: 'unlisted' })))
    fireEvent.click(screen.getByRole('button', { name: 'Copy link' }))
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('/share/safe-id'))
    expect(screen.getByRole('link', { name: 'Email' })).toHaveAttribute('href', expect.stringContaining('Grace%20%26%20Hope'))
    expect(screen.getByRole('link', { name: 'WhatsApp' })).toHaveAttribute('href', expect.stringContaining('wa.me'))
  })
})
