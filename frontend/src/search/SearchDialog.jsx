import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

export default function SearchDialog({ open, onClose, onNavigate }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [state, setState] = useState('idle')
  const [active, setActive] = useState(-1)
  const inputRef = useRef(null)

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const escape = (event) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [open, onClose])

  useEffect(() => {
    if (!open || query.trim().length < 2) { setResults([]); setState('idle'); return }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setState('loading')
      api.get(`/search?q=${encodeURIComponent(query.trim())}`, { signal: controller.signal })
        .then((data) => { setResults(data.results); setActive(-1); setState(data.results.length ? 'ready' : 'empty') })
        .catch((error) => { if (error.name !== 'AbortError') setState('error') })
    }, 200)
    return () => { clearTimeout(timer); controller.abort() }
  }, [open, query])

  if (!open) return null
  const keyDown = (event) => {
    if (event.key === 'ArrowDown') { event.preventDefault(); setActive((value) => Math.min(value + 1, results.length - 1)) }
    if (event.key === 'ArrowUp') { event.preventDefault(); setActive((value) => Math.max(value - 1, 0)) }
    if (event.key === 'Enter' && results[active]) { event.preventDefault(); onNavigate(results[active].url) }
  }
  return <div className="search-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <div className="search-dialog" role="dialog" aria-modal="true" aria-label="Search">
      <div className="search-field"><span aria-hidden="true">⌕</span><input ref={inputRef} role="combobox" aria-label="Search the library" aria-controls="search-results" aria-expanded={results.length > 0} value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={keyDown} placeholder="Search Scripture, studies, places…" /><kbd>Esc</kbd></div>
      <div id="search-results" role="listbox" className="search-results">
        {results.map((result, index) => <button key={`${result.group}-${result.id}`} role="option" aria-selected={index === active} className={index === active ? 'active' : ''} onMouseEnter={() => setActive(index)} onClick={() => onNavigate(result.url)}><span><small>{result.group.replace('_', ' ')}</small><strong>{result.title}</strong><p>{result.excerpt}</p></span><span aria-hidden="true">→</span></button>)}
        {state === 'loading' && <p role="status">Searching your library…</p>}
        {state === 'empty' && <p role="status">No results found. Try a book, passage, person, or theme.</p>}
        {state === 'error' && <p role="status">Search is temporarily unavailable. Please try again.</p>}
        {state === 'idle' && <p className="search-hint">Press ↑ or ↓ to choose, then Enter to open.</p>}
      </div>
    </div>
  </div>
}
