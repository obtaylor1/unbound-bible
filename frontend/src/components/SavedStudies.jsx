import { useState, useEffect } from 'react'
import './SavedStudies.css'

function SavedStudies() {
  const [notes, setNotes] = useState([])
  const [savedSessions, setSavedSessions] = useState([])
  const [activeView, setActiveView] = useState('notes') // 'notes' or 'sessions'
  
  // Search & Filter States
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTag, setSelectedTag] = useState('')
  const [editingNoteId, setEditingNoteId] = useState(null)
  const [editingText, setEditingText] = useState('')

  // Load saved content
  useEffect(() => {
    const fetchNotes = async () => {
      try {
        const response = await fetch('/api/v1/notes')
        if (response.ok) {
          const apiNotes = await response.json()
          
          // Check for legacy localStorage notes to migrate
          const local = localStorage.getItem('unbound_notes')
          if (local) {
            const localNotes = JSON.parse(local)
            const migrated = []
            for (const note of localNotes) {
              try {
                const res = await fetch('/api/v1/notes', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    book: note.book || null,
                    chapter: note.chapter ? parseInt(note.chapter) : null,
                    verse: note.verse ? parseInt(note.verse) : null,
                    text: note.text,
                    tags: note.tags || []
                  })
                })
                if (res.ok) {
                  const savedNote = await res.json()
                  migrated.push(savedNote)
                }
              } catch (err) {
                console.error("Migration of note failed:", err)
              }
            }
            // Clear legacy local storage once migrated
            localStorage.removeItem('unbound_notes')
            setNotes([...apiNotes, ...migrated])
          } else {
            setNotes(apiNotes)
          }
        }
      } catch (err) {
        console.error("Failed to fetch notes from API:", err)
        // Fallback to local storage if API is offline
        const loadedNotes = localStorage.getItem('unbound_notes')
        if (loadedNotes) setNotes(JSON.parse(loadedNotes))
      }
    }
    
    fetchNotes()

    const loadedSessions = localStorage.getItem('unbound_saved_studies')
    if (loadedSessions) {
      setSavedSessions(JSON.parse(loadedSessions))
    }
  }, [])

  // Retrieve unique tags from notes
  const getAllTags = () => {
    const tags = new Set()
    notes.forEach(note => {
      if (note.tags) {
        note.tags.forEach(t => tags.add(t))
      }
    })
    return Array.from(tags)
  }

  // Delete note
  const handleDeleteNote = async (id) => {
    if (!window.confirm('Are you sure you want to delete this note?')) return
    
    const isApiNote = typeof id === 'number'
    
    if (isApiNote) {
      try {
        const res = await fetch(`/api/v1/notes/${id}`, { method: 'DELETE' })
        if (res.ok) {
          setNotes(prev => prev.filter(n => n.id !== id))
        } else {
          alert('Failed to delete note from database.')
        }
      } catch (err) {
        console.error(err)
      }
    } else {
      const updated = notes.filter(n => n.id !== id)
      setNotes(updated)
      localStorage.setItem('unbound_notes', JSON.stringify(updated))
    }
  }

  // Edit Note
  const startEditNote = (note) => {
    setEditingNoteId(note.id)
    setEditingText(note.text)
  }

  const handleSaveEdit = async () => {
    const isApiNote = typeof editingNoteId === 'number'
    
    if (isApiNote) {
      try {
        const res = await fetch(`/api/v1/notes/${editingNoteId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: editingText
          })
        })
        if (res.ok) {
          const updatedNote = await res.json()
          setNotes(prev => prev.map(n => n.id === editingNoteId ? updatedNote : n))
          setEditingNoteId(null)
        } else {
          alert('Failed to update note in database.')
        }
      } catch (err) {
        console.error(err)
      }
    } else {
      const updated = notes.map(n => {
        if (n.id === editingNoteId) {
          return { ...n, text: editingText, timestamp: new Date().toISOString() }
        }
        return n
      })
      setNotes(updated)
      localStorage.setItem('unbound_notes', JSON.stringify(updated))
      setEditingNoteId(null)
    }
  }

  // Delete Session
  const handleDeleteSession = (id) => {
    if (!window.confirm('Delete this saved study session?')) return
    const updated = savedSessions.filter(s => s.id !== id)
    setSavedSessions(updated)
    localStorage.setItem('unbound_saved_studies', JSON.stringify(updated))
  }

  // Export Notes
  const handleExport = () => {
    const formattedNotes = notes.map(n => {
      const location = n.book ? `${n.book} ${n.chapter}:${n.verse}` : 'General Topic'
      return `=== NOTE (${location}) ===\nDate: ${new Date(n.created_at || n.timestamp).toLocaleString()}\nTags: ${n.tags ? n.tags.join(', ') : ''}\nContent:\n${n.text}\n\n`
    }).join('\n')

    const blob = new Blob([formattedNotes], { type: 'text/plain;charset=utf-8' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = 'unbound_bible_notes.txt'
    link.click()
  }

  // Filter Notes
  const filteredNotes = notes.filter(n => {
    const matchesSearch = n.text.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          (n.book && n.book.toLowerCase().includes(searchQuery.toLowerCase()))
    const matchesTag = selectedTag ? n.tags && n.tags.includes(selectedTag) : true
    return matchesSearch && matchesTag
  })

  // Filter Sessions
  const filteredSessions = savedSessions.filter(s => {
    return s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
           (s.book && s.book.toLowerCase().includes(searchQuery.toLowerCase()))
  })

  return (
    <div className="saved-studies-page glass-panel">
      <div className="saved-header">
        <span className="saved-badge">📂 PERSONAL LIBRARY</span>
        <h2>Notes & Saved Studies</h2>
        <p className="subtitle">Manage your bookmarked verses, outline notes, and saved study sessions.</p>
      </div>

      {/* Control row */}
      <div className="controls-row">
        <div className="view-toggle">
          <button className={`toggle-btn ${activeView === 'notes' ? 'active' : ''}`} onClick={() => setActiveView('notes')}>
            📝 Verse Notes ({notes.length})
          </button>
          <button className={`toggle-btn ${activeView === 'sessions' ? 'active' : ''}`} onClick={() => setActiveView('sessions')}>
            🤖 AI Q&A Sessions ({savedSessions.length})
          </button>
        </div>

        <div className="search-filter-wrapper">
          <input 
            type="text" 
            placeholder="Search notes or book names..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
          />
          {activeView === 'notes' && notes.length > 0 && (
            <button className="export-btn" onClick={handleExport}>
              📥 Export All Notes
            </button>
          )}
        </div>
      </div>

      <div className="saved-content-grid">
        
        {/* VIEW 1: NOTES LIST */}
        {activeView === 'notes' && (
          <div className="notes-view-layout">
            {/* Tag Sidebar filter */}
            {getAllTags().length > 0 && (
              <div className="tags-sidebar">
                <h4>Filter by Tag</h4>
                <div className="tags-buttons-list">
                  <button className={`tag-filter-btn ${!selectedTag ? 'active' : ''}`} onClick={() => setSelectedTag('')}>
                    All Tags
                  </button>
                  {getAllTags().map(t => (
                    <button 
                      key={t}
                      className={`tag-filter-btn ${selectedTag === t ? 'active' : ''}`}
                      onClick={() => setSelectedTag(t)}
                    >
                      🏷️ {t}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="notes-list-area">
              {filteredNotes.length === 0 ? (
                <div className="empty-workspace-card">
                  <p>No notes found matching your criteria.</p>
                  <span className="tip-txt">Tip: Tap on any verse in the Scripture Reader or comparison view to create notes.</span>
                </div>
              ) : (
                <div className="notes-vertical-flex">
                  {filteredNotes.map((note) => (
                    <div key={note.id} className="note-item-card glass-panel">
                      <div className="note-card-header">
                        <span className="note-verse-tag">
                          📖 {note.book ? `${note.book} ${note.chapter}:${note.verse}` : 'General note'}
                        </span>
                        <span className="note-date-txt">
                          {new Date(note.created_at || note.timestamp).toLocaleDateString()}
                        </span>
                      </div>

                      {editingNoteId === note.id ? (
                        <div className="note-editing-area">
                          <textarea 
                            value={editingText}
                            onChange={(e) => setEditingText(e.target.value)}
                            rows="4"
                          />
                          <div className="edit-actions">
                            <button className="btn-save" onClick={handleSaveEdit}>Save</button>
                            <button className="btn-cancel" onClick={() => setEditingNoteId(null)}>Cancel</button>
                          </div>
                        </div>
                      ) : (
                        <p className="note-text-body">{note.text}</p>
                      )}

                      <div className="note-card-footer">
                        <div className="note-tags-flex">
                          {note.tags?.map(t => <span key={t} className="mini-tag">#{t}</span>)}
                        </div>
                        {editingNoteId !== note.id && (
                          <div className="note-actions">
                            <button onClick={() => startEditNote(note)} className="action-btn-edit">✏️ Edit</button>
                            <button onClick={() => handleDeleteNote(note.id)} className="action-btn-del">🗑️ Delete</button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* VIEW 2: AI CHAT SESSIONS */}
        {activeView === 'sessions' && (
          <div className="sessions-view-layout">
            {filteredSessions.length === 0 ? (
              <div className="empty-workspace-card">
                <p>No saved AI study conversations found.</p>
                <span className="tip-txt">Tip: Save conversation logs in the Ask the Bible or Study Assistant sidebar to store them here.</span>
              </div>
            ) : (
              <div className="sessions-grid-layout">
                {filteredSessions.map((session) => (
                  <div key={session.id} className="session-item-card glass-panel">
                    <div className="session-card-header">
                      <h4>{session.title}</h4>
                      <button className="session-del-btn" onClick={() => handleDeleteSession(session.id)} title="Delete Session">✕</button>
                    </div>
                    
                    <div className="session-metadata">
                      <span>📅 Saved: {session.date}</span>
                      {session.book && <span>📖 Verse: {session.book} {session.chapter}:{session.verse}</span>}
                    </div>

                    <div className="session-chat-preview">
                      <h5>Conversation History ({session.messages?.length || 0} messages):</h5>
                      <div className="preview-scroller">
                        {session.messages?.map((msg, idx) => (
                          <div key={idx} className={`preview-row ${msg.type}`}>
                            <strong>{msg.type === 'user' ? 'You:' : 'AI:'}</strong>
                            <p>{msg.content.slice(0, 120)}{msg.content.length > 120 ? '...' : ''}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}

export default SavedStudies
