import { act, render, screen, waitFor } from '@testing-library/react'
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

function deferred() {
  let resolve
  let reject
  const promise = new Promise((next, fail) => {
    resolve = next
    reject = fail
  })
  return { promise, reject, resolve }
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

  it('waits for authentication restoration before offering note creation', () => {
    renderStudies('loading')

    expect(screen.queryByLabelText('Note for Genesis 1:2')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save note' })).not.toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
    expect(window.localStorage.getItem('unbound_notes')).toBeNull()
  })

  it('ignores a stale private response after the user becomes anonymous', async () => {
    const remoteNotes = deferred()
    const remoteStudies = deferred()
    api.get.mockImplementation((path) => (
      path === '/notes' ? remoteNotes.promise : remoteStudies.promise
    ))
    window.localStorage.setItem('unbound_notes', JSON.stringify([{
      id: 'local-note',
      passage_reference: 'Genesis 1:2',
      content: 'Local note.',
    }]))

    const { rerender } = renderStudies('authenticated')
    rerender(
      <AuthContext.Provider value={{ user: null, status: 'anonymous' }}>
        <SavedStudies reference={{ book: 'Genesis', chapter: 1, verse: 2 }} />
      </AuthContext.Provider>,
    )
    expect(await screen.findByText('Local note.')).toBeVisible()

    await act(async () => {
      remoteNotes.resolve([{
        id: 'private-note',
        passage_reference: 'Genesis 1:2',
        content: 'Private account note.',
      }])
      remoteStudies.resolve([])
      await Promise.all([remoteNotes.promise, remoteStudies.promise])
    })

    await waitFor(() => {
      expect(screen.queryByText('Private account note.')).not.toBeInTheDocument()
      expect(screen.getByText('Local note.')).toBeVisible()
    })
  })

  it('does not let an older account load erase a newly saved note', async () => {
    const remoteNotes = deferred()
    const remoteStudies = deferred()
    api.get.mockImplementation((path) => (
      path === '/notes' ? remoteNotes.promise : remoteStudies.promise
    ))
    api.post.mockResolvedValue({
      id: 'new-note',
      passage_reference: 'Genesis 1:2',
      content: 'Newly saved note.',
    })
    const user = userEvent.setup()
    renderStudies('authenticated')

    await user.type(screen.getByLabelText('Note for Genesis 1:2'), 'Newly saved note.')
    await user.click(screen.getByRole('button', { name: 'Save note' }))
    expect(await screen.findByText('Newly saved note.')).toBeVisible()

    await act(async () => {
      remoteNotes.resolve([])
      remoteStudies.resolve([{ id: 'study-1', title: 'Loaded study' }])
      await Promise.all([remoteNotes.promise, remoteStudies.promise])
    })

    expect(screen.getByText('Newly saved note.')).toBeVisible()
  })

  it('does not insert an authenticated save that finishes after logout', async () => {
    api.get.mockResolvedValue([])
    const savedNote = deferred()
    api.post.mockReturnValue(savedNote.promise)
    const user = userEvent.setup()
    const { rerender } = renderStudies('authenticated')

    await user.type(screen.getByLabelText('Note for Genesis 1:2'), 'Private pending note.')
    await user.click(screen.getByRole('button', { name: 'Save note' }))
    rerender(
      <AuthContext.Provider value={{ user: null, status: 'anonymous' }}>
        <SavedStudies reference={{ book: 'Genesis', chapter: 1, verse: 2 }} />
      </AuthContext.Provider>,
    )

    await act(async () => {
      savedNote.resolve({
        id: 'private-pending',
        passage_reference: 'Genesis 1:2',
        content: 'Private pending note.',
      })
      await savedNote.promise
    })

    expect(screen.queryByText('Private pending note.')).not.toBeInTheDocument()
    expect(screen.getByText('No saved notes yet.')).toBeVisible()
  })

  it('does not let an old-session save rejection invalidate a new account load', async () => {
    const oldSave = deferred()
    const newNotes = deferred()
    const newStudies = deferred()
    let accountLoad = 0
    api.get.mockImplementation((path) => {
      accountLoad += 1
      if (accountLoad <= 2) return Promise.resolve([])
      return path === '/notes' ? newNotes.promise : newStudies.promise
    })
    api.post.mockReturnValue(oldSave.promise)
    const user = userEvent.setup()
    const { rerender } = renderStudies('authenticated')

    await user.type(screen.getByLabelText('Note for Genesis 1:2'), 'Old session draft.')
    await user.click(screen.getByRole('button', { name: 'Save note' }))
    rerender(
      <AuthContext.Provider value={{ user: null, status: 'anonymous' }}>
        <SavedStudies reference={{ book: 'Genesis', chapter: 1, verse: 2 }} />
      </AuthContext.Provider>,
    )
    rerender(
      <AuthContext.Provider value={{ user: { id: 'new-user' }, status: 'authenticated' }}>
        <SavedStudies reference={{ book: 'Genesis', chapter: 1, verse: 2 }} />
      </AuthContext.Provider>,
    )

    await act(async () => {
      oldSave.reject(new Error('Old session save failed'))
      await oldSave.promise.catch(() => {})
      newNotes.resolve([{
        id: 'new-account-note',
        passage_reference: 'Genesis 1:2',
        content: 'New account note.',
      }])
      newStudies.resolve([])
      await Promise.all([newNotes.promise, newStudies.promise])
    })

    expect(screen.getByText('New account note.')).toBeVisible()
    expect(screen.queryByText('Old session draft.')).not.toBeInTheDocument()
  })

  it('treats malformed local storage as an empty collection', () => {
    window.localStorage.setItem('unbound_notes', JSON.stringify({ unexpected: true }))
    window.localStorage.setItem('unbound_saved_studies', JSON.stringify(['bad', null]))

    expect(() => renderStudies()).not.toThrow()
    expect(screen.getByText('No saved notes yet.')).toBeVisible()
  })
})
