import { useCallback, useEffect, useMemo, useState } from 'react'
import './SavedStudies.css'
import { api } from '../api/client'
import { useAuth } from '../auth/authContext'

const readLocal = (key) => {
  try { return JSON.parse(localStorage.getItem(key) || '[]') }
  catch { return [] }
}

export default function SavedStudies() {
  const { status } = useAuth()
  const [activeView, setActiveView] = useState('notes')
  const [notes, setNotes] = useState([])
  const [studies, setStudies] = useState([])
  const [query, setQuery] = useState('')
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    if (status === 'authenticated') {
      const [remoteNotes, remoteStudies] = await Promise.all([api.get('/notes'), api.get('/studies')])
      setNotes(remoteNotes); setStudies(remoteStudies)
    } else if (status === 'anonymous') {
      setNotes(readLocal('unbound_notes')); setStudies(readLocal('unbound_saved_studies'))
    }
  }, [status])
  useEffect(() => { load().catch((error) => setMessage(error.message)) }, [load])

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
    <div className="controls-row">
      <div className="view-toggle"><button className={`toggle-btn ${activeView === 'notes' ? 'active' : ''}`} onClick={() => setActiveView('notes')}>Notes ({notes.length})</button><button className={`toggle-btn ${activeView === 'studies' ? 'active' : ''}`} onClick={() => setActiveView('studies')}>Studies ({studies.length})</button></div>
      <input className="search-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your library" aria-label="Search your library" />
    </div>
    <div className="notes-vertical-flex">{filtered.length === 0 ? <div className="empty-workspace-card"><p>No saved {activeView} yet.</p><span className="tip-txt">Your saved work will appear here.</span></div> : filtered.map((item) => <article key={item.id} className="note-item-card glass-panel"><div className="note-card-header"><span className="note-verse-tag">{item.passage_reference || item.title || 'General note'}</span><span className="note-date-txt">{item.updated_at ? new Date(item.updated_at).toLocaleDateString() : ''}</span></div>{activeView === 'notes' && <p className="note-text-body">{item.content || item.text}</p>}<div className="note-card-footer"><button className="delete-note-btn" onClick={() => remove(activeView, item.id)}>Delete</button></div></article>)}</div>
  </div>
}
