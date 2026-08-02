import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './SavedStudies.css'
import { api } from '../api/client'
import { useAuth } from '../auth/authContext'
import { normalizeStudyReference } from '../reader/studyToolRegistry'

const readLocal = (key) => {
  try {
    const value = JSON.parse(localStorage.getItem(key) || '[]')
    return Array.isArray(value)
      ? value.filter((item) => item && typeof item === 'object' && !Array.isArray(item))
      : []
  }
  catch { return [] }
}

export default function SavedStudies({ reference }) {
  const { status } = useAuth()
  const [activeView, setActiveView] = useState('notes')
  const [notes, setNotes] = useState([])
  const [studies, setStudies] = useState([])
  const [query, setQuery] = useState('')
  const [message, setMessage] = useState('')
  const [draft, setDraft] = useState('')
  const loadGeneration = useRef(0)
  const normalizedReference = normalizeStudyReference(reference)
  const canCreateReferenceNote = Boolean(
    normalizedReference.value.book && normalizedReference.value.chapter,
  )

  const createNote = async (event) => {
    event.preventDefault()
    const content = draft.trim()
    if (
      !content
      || !canCreateReferenceNote
      || !['anonymous', 'authenticated'].includes(status)
    ) return
    const payload = {
      passage_reference: normalizedReference.label,
      content,
    }
    try {
      let created
      if (status === 'authenticated') {
        created = await api.post('/notes', payload)
      } else {
        created = {
          ...payload,
          id: `local-${Date.now()}-${Math.random().toString(16).slice(2)}`,
          updated_at: new Date().toISOString(),
        }
        const nextNotes = [created, ...readLocal('unbound_notes')]
        localStorage.setItem('unbound_notes', JSON.stringify(nextNotes))
      }
      setNotes((current) => [created, ...current.filter((note) => note.id !== created.id)])
      setDraft('')
      setActiveView('notes')
      setMessage(`Note saved for ${normalizedReference.label}.`)
    } catch (error) {
      setMessage(`Your note could not be saved: ${error.message}`)
    }
  }

  const load = useCallback(async () => {
    const generation = ++loadGeneration.current
    try {
      if (status === 'authenticated') {
        const [remoteNotes, remoteStudies] = await Promise.all([api.get('/notes'), api.get('/studies')])
        if (generation !== loadGeneration.current) return
        setNotes(Array.isArray(remoteNotes) ? remoteNotes : [])
        setStudies(Array.isArray(remoteStudies) ? remoteStudies : [])
      } else if (status === 'anonymous') {
        setNotes(readLocal('unbound_notes')); setStudies(readLocal('unbound_saved_studies'))
      } else {
        setNotes([])
        setStudies([])
      }
    } catch (error) {
      if (generation === loadGeneration.current) setMessage(error.message)
    }
  }, [status])
  useEffect(() => {
    load()
    return () => {
      loadGeneration.current += 1
    }
  }, [load])

  const guestNotes = readLocal('unbound_notes')
  const guestStudies = readLocal('unbound_saved_studies')
  const guestCount = guestNotes.length + guestStudies.length

  const importGuestData = async () => {
    if (!window.confirm(`Import ${guestNotes.length} notes and ${guestStudies.length} studies into your account? Local copies are removed only after every item is saved.`)) return
    setMessage('Importing your local library…')
    try {
      for (const note of guestNotes) {
        const reference = note.passage_reference || (note.book ? `${note.book} ${note.chapter || ''}${note.verse ? `:${note.verse}` : ''}`.trim() : null)
        await api.post('/notes', { passage_reference: reference, content: note.content || note.text })
      }
      for (const study of guestStudies) await api.post('/studies', { title: study.title || 'Imported study' })
      localStorage.removeItem('unbound_notes'); localStorage.removeItem('unbound_saved_studies')
      setMessage('Your local library was imported successfully.'); await load()
    } catch (error) { setMessage(`Import stopped: ${error.message}. Your local copies are still safe.`) }
  }

  const remove = async (kind, id) => {
    if (!window.confirm(`Delete this ${kind === 'notes' ? 'note' : 'study'}?`)) return
    if (status === 'authenticated') await api.delete(`/${kind}/${id}`)
    else {
      const key = kind === 'notes' ? 'unbound_notes' : 'unbound_saved_studies'
      localStorage.setItem(key, JSON.stringify(readLocal(key).filter((item) => item.id !== id)))
    }
    await load()
  }

  const items = activeView === 'notes' ? notes : studies
  const filtered = useMemo(() => items.filter((item) => `${item.title || ''} ${item.passage_reference || item.book || ''} ${item.content || item.text || ''}`.toLowerCase().includes(query.toLowerCase())), [items, query])

  return <div className="saved-studies-page glass-panel">
    <div className="saved-header"><span className="saved-badge">PERSONAL LIBRARY</span><h2>Notes & saved studies</h2><p className="subtitle">Private research and conversations, ready when you return.</p></div>
    {status === 'anonymous' && <div className="empty-workspace-card"><strong>Your work is saved only on this device.</strong><p>Sign in to keep it private and available across devices.</p></div>}
    {status === 'authenticated' && guestCount > 0 && <div className="empty-workspace-card"><strong>Local work found</strong><p>{guestNotes.length} notes and {guestStudies.length} studies are ready to import.</p><button className="export-btn" onClick={importGuestData}>Review and import</button></div>}
    {message && <p role="status">{message}</p>}
    {canCreateReferenceNote && ['anonymous', 'authenticated'].includes(status) && (
      <form className="saved-note-composer" onSubmit={createNote}>
        <h3>Add a note for {normalizedReference.label}</h3>
        <label htmlFor="saved-note-content">Note for {normalizedReference.label}</label>
        <textarea
          id="saved-note-content"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows="4"
          maxLength="5000"
          required
        />
        <button className="export-btn" type="submit" disabled={!draft.trim()}>Save note</button>
      </form>
    )}
    <div className="controls-row">
      <div className="view-toggle"><button className={`toggle-btn ${activeView === 'notes' ? 'active' : ''}`} onClick={() => setActiveView('notes')}>Notes ({notes.length})</button><button className={`toggle-btn ${activeView === 'studies' ? 'active' : ''}`} onClick={() => setActiveView('studies')}>Studies ({studies.length})</button></div>
      <input className="search-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your library" aria-label="Search your library" />
    </div>
    <div className="notes-vertical-flex">{filtered.length === 0 ? <div className="empty-workspace-card"><p>No saved {activeView} yet.</p><span className="tip-txt">Your saved work will appear here.</span></div> : filtered.map((item) => <article key={item.id} className="note-item-card glass-panel"><div className="note-card-header"><span className="note-verse-tag">{item.passage_reference || item.title || 'General note'}</span><span className="note-date-txt">{item.updated_at ? new Date(item.updated_at).toLocaleDateString() : ''}</span></div>{activeView === 'notes' && <p className="note-text-body">{item.content || item.text}</p>}<div className="note-card-footer"><button className="delete-note-btn" onClick={() => remove(activeView, item.id)}>Delete</button></div></article>)}</div>
  </div>
}
