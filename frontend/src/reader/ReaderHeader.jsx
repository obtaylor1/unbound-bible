import { useState } from 'react'
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
              className="reader-header__sign-in"
              type="button"
              onClick={() => setAuthOpen(true)}
            >
              Sign in
            </button>
          )}
        </nav>
      </header>

      <AuthDialog open={authOpen} onClose={() => setAuthOpen(false)} />
    </>
  )
}
