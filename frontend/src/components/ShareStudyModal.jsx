import { useEffect, useRef, useState } from 'react'
import './ShareStudyModal.css'
import { createShare, updateShare } from '../services/sharingApi'

export default function ShareStudyModal({ isOpen, onClose, shareData }) {
  const [visibility, setVisibility] = useState('unlisted')
  const [created, setCreated] = useState(null)
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  const closeButtonRef = useRef(null)
  const previousFocusRef = useRef(null)

  useEffect(() => {
    if (!isOpen) return
    previousFocusRef.current = document.activeElement; closeButtonRef.current?.focus()
    const escape = (event) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('keydown', escape); previousFocusRef.current?.focus() }
  }, [isOpen, onClose])

  if (!isOpen || !shareData) return null
  const shareUrl = created ? `${window.location.origin}/share/${created.share_id}` : ''
  const persist = async () => {
    setState('creating'); setError('')
    try { const result = await createShare({ study_id: shareData.studyId, title: shareData.title, visibility }); setCreated(result); setState('created') }
    catch (caught) { setError(caught.message); setState('error') }
  }
  const changeVisibility = async (next) => {
    if (next === 'public' && !window.confirm('Publish this snapshot to the public Community listing?')) return
    setVisibility(next)
    if (created) try { setCreated(await updateShare(created.share_id, next)) } catch (caught) { setError(caught.message) }
  }
  const copy = async () => { setState('copying'); await navigator.clipboard.writeText(shareUrl); setState('copied') }
  const emailHref = `mailto:?subject=${encodeURIComponent(shareData.title)}&body=${encodeURIComponent(`Explore this study: ${shareUrl}`)}`
  const whatsappHref = `https://wa.me/?text=${encodeURIComponent(`${shareData.title} — ${shareUrl}`)}`

  return <div className="share-modal-overlay" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <div className="share-modal-card glass-panel" role="dialog" aria-modal="true" aria-labelledby="share-dialog-title">
      <div className="modal-header"><h3 id="share-dialog-title">Share study session</h3><button ref={closeButtonRef} className="close-btn" aria-label="Close sharing dialog" onClick={onClose}>✕</button></div>
      <div className="modal-body">
        <div className="share-summary-box"><span className="summary-label">Session type</span><span className="summary-val">{shareData.type}</span><span className="summary-label">Title</span><span className="summary-val bold">{shareData.title}</span></div>
        <label className="toggle-label-group">Who can view this snapshot?<select value={visibility} onChange={(event) => changeVisibility(event.target.value)} disabled={state === 'creating'}><option value="private">Only me</option><option value="unlisted">Anyone with the link</option><option value="public">Public Community listing</option></select></label>
        {!created ? <button className="copy-btn" onClick={persist} disabled={state === 'creating' || !shareData.studyId}>{state === 'creating' ? 'Creating secure link…' : 'Create link'}</button> : <><div className="link-output-box"><input aria-label="Share link" value={shareUrl} readOnly className="share-url-input" /><button className={`copy-btn ${state === 'copied' ? 'success' : ''}`} onClick={copy}>{state === 'copied' ? 'Copied ✓' : 'Copy link'}</button></div><div className="share-intents"><a href={emailHref}>Email</a><a href={whatsappHref} target="_blank" rel="noreferrer">WhatsApp</a></div></>}
        {!shareData.studyId && <p className="share-availability-note">Save this study to your library before sharing it.</p>}
        {error && <p role="alert" className="share-availability-note">{error} <button onClick={persist}>Retry</button></p>}
      </div>
      <div className="modal-footer"><p className="disclaimer-txt">Shared links use an immutable snapshot, preserving citations without exposing private account details.</p></div>
    </div>
  </div>
}
