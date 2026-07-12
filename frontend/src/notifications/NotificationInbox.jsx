import { useEffect, useState } from 'react'
import { api } from '../api/client'

export default function NotificationInbox() {
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState(0)
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  useEffect(() => { api.get('/notifications/unread-count').then((data) => setCount(data.count)).catch(() => {}) }, [])

  const toggle = async () => {
    const next = !open; setOpen(next); setError('')
    if (next) try { setItems(await api.get('/notifications')) } catch { setError('Could not load notifications.') }
  }
  const read = async (item) => {
    if (item.read_at) return
    const previous = items; setItems(items.map((entry) => entry.id === item.id ? { ...entry, read_at: new Date().toISOString() } : entry)); setCount((value) => Math.max(0, value - 1))
    try { await api.patch(`/notifications/${item.id}/read`, {}) }
    catch { setItems(previous); setCount((value) => value + 1); setError('Could not update the notification. Please try again.') }
  }
  const readAll = async () => {
    const previous = items; const previousCount = count; setItems(items.map((item) => ({ ...item, read_at: item.read_at || new Date().toISOString() }))); setCount(0)
    try { await api.post('/notifications/read-all', {}) } catch { setItems(previous); setCount(previousCount); setError('Could not update notifications.') }
  }
  return <div className="notification-inbox">
    <button className="nav-action-btn" type="button" aria-label={`Notifications${count ? `, ${count} unread` : ''}`} aria-expanded={open} onClick={toggle}><span aria-hidden="true">◌</span>{count > 0 && <span className="notification-badge">{count > 99 ? '99+' : count}</span>}</button>
    {open && <div className="notification-popover"><div className="notification-header"><strong>Notifications</strong>{count > 0 && <button onClick={readAll}>Mark all read</button>}</div>{error && <p role="alert">{error}</p>}<div className="notification-list">{items.length === 0 ? <p>No notifications yet.</p> : items.map((item) => <button key={item.id} className={item.read_at ? 'read' : 'unread'} onClick={() => read(item)} aria-label={item.message}><span>{item.message}</span><small>{new Date(item.created_at).toLocaleDateString()}</small></button>)}</div><a href="#preferences">Notification settings</a></div>}
  </div>
}
