import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import SearchDialog from './SearchDialog'
import { api } from '../api/client'

vi.mock('../api/client', () => ({ api: { get: vi.fn() } }))

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
})
