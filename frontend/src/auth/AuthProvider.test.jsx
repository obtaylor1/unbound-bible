import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from './AuthProvider'
import { useAuth } from './authContext'

vi.mock('../api/client', () => ({
  api: { get: vi.fn().mockResolvedValue({ id: '1', username: 'reader' }), post: vi.fn() },
  credentials: { hasSession: true, set: vi.fn(), clear: vi.fn() }
}))

function Status() {
  const { status, user } = useAuth()
  return <span>{status}:{user?.username}</span>
}

describe('AuthProvider', () => {
  it('restores the current user on startup', async () => {
    render(<AuthProvider><Status /></AuthProvider>)
    await waitFor(() => expect(screen.getByText('authenticated:reader')).toBeInTheDocument())
  })
})
