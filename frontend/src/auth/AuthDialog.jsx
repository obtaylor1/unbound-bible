import { useState } from 'react'
import { useAuth } from './authContext'

export default function AuthDialog({ open, onClose }) {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [error, setError] = useState('')
  if (!open) return null

  const submit = async (event) => {
    event.preventDefault(); setError('')
    const data = new FormData(event.currentTarget)
    const payload = { email: data.get('email'), password: data.get('password') }
    if (mode === 'register') payload.username = data.get('username')
    try { await (mode === 'login' ? login(payload) : register(payload)); onClose() }
    catch (caught) { setError(caught.message) }
  }

  return <div className="auth-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <div className="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title">
      <button className="auth-close" onClick={onClose} aria-label="Close">×</button>
      <p className="eyebrow">Your library, everywhere</p>
      <h2 id="auth-title">{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
      <p>Save notes and study conversations privately across your devices.</p>
      <form onSubmit={submit}>
        {mode === 'register' && <label>Username<input name="username" minLength="3" required autoComplete="username" /></label>}
        <label>Email<input name="email" type="email" required autoComplete="email" /></label>
        <label>Password<input name="password" type="password" minLength="12" required autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button className="primary-button" type="submit">{mode === 'login' ? 'Sign in' : 'Create account'}</button>
      </form>
      <button className="auth-switch" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
        {mode === 'login' ? 'New here? Create an account' : 'Already have an account? Sign in'}
      </button>
    </div>
  </div>
}
