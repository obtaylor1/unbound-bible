import { useEffect, useRef, useState } from 'react'
import AccountMenu from '../auth/AccountMenu'
import AuthDialog from '../auth/AuthDialog'
import { useAuth } from '../auth/authContext'

export default function ReaderHeader({
  onHome,
  onOpenBooks,
  onOpenStudyTools,
}) {
  const [authOpen, setAuthOpen] = useState(false)
  const { user } = useAuth()
  const authContainerRef = useRef(null)
  const headerActionsRef = useRef(null)
  const signInTriggerRef = useRef(null)
  const shouldRestoreAuthFocusRef = useRef(false)

  function openAuthDialog() {
    shouldRestoreAuthFocusRef.current = true
    setAuthOpen(true)
  }

  useEffect(() => {
    if (!authOpen) return undefined

    const dialog = authContainerRef.current?.querySelector('[role="dialog"]')
    if (!dialog) return undefined

    const focusableElements = () => (
      [...dialog.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      )].filter((element) => element.getAttribute('aria-hidden') !== 'true')
    )

    const initialFocus = dialog.querySelector('input:not([disabled])')
      || focusableElements()[0]
    initialFocus?.focus()

    function handleDialogKeyDown(event) {
      if (event.key === 'Escape') {
        event.preventDefault()
        setAuthOpen(false)
        return
      }

      if (event.key !== 'Tab') return

      const focusable = focusableElements()
      if (focusable.length === 0) {
        event.preventDefault()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const activeElement = document.activeElement

      if (event.shiftKey && (activeElement === first || !dialog.contains(activeElement))) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && (activeElement === last || !dialog.contains(activeElement))) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleDialogKeyDown)
    return () => {
      document.removeEventListener('keydown', handleDialogKeyDown)
    }
  }, [authOpen])

  useEffect(() => {
    if (authOpen || !shouldRestoreAuthFocusRef.current) return

    shouldRestoreAuthFocusRef.current = false
    const originalTrigger = signInTriggerRef.current
    const accountTrigger = headerActionsRef.current?.querySelector(
      '.account-menu .nav-signin',
    )
    const fallbackAction = headerActionsRef.current?.querySelector('button')
    const focusTarget = originalTrigger?.isConnected
      ? originalTrigger
      : accountTrigger || fallbackAction

    focusTarget?.focus()
  }, [authOpen, user])

  return (
    <>
      <header className="reader-header">
        <button
          className="reader-header__brand"
          type="button"
          aria-label="The Unbound Bible home"
          onClick={onHome}
        >
          <span className="reader-header__brand-mark" aria-hidden="true">U</span>
          <span className="reader-header__brand-copy">
            <strong>The Unbound Bible</strong>
            <span>Scripture reader</span>
          </span>
        </button>

        <nav
          ref={headerActionsRef}
          className="reader-header__actions"
          aria-label="Scripture reader actions"
        >
          <button type="button" onClick={onOpenBooks}>
            Choose a book
          </button>
          <button type="button" onClick={onOpenStudyTools}>
            Open study tools
          </button>
          {user ? (
            <AccountMenu />
          ) : (
            <button
              ref={signInTriggerRef}
              className="reader-header__sign-in"
              type="button"
              onClick={openAuthDialog}
            >
              Sign in
            </button>
          )}
        </nav>
      </header>

      <div ref={authContainerRef} className="reader-header__auth">
        {authOpen && (
          <AuthDialog open onClose={() => setAuthOpen(false)} />
        )}
      </div>
    </>
  )
}
