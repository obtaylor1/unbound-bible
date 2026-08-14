import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ShareStudyModal from './ShareStudyModal'
import { createShare } from '../services/sharingApi'

vi.mock('../services/sharingApi', () => ({ createShare: vi.fn(), updateShare: vi.fn() }))

describe('ShareStudyModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

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

  it('does not expose or copy a previous study link after closing and reopening', async () => {
    createShare
      .mockResolvedValueOnce({ share_id: 'first-link', visibility: 'unlisted' })
      .mockResolvedValueOnce({ share_id: 'second-link', visibility: 'unlisted' })
    const writeText = vi.fn().mockResolvedValue()
    Object.assign(navigator, { clipboard: { writeText } })
    const onClose = vi.fn()
    const firstStudy = { studyId: 'study-1', type: 'Q&A', title: 'First study', verses: [] }
    const secondStudy = { studyId: 'study-2', type: 'Q&A', title: 'Second study', verses: [] }
    const { rerender } = render(<ShareStudyModal isOpen onClose={onClose} shareData={firstStudy} />)

    fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
    expect((await screen.findByRole('textbox', { name: 'Share link' })).value).toContain('/share/first-link')

    rerender(<ShareStudyModal isOpen={false} onClose={onClose} shareData={firstStudy} />)
    rerender(<ShareStudyModal isOpen onClose={onClose} shareData={secondStudy} />)

    expect(screen.queryByRole('textbox', { name: 'Share link' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Copy link' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Email' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create link' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
    expect((await screen.findByRole('textbox', { name: 'Share link' })).value).toContain('/share/second-link')
    fireEvent.click(screen.getByRole('button', { name: 'Copy link' }))

    expect(createShare).toHaveBeenLastCalledWith(expect.objectContaining({ study_id: 'study-2' }))
    expect(writeText).toHaveBeenCalledOnce()
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('/share/second-link'))
    expect(writeText).not.toHaveBeenCalledWith(expect.stringContaining('/share/first-link'))
  })

  it('traps forward and reverse tab navigation and restores the exact prior focus', () => {
    const priorFocus = document.createElement('button')
    priorFocus.textContent = 'Open share dialog'
    document.body.appendChild(priorFocus)
    priorFocus.focus()
    const onClose = vi.fn()
    const shareData = { studyId: 'study-1', type: 'Q&A', title: 'Study', verses: [] }
    const { rerender } = render(<ShareStudyModal isOpen onClose={onClose} shareData={shareData} />)
    const closeButton = screen.getByRole('button', { name: 'Close sharing dialog' })
    const createButton = screen.getByRole('button', { name: 'Create link' })

    expect(closeButton).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(createButton).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Tab' })
    expect(closeButton).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
    rerender(<ShareStudyModal isOpen={false} onClose={onClose} shareData={shareData} />)
    expect(priorFocus).toHaveFocus()

    priorFocus.remove()
  })
})
