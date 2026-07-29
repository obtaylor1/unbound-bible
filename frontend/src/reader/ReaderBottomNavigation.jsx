const items = [
  { label: 'Home', action: 'navigate', page: 'home' },
  { label: 'Bible', action: 'books', current: true },
  { label: 'Search', action: 'search' },
  { label: 'Library', action: 'navigate', page: 'notes' },
  { label: 'More', action: 'navigate', page: 'research' },
]

export default function ReaderBottomNavigation({
  onNavigate,
  onSearch,
  onOpenBooks,
}) {
  const available = (item) => {
    if (item.action === 'navigate') return typeof onNavigate === 'function'
    if (item.action === 'search') return typeof onSearch === 'function'
    return typeof onOpenBooks === 'function'
  }

  const activate = (item) => {
    if (item.action === 'navigate') onNavigate?.(item.page)
    else if (item.action === 'search') onSearch?.()
    else onOpenBooks?.()
  }

  return (
    <nav className="reader-bottom-navigation" aria-label="Mobile reader navigation">
      {items.map((item) => (
        <button
          key={item.label}
          type="button"
          aria-current={item.current ? 'page' : undefined}
          disabled={!available(item)}
          onClick={() => activate(item)}
        >
          <span aria-hidden="true" className="reader-bottom-navigation__mark">
            {item.label.slice(0, 1)}
          </span>
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  )
}
