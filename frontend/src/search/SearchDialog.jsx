import { useEffect, useId, useRef, useState } from 'react'
import { api } from '../api/client'
import useDialogFocus from '../reader/useDialogFocus'

export default function SearchDialog({ open, onClose, onNavigate }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [state, setState] = useState('idle')
  const [active, setActive] = useState(-1)
  const inputRef = useRef(null)
  const dialogRef = useRef(null)
  const resultListId = useId()
  const optionIdPrefix = useId()
  useDialogFocus({ open, containerRef: dialogRef, initialRef: inputRef, onClose })

  useEffect(() => {
    if (!open || query.trim().length < 2) {
      setResults([])
      setActive(-1)
      setState('idle')
      return undefined
    }
    const controller = new AbortController()
    let currentRequest = true
    const timer = setTimeout(() => {
      setState('loading')
      api.get(`/search?q=${encodeURIComponent(query.trim())}`, { signal: controller.signal })
        .then((data) => {
          if (!currentRequest || controller.signal.aborted) return
          const nextResults = Array.isArray(data?.results) ? data.results : []
          setResults(nextResults)
          setActive(-1)
          setState(nextResults.length ? 'ready' : 'empty')
        })
        .catch((error) => {
          if (currentRequest && error.name !== 'AbortError') setState('error')
        })
    }, 200)
    return () => {
      currentRequest = false
      clearTimeout(timer)
      controller.abort()
    }
  }, [open, query])

  if (!open) return null
  const keyDown = (event) => {
    if (event.key === 'ArrowDown') { event.preventDefault(); setActive((value) => Math.min(value + 1, results.length - 1)) }
    if (event.key === 'ArrowUp') { event.preventDefault(); setActive((value) => Math.max(value - 1, 0)) }
    if (event.key === 'Enter' && results[active]) { event.preventDefault(); onNavigate(results[active].url) }
  }
  return <div className="search-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <div ref={dialogRef} className="search-dialog" role="dialog" aria-modal="true" aria-label="Search" tabIndex="-1">
      <div className="search-field"><span aria-hidden="true">⌕</span><input ref={inputRef} role="combobox" aria-label="Search the library" aria-controls={resultListId} aria-expanded={results.length > 0} aria-activedescendant={active >= 0 && results[active] ? `${optionIdPrefix}-option-${active}` : undefined} value={query} onChange={(event) => { setQuery(event.target.value); setActive(-1) }} onKeyDown={keyDown} placeholder="Search Scripture, studies, places…" /><kbd>Esc</kbd></div>
      <div id={resultListId} role="listbox" aria-label="Search results" className="search-results">
        {results.map((result, index) => <button id={`${optionIdPrefix}-option-${index}`} key={`${result.group}-${result.id}`} role="option" aria-selected={index === active} className={index === active ? 'active' : ''} onMouseEnter={() => setActive(index)} onClick={() => onNavigate(result.url)}><span><small>{result.group.replace('_', ' ')}</small><strong>{result.title}</strong><p>{result.excerpt}</p></span><span aria-hidden="true">→</span></button>)}
        {state === 'loading' && <p role="status">Searching your library…</p>}
        {state === 'empty' && <p role="status">No results found. Try a book, passage, person, or theme.</p>}
        {state === 'error' && <p role="status">Search is temporarily unavailable. Please try again.</p>}
        {state === 'idle' && <p className="search-hint">Press ↑ or ↓ to choose, then Enter to open.</p>}
      </div>
    </div>
  </div>
}
