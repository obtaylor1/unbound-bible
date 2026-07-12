import { useState } from 'react'
import { useAuth } from './authContext'

export default function AccountMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  return <div className="account-menu">
    <button className="nav-signin" type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
      <span aria-hidden="true">◉</span><span>{user.username}</span>
    </button>
    {open && <div className="account-popover">
      <strong>{user.username}</strong><small>{user.email}</small>
      <button type="button">Preferences</button>
      <button type="button" onClick={logout}>Sign out</button>
    </div>}
  </div>
}
