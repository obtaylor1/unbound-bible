import { useEffect, useState } from 'react'
import { getShare } from '../services/sharingApi'

export default function PublicStudyPage({ shareId }) {
  const [study, setStudy] = useState(null)
  const [state, setState] = useState('loading')
  useEffect(() => { getShare(shareId).then((data) => { setStudy(data); setState('ready') }).catch((error) => setState(error.status === 410 ? 'revoked' : 'missing')) }, [shareId])
  if (state === 'loading') return <main className="page-container" role="status">Opening shared study…</main>
  if (state !== 'ready') return <main className="page-container"><div className="empty-workspace-card" role="status"><h1>Study unavailable</h1><p>{state === 'revoked' ? 'This shared study is no longer available.' : 'This link is invalid, private, or has been removed.'}</p></div></main>
  return <main className="page-container"><article className="glass-panel" style={{ padding: 'clamp(24px, 5vw, 64px)', maxWidth: 900, margin: '40px auto' }}><p className="eyebrow">SHARED STUDY SNAPSHOT</p><h1>{study.title}</h1><p>This is a read-only snapshot. Its contents do not change when the owner continues studying.</p>{study.messages.map((message, index) => <section key={index}><h2>{message.role === 'assistant' ? 'Study response' : 'Question'}</h2><p>{message.content}</p></section>)}{study.sources?.length > 0 && <section><h2>Sources</h2>{study.sources.map((source, index) => <div key={index}><strong>{source.title}</strong><p>{source.citation}</p></div>)}</section>}</article></main>
}
