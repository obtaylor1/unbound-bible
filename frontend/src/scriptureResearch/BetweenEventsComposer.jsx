import { useEffect, useId, useRef, useState } from 'react'
import { searchResearchEvents } from './researchApi'

export default function BetweenEventsComposer({
  question,
  onSubmit,
  searchEvents = searchResearchEvents,
  loading: submitting = false,
}) {
  const [events, setEvents] = useState([])
  const [fromId, setFromId] = useState('')
  const [toId, setToId] = useState('')
  const [status, setStatus] = useState('loading')
  const requestSequence = useRef(0)
  const fromIdAttribute = useId()
  const toIdAttribute = useId()

  useEffect(() => {
    const controller = new AbortController()
    const sequence = requestSequence.current + 1
    requestSequence.current = sequence
    setStatus('loading')
    setEvents([])
    setFromId('')
    setToId('')

    let request
    try {
      request = searchEvents('', { signal: controller.signal })
    } catch {
      if (!controller.signal.aborted && sequence === requestSequence.current) setStatus('error')
      return () => controller.abort()
    }

    Promise.resolve(request).then((result) => {
      if (controller.signal.aborted || sequence !== requestSequence.current) return
      const nextEvents = Array.isArray(result?.events) ? result.events : []
      setEvents(nextEvents)
      setStatus(nextEvents.length ? 'ready' : 'empty')
    }).catch(() => {
      if (!controller.signal.aborted && sequence === requestSequence.current) setStatus('error')
    })

    return () => controller.abort()
  }, [searchEvents])

  if (status === 'loading') return <p role="status">Loading events…</p>
  if (status === 'error') return <p role="alert">Unable to load verified events.</p>
  if (status === 'empty') return <p role="status">No verified events are available.</p>

  const fromIndex = events.findIndex((event) => event.id === fromId)
  const toIndex = events.findIndex((event) => event.id === toId)
  const bothSelected = fromIndex >= 0 && toIndex >= 0
  const sameEvent = bothSelected && fromIndex === toIndex
  const reversed = bothSelected && fromIndex > toIndex
  const valid = bothSelected && fromIndex < toIndex
  let validationMessage = ''
  if (sameEvent) validationMessage = 'Choose two different events.'
  if (reversed) validationMessage = 'The From event must come before the To event.'

  const buildTimeline = () => {
    if (!valid || submitting) return
    const from = events[fromIndex]
    const to = events[toIndex]
    onSubmit({
      question: question.trim() || `What happened between ${from.title} and ${to.title}?`,
      modeParameters: { from_event_id: from.id, to_event_id: to.id },
    })
  }

  return (
    <section className="between-events-composer" aria-label="Build a timeline between events">
      <div className="between-events-composer__selectors">
        <label htmlFor={fromIdAttribute}>From</label>
        <select id={fromIdAttribute} value={fromId} onChange={(event) => setFromId(event.target.value)}>
          <option value="">Choose an event</option>
          {events.map((event) => <option key={event.id} value={event.id}>{event.title}</option>)}
        </select>
        <label htmlFor={toIdAttribute}>To</label>
        <select id={toIdAttribute} value={toId} onChange={(event) => setToId(event.target.value)}>
          <option value="">Choose an event</option>
          {events.map((event) => <option key={event.id} value={event.id}>{event.title}</option>)}
        </select>
      </div>
      {validationMessage && <p role="alert">{validationMessage}</p>}
      <button type="button" disabled={!valid || submitting} onClick={buildTimeline}>Build Timeline</button>
    </section>
  )
}
