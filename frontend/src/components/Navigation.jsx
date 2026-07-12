import { useEffect, useRef, useState } from 'react'
import './Navigation.css'

const GROUPS = [
  {
    id: 'scriptures', label: 'Scriptures', icon: '◫', pages: ['apocrypha', 'textual', 'canon-compare'],
    items: [
      ['apocrypha', 'Scripture Reader', '◧'],
      ['textual', 'Compare Scripture', '⇄'],
      ['canon-compare', 'Canon Comparison', '≡']
    ]
  },
  {
    id: 'decolonial', label: 'Decolonial Audit', icon: '⚖', pages: ['race-misuse', 'bias-explorer', 'factbook'],
    items: [
      ['race-misuse', 'Race & Misuse', '✦'],
      ['bias-explorer', 'Translation Bias', '⌁'],
      ['factbook', 'Factbook Encyclopedia', '▣']
    ]
  },
  {
    id: 'aistudy', label: 'AI Study', icon: '✧', pages: ['chat', 'sermon'],
    items: [
      ['chat', 'Ask the Bible', '✧'],
      ['sermon', 'Sermon Analysis', '◉']
    ]
  },
  {
    id: 'research', label: 'Research', icon: '⌕', pages: ['research', 'media', 'map'],
    items: [
      ['research', 'Research Hub', '⌕'],
      ['media', 'Interactive Media', '◇'],
      ['map', 'Biblical Map', '⌖']
    ]
  },
  {
    id: 'library', label: 'My Library', icon: '▤', pages: ['notes', 'forum'],
    items: [
      ['notes', 'Saved Studies', '▤'],
      ['forum', 'Community', '◎']
    ]
  }
]

function Navigation({ currentPage, onPageChange }) {
  const [openDropdown, setOpenDropdown] = useState(null)
  const [mobileOpen, setMobileOpen] = useState(false)
  const triggerRefs = useRef({})

  const navigate = (page) => {
    onPageChange(page)
    setOpenDropdown(null)
    setMobileOpen(false)
  }

  const toggleDropdown = (name, event) => {
    event.stopPropagation()
    setOpenDropdown((previous) => previous === name ? null : name)
  }

  useEffect(() => {
    const closeAll = () => setOpenDropdown(null)
    const handleKeyDown = (event) => {
      if (event.key !== 'Escape') return
      const openTrigger = openDropdown ? triggerRefs.current[openDropdown] : null
      setOpenDropdown(null)
      setMobileOpen(false)
      openTrigger?.focus()
    }

    window.addEventListener('click', closeAll)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('click', closeAll)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [openDropdown])

  return (
    <nav className="navigation" aria-label="Primary navigation">
      <div className="nav-container">
        <button className="nav-logo" type="button" onClick={() => navigate('home')}>
          <span className="logo-mark" aria-hidden="true">U</span>
          <span className="logo-copy">
            <span className="logo-text">The Unbound Bible</span>
            <span className="logo-subtitle">Study beyond the margins</span>
          </span>
        </button>

        <button
          className="mobile-menu-trigger"
          type="button"
          aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'}
          aria-expanded={mobileOpen}
          aria-controls="primary-navigation-links"
          onClick={(event) => {
            event.stopPropagation()
            setMobileOpen((open) => !open)
          }}
        >
          <span aria-hidden="true">{mobileOpen ? '×' : '☰'}</span>
        </button>

        <div id="primary-navigation-links" className={`nav-links ${mobileOpen ? 'is-mobile-open' : ''}`}>
          <button
            className={`nav-item home-link ${currentPage === 'home' ? 'active' : ''}`}
            type="button"
            onClick={() => navigate('home')}
          >
            <span className="nav-icon" aria-hidden="true">⌂</span>
            <span>Home</span>
          </button>

          {GROUPS.map((group) => {
            const isOpen = openDropdown === group.id
            const isActive = group.pages.includes(currentPage)
            return (
              <div className={`nav-dropdown ${isOpen ? 'is-open' : ''}`} key={group.id}>
                <button
                  ref={(node) => { triggerRefs.current[group.id] = node }}
                  className={`nav-item dropdown-trigger ${isActive ? 'active' : ''}`}
                  type="button"
                  aria-label={group.label}
                  aria-expanded={isOpen}
                  aria-controls={`${group.id}-menu`}
                  onClick={(event) => toggleDropdown(group.id, event)}
                >
                  <span className="nav-icon" aria-hidden="true">{group.icon}</span>
                  <span>{group.label}</span>
                  <span className="dropdown-arrow" aria-hidden="true">⌄</span>
                </button>
                <div id={`${group.id}-menu`} className="dropdown-menu" hidden={!isOpen}>
                  <div className="dropdown-kicker">{group.label}</div>
                  {group.items.map(([page, label, icon]) => (
                    <button
                      className={`dropdown-item ${currentPage === page ? 'active' : ''}`}
                      type="button"
                      onClick={() => navigate(page)}
                      key={page}
                    >
                      <span className="nav-icon" aria-hidden="true">{icon}</span>
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              </div>
            )
          })}
        </div>

        <div className="nav-actions">
          <button className="nav-action-btn" type="button" aria-label="Search" onClick={() => navigate('factbook')}>
            <span aria-hidden="true">⌕</span>
          </button>
          <button className="nav-action-btn" type="button" aria-label="Notifications" onClick={() => navigate('notes')}>
            <span aria-hidden="true">◌</span>
          </button>
          <button className="nav-signin" type="button" onClick={() => navigate('forum')}>
            <span aria-hidden="true">◉</span>
            <span>Sign in</span>
          </button>
        </div>
      </div>
    </nav>
  )
}

export default Navigation
