import { useEffect, useRef, useState } from 'react'
import StudyAssistantSidebar from '../StudyAssistantSidebar'

const TOOLS = [
  { id: 'insights', label: 'Insights', icon: '✦' },
  { id: 'cross-references', label: 'Cross-References', icon: '↗' },
  { id: 'words', label: 'Words', icon: '文' },
  { id: 'notes', label: 'Notes', icon: '□' },
]

const TOOL_DESTINATIONS = {
  insights: { initialTab: 'insights', initialInsightSubTab: 'commentary' },
  'cross-references': { initialTab: 'insights', initialInsightSubTab: 'crossrefs' },
  words: { initialTab: 'insights', initialInsightSubTab: 'lexicon' },
  notes: { initialTab: 'insights', initialInsightSubTab: 'canon' },
}

export default function ComparisonStudyDrawer({
  open,
  triggerRef,
  book,
  chapter,
  verse,
  onClose,
  onAddNote,
  initialTool = 'insights',
}) {
  const [activeTool, setActiveTool] = useState(initialTool)
  const closeRef = useRef(null)
  const drawerRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    setActiveTool(initialTool)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()

    const closeDrawer = () => {
      triggerRef?.current?.focus()
      onClose()
    }
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeDrawer()
        return
      }
      if (event.key !== 'Tab') return
      const focusable = drawerRef.current?.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href]',
      )
      if (!focusable?.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [initialTool, onClose, open, triggerRef])

  if (!open) return null

  const toolDestination = TOOL_DESTINATIONS[activeTool] ?? TOOL_DESTINATIONS.insights

  const closeDrawer = () => {
    triggerRef?.current?.focus()
    onClose()
  }

  return (
    <div className="comparison-study-layer">
      <button
        type="button"
        className="comparison-study-backdrop"
        aria-label="Dismiss Study Tools backdrop"
        onClick={closeDrawer}
      />
      <aside
        ref={drawerRef}
        className="comparison-study-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="comparison-study-title"
      >
        <header className="comparison-study-header">
          <div>
            <p className="compare-eyebrow">Study companion</p>
            <h2 id="comparison-study-title">Study Tools</h2>
          </div>
          <button ref={closeRef} type="button" aria-label="Close Study Tools" onClick={closeDrawer}>×</button>
        </header>

        <div className="comparison-study-tabs" role="tablist" aria-label="Study tools">
          {TOOLS.map((tool) => (
            <button
              type="button"
              role="tab"
              key={tool.id}
              aria-selected={activeTool === tool.id}
              aria-controls="comparison-study-panel"
              tabIndex={activeTool === tool.id ? 0 : -1}
              onClick={() => setActiveTool(tool.id)}
              onKeyDown={(event) => {
                if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
                event.preventDefault()
                const tabs = [...event.currentTarget.parentElement.querySelectorAll('[role="tab"]')]
                const currentIndex = tabs.indexOf(event.currentTarget)
                const nextIndex = event.key === 'Home'
                  ? 0
                  : event.key === 'End'
                    ? tabs.length - 1
                    : (currentIndex + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length
                tabs[nextIndex]?.focus()
                setActiveTool(TOOLS[nextIndex].id)
              }}
            >
              <span aria-hidden="true">{tool.icon}</span>
              {tool.label}
            </button>
          ))}
        </div>

        <div
          id="comparison-study-panel"
          className={`comparison-study-content tool-${activeTool}`}
          role="tabpanel"
          aria-label={TOOLS.find((tool) => tool.id === activeTool)?.label}
        >
          <StudyAssistantSidebar
            book={book}
            chapter={chapter}
            verse={verse}
            onClose={closeDrawer}
            onAddNote={onAddNote}
            initialTab={toolDestination.initialTab}
            initialInsightSubTab={toolDestination.initialInsightSubTab}
          />
        </div>

        <button type="button" className="comparison-ask-assistant" aria-label="Ask Study Assistant" onClick={() => setActiveTool('insights')}>
          <strong>✦ Ask Study Assistant</strong>
          <span>Ask any question about this passage</span>
        </button>
      </aside>
    </div>
  )
}
