import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import NotificationInbox from './NotificationInbox'
import { api } from '../api/client'

vi.mock('../api/client', () => ({ api: { get: vi.fn(), patch: vi.fn(), post: vi.fn() } }))

describe('NotificationInbox', () => {
  it('shows unread count and marks a notification read', async () => {
    api.get.mockImplementation((path) => Promise.resolve(path.endsWith('unread-count') ? { count: 1 } : [{ id: '1', message: 'A reply arrived', read_at: null, created_at: new Date().toISOString() }]))
    api.patch.mockResolvedValue({})
    render(<NotificationInbox />)
    expect(await screen.findByText('1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Notifications/ }))
    expect(await screen.findByText('A reply arrived')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'A reply arrived' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/notifications/1/read', {}))
  })

  it('rolls back an optimistic read when the API fails', async () => {
    api.get.mockImplementation((path) => Promise.resolve(path.endsWith('unread-count') ? { count: 1 } : [{ id: '1', message: 'Still unread', read_at: null, created_at: new Date().toISOString() }]))
    api.patch.mockRejectedValue(new Error('offline'))
    render(<NotificationInbox />); fireEvent.click(await screen.findByRole('button', { name: /Notifications/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Still unread' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Could not update'))
    expect(screen.getByText('1')).toBeInTheDocument()
  })
})
