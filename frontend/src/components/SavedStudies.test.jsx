import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { AuthContext } from '../auth/authContext'
import SavedStudies from './SavedStudies'

vi.mock('../api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

function renderStudies(status = 'anonymous') {
  return render(
    <AuthContext.Provider value={{ user: null, status }}>
      <SavedStudies reference={{ book: 'Genesis', chapter: 1, verse: 2 }} />
    </AuthContext.Provider>,
  )
}

afterEach(() => {
  window.localStorage.clear()
  vi.clearAllMocks()
})

describe('SavedStudies note creation', () => {
  it('creates a local note for the selected reference and keeps it visible', async () => {
    const user = userEvent.setup()
    renderStudies()

    expect(screen.getByRole('heading', { name: 'Add a note for Genesis 1:2' })).toBeVisible()
    await user.type(screen.getByLabelText('Note for Genesis 1:2'), 'Remember the movement from chaos to order.')
    await user.click(screen.getByRole('button', { name: 'Save note' }))

    expect(screen.getByRole('status')).toHaveTextContent('Note saved for Genesis 1:2')
    expect(screen.getByText('Remember the movement from chaos to order.')).toBeVisible()
    expect(JSON.parse(window.localStorage.getItem('unbound_notes'))[0]).toMatchObject({
      passage_reference: 'Genesis 1:2',
      content: 'Remember the movement from chaos to order.',
    })
  })

  it('creates an authenticated note through the private notes API', async () => {
    api.get.mockImplementation(async (path) => path === '/notes' ? [] : [])
    api.post.mockResolvedValue({
      id: 'note-1',
      passage_reference: 'Genesis 1:2',
      content: 'A private note.',
    })
    const user = userEvent.setup()
    renderStudies('authenticated')

    await user.type(await screen.findByLabelText('Note for Genesis 1:2'), 'A private note.')
    await user.click(screen.getByRole('button', { name: 'Save note' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/notes', {
      passage_reference: 'Genesis 1:2',
      content: 'A private note.',
    }))
    expect(screen.getByText('A private note.')).toBeVisible()
  })
})
