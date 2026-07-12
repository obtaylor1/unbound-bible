import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ShareStudyModal from './ShareStudyModal'

describe('ShareStudyModal', () => {
  it('renders a named dialog and closes with Escape', () => {
    const onClose = vi.fn()
    render(<ShareStudyModal isOpen onClose={onClose} shareData={{ type: 'Q&A', title: 'Study', verses: [] }} />)

    expect(screen.getByRole('dialog', { name: 'Share study session' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close sharing dialog' })).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })
})
