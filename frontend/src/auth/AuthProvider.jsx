import { useEffect, useMemo, useState } from 'react'
import { api, credentials } from '../api/client'
import { AuthContext } from './authContext'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    let active = true
    if (!credentials.hasSession) { setStatus('anonymous'); return () => { active = false } }
    api.get('/auth/me').then((current) => {
      if (active) { setUser(current); setStatus('authenticated') }
    }).catch(() => {
      credentials.clear()
      if (active) setStatus('anonymous')
    })
    return () => { active = false }
  }, [])

  const authenticate = async (path, payload) => {
    const tokens = await api.post(path, payload)
    credentials.set(tokens)
    const current = await api.get('/auth/me')
    setUser(current); setStatus('authenticated')
    return current
  }

  const value = useMemo(() => ({
    user, status,
    login: (payload) => authenticate('/auth/login', payload),
    register: (payload) => authenticate('/auth/register', payload),
    refresh: () => api.get('/auth/me'),
    logout: async () => {
      const refreshToken = credentials.refreshToken
      if (refreshToken) await api.post('/auth/logout', { refresh_token: refreshToken }).catch(() => {})
      credentials.clear(); setUser(null); setStatus('anonymous')
    }
  }), [user, status])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
