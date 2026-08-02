export default function SkipLink({ targetId = 'main-content' }) {
  const focusTarget = (event) => {
    event.preventDefault()
    const target = document.getElementById(targetId)
    if (!target) return
    target.focus({ preventScroll: true })
    target.scrollIntoView?.({ block: 'start' })
  }

  return (
    <a className="skip-link" href={`#${targetId}`} onClick={focusTarget}>
      Skip to main content
    </a>
  )
}
