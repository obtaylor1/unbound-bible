import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SearchDialog from './SearchDialog'
import { api } from '../api/client'

vi.mock('../api/client', () => ({ api: { get: vi.fn() } }))

afterEach(() => vi.clearAllMocks())

describe('SearchDialog', () => {
  it('searches, supports arrow navigation, Enter, and Escape', async () => {
    api.get.mockResolvedValue({ results: [{ group: 'scripture', id: '1', title: 'Romans 8:1', excerpt: 'No condemnation', url: '/#scriptures' }] })
    const navigate = vi.fn(); const close = vi.fn()
    render(<SearchDialog open onClose={close} onNavigate={navigate} />)
    const input = screen.getByRole('combobox', { name: 'Search the library' })
    fireEvent.change(input, { target: { value: 'condemnation' } })
    await waitFor(() => expect(screen.getByRole('option', { name: /Romans 8:1/ })).toBeInTheDocument())
    fireEvent.keyDown(input, { key: 'ArrowDown' }); fireEvent.keyDown(input, { key: 'Enter' })
    expect(navigate).toHaveBeenCalledWith('/#scriptures')
    fireEvent.keyDown(document, { key: 'Escape' }); expect(close).toHaveBeenCalled()
  })

  it('announces empty results', async () => {
    api.get.mockResolvedValue({ results: [] })
    render(<SearchDialog open onClose={vi.fn()} onNavigate={vi.fn()} />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'nothing' } })
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('No results'))
  })

  it('traps focus, closes with Escape, restores its opener, and locks scrolling', async () => {
    const user = userEvent.setup()
    const close = vi.fn()
    function Harness() {
      const [open, setOpen] = useState(false)
      return <>
        <button onClick={() => setOpen(true)}>Open search</button>
        <SearchDialog open={open} onClose={() => {
          close()
          setOpen(false)
        }} onNavigate={vi.fn()} />
      </>
    }
    render(<Harness />)
    const opener = screen.getByRole('button', { name: 'Open search' })
    await user.click(opener)
    const input = screen.getByRole('combobox', { name: 'Search the library' })
    expect(input).toHaveFocus()
    expect(document.body).toHaveStyle({ overflow: 'hidden' })

    await user.tab({ shift: true })
    expect(input).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(close).toHaveBeenCalledOnce()
    expect(opener).toHaveFocus()
    expect(document.body.style.overflow).toBe('')
  })

  it('owns the active option id and clears stale descendants with changing results', async () => {
    api.get
      .mockResolvedValueOnce({ results: [
        { group: 'scripture', id: '1', title: 'Romans 8:1', excerpt: 'First', url: '/#scriptures' },
        { group: 'scripture', id: '2', title: 'Romans 8:2', excerpt: 'Second', url: '/#scriptures' },
      ] })
      .mockResolvedValueOnce({ results: [] })
    render(<SearchDialog open onClose={vi.fn()} onNavigate={vi.fn()} />)
    const input = screen.getByRole('combobox', { name: 'Search the library' })
    fireEvent.change(input, { target: { value: 'Romans' } })
    await screen.findByRole('option', { name: /Romans 8:1/ })
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    const activeId = input.getAttribute('aria-activedescendant')
    expect(activeId).toBeTruthy()
    expect(document.getElementById(activeId)).toHaveAttribute('aria-selected', 'true')

    fireEvent.change(input, { target: { value: 'nothing' } })
    await waitFor(() => expect(screen.queryByRole('option')).not.toBeInTheDocument())
    expect(input).not.toHaveAttribute('aria-activedescendant')
  })
})
