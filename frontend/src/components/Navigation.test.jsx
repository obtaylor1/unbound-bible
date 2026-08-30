import { fireEvent, render, screen } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/authContext'
import Navigation from './Navigation'

describe('Navigation', () => {
  it('exposes accessible disclosure and action names', () => {
    render(<Navigation currentPage="home" onPageChange={vi.fn()} />)

    const aiStudy = screen.getByRole('button', { name: 'AI Study' })
    expect(aiStudy).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(aiStudy)
    expect(screen.getByRole('button', { name: 'Scripture Research AI' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ask the Bible' })).not.toBeInTheDocument()
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

  it('exposes source verification only to an authenticated administrator', () => {
    const onPageChange = vi.fn()
    const { rerender } = render(
      <AuthContext.Provider value={{ user: { username: 'reader', role: 'member' } }}>
        <Navigation currentPage="home" onPageChange={onPageChange} />
      </AuthContext.Provider>,
    )
    expect(screen.queryByRole('button', { name: 'Source verification' })).not.toBeInTheDocument()

    rerender(
      <AuthContext.Provider value={{ user: { username: 'admin', role: 'admin' } }}>
        <Navigation currentPage="home" onPageChange={onPageChange} />
      </AuthContext.Provider>,
    )
    const adminTarget = screen.getByRole('button', { name: 'Source verification' })
    expect(adminTarget).toHaveClass('nav-admin-link')
    const stylesheet = readFileSync('src/components/Navigation.css', 'utf8')
    expect(stylesheet).toMatch(/\.nav-admin-link\s*\{[^}]*min-width:\s*44px;[^}]*min-height:\s*44px;/s)
    expect(stylesheet).toMatch(/\.nav-admin-link\s*\{\s*width:\s*44px;/s)
    fireEvent.click(adminTarget)
    expect(onPageChange).toHaveBeenCalledWith('scripture-verification-admin')
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
