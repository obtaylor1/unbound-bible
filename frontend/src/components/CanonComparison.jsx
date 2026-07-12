import { useState, useEffect } from 'react'
import './CanonComparison.css'

function CanonComparison() {
  const [comparisonData, setComparisonData] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedBook, setSelectedBook] = useState(null)
  const [filterTestament, setFilterTestament] = useState('all') // 'all', 'OT', 'NT', 'Apoc', 'Pseud'

  useEffect(() => {
    const fetchComparison = async () => {
      try {
        const res = await fetch('/api/v1/canons/compare')
        if (res.ok) {
          const data = await res.json()
          setComparisonData(data.books || [])
        }
      } catch (err) {
        console.error('Failed to fetch canon comparison:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchComparison()
  }, [])

  const filteredBooks = comparisonData.filter(b => {
    if (filterTestament === 'all') return true
    return b.testament === filterTestament
  })

  const canons = [
    { code: 'PROT66', name: 'Protestant (66)', color: 'rgba(239, 68, 68, 0.7)' },
    { code: 'CATH73', name: 'Catholic (73)', color: 'rgba(245, 158, 11, 0.7)' },
    { code: 'ETHIO81', name: 'Ethiopian Orthodox (81)', color: 'rgba(139, 92, 246, 0.9)' },
    { code: 'BROADER', name: 'Broader Canon (85+)', color: 'rgba(16, 185, 129, 0.7)' }
  ]

  const getBookTypeLabel = (testament) => {
    switch (testament) {
      case 'OT': return 'Old Testament'
      case 'NT': return 'New Testament'
      case 'Apoc': return 'Deuterocanon (Greek)'
      case 'Pseud': return 'Ethiopian Preserved'
      default: return testament
    }
  }

  return (
    <div className="canon-comparison-container">
      <div className="workspace-layout">
        <div className="matrix-panel">
          <div className="panel-header">
            <h2>Biblical Canon Comparison</h2>
            <p>Compare book inclusions across global Christian traditions. The Ethiopian Orthodox canon preserves Second Temple Jewish texts lost in Western traditions.</p>
          </div>

          <div className="filter-bar">
            <button className={`filter-btn ${filterTestament === 'all' ? 'active' : ''}`} onClick={() => setFilterTestament('all')}>All Books</button>
            <button className={`filter-btn ${filterTestament === 'OT' ? 'active' : ''}`} onClick={() => setFilterTestament('OT')}>Hebrew Covenant (OT)</button>
            <button className={`filter-btn ${filterTestament === 'NT' ? 'active' : ''}`} onClick={() => setFilterTestament('NT')}>Greek Covenant (NT)</button>
            <button className={`filter-btn ${filterTestament === 'Apoc' ? 'active' : ''}`} onClick={() => setFilterTestament('Apoc')}>Deuterocanon / Apocrypha</button>
            <button className={`filter-btn ${filterTestament === 'Pseud' ? 'active' : ''}`} onClick={() => setFilterTestament('Pseud')}>Ethiopian Preserved (Enoch, Jubilees, etc.)</button>
          </div>

          {loading ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <span>Generating Canon Matrix Grid...</span>
            </div>
          ) : (
            <div className="matrix-table-container">
              <table className="matrix-table">
                <thead>
                  <tr>
                    <th>Book Name</th>
                    <th>Tradition Category</th>
                    {canons.map(c => (
                      <th key={c.code} style={{ borderBottomColor: c.color }}>{c.name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredBooks.map(b => {
                    const isEthiopianUnique = b.testament === 'Pseud'
                    return (
                      <tr 
                        key={b.book_id} 
                        className={`book-row ${selectedBook?.book_id === b.book_id ? 'selected' : ''} ${isEthiopianUnique ? 'ethiopian-unique' : ''}`}
                        onClick={() => setSelectedBook(b)}
                      >
                        <td className="book-name-cell">
                          {b.name}
                          {isEthiopianUnique && <span className="unique-badge">Ethiopian-Preserved</span>}
                        </td>
                        <td className="book-category-cell">
                          <span className={`category-tag ${b.testament.toLowerCase()}`}>{getBookTypeLabel(b.testament)}</span>
                        </td>
                        {canons.map(c => {
                          const included = b.in_canons.includes(c.code) || (c.code === 'ETHIO81' && b.in_canons.includes('ETH81'))
                          return (
                            <td key={c.code} className="inclusion-cell">
                              {included ? (
                                <span className="checkmark" style={{ color: c.color }}>✔</span>
                              ) : (
                                <span className="cross">✕</span>
                              )}
                            </td>
                          )
                        })}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className={`details-drawer ${selectedBook ? 'open' : ''}`}>
          {selectedBook ? (
            <div className="drawer-content">
              <button className="close-drawer" onClick={() => setSelectedBook(null)}>×</button>
              <span className={`category-tag ${selectedBook.testament.toLowerCase()}`}>
                {getBookTypeLabel(selectedBook.testament)}
              </span>
              <h3>{selectedBook.name}</h3>
              
              <div className="section-block">
                <h4>Significance & Decolonial Context</h4>
                <p className="scholarly-text">{selectedBook.significance}</p>
              </div>

              <div className="section-block">
                <h4>Scribal Notes & Metadata</h4>
                <p className="notes-text">{selectedBook.notes || 'No notes available. Standard canonical text in EOTC tradition.'}</p>
              </div>

              <div className="section-block">
                <h4>Canon Attestation List</h4>
                <ul className="attestation-list">
                  {canons.map(c => {
                    const included = selectedBook.in_canons.includes(c.code) || (c.code === 'ETHIO81' && selectedBook.in_canons.includes('ETH81'))
                    return (
                      <li key={c.code} className={included ? 'included' : 'excluded'}>
                        <span className="dot"></span>
                        <span className="canon-name">{c.name}:</span>
                        <span className="status">{included ? 'Included (Canonical)' : 'Omitted (Apocryphal)'}</span>
                      </li>
                    )
                  })}
                </ul>
              </div>
            </div>
          ) : (
            <div className="empty-drawer">
              <span className="drawer-icon">📜</span>
              <p>Select any book in the matrix to view translation history, manuscript witnesses, and theological significance.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default CanonComparison
