import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Navigation from './Navigation'

describe('Navigation', () => {
  it('exposes accessible disclosure and action names', () => {
    render(<Navigation currentPage="home" onPageChange={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'AI Study' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
    expect(screen.getByLabelText('Open navigation')).toBeInTheDocument()
  })

  it('closes an open dropdown with Escape', () => {
    render(<Navigation currentPage="home" onPageChange={vi.fn()} />)
    const trigger = screen.getByRole('button', { name: 'AI Study' })

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  it.each([
    ['Ctrl+K', { ctrlKey: true }],
    ['Cmd+K', { metaKey: true }],
  ])('opens global search with %s when no modal dialog is active', (_, modifier) => {
    render(<Navigation currentPage="home" onPageChange={vi.fn()} />)

    fireEvent.keyDown(document, { key: 'k', ...modifier })

    expect(screen.getByRole('dialog', { name: 'Search' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Search the library' })).toHaveFocus()
  })
})
