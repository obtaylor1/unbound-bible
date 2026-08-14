import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ShareStudyModal from '../components/ShareStudyModal'
import { api } from '../api/client'
import { useAuth } from '../auth/authContext'
import { parseReaderHash, readerHash } from '../reader/readerRoute'
import ResearchComposer from './ResearchComposer'
import ResearchLoadingState from './ResearchLoadingState'
import ResearchTrail from './ResearchTrail'
import ResearchWorkspace from './ResearchWorkspace'
import {
  clearGuestResearchSession,
  loadGuestResearchSession,
  runResearch,
  saveGuestResearchSession,
  searchResearchEvents,
} from './researchApi'
import {
  createEmptyResearchSession,
  DEFAULT_RESEARCH_MODE,
  DEFAULT_RESEARCH_SETTINGS,
  SOURCE_SCOPES,
} from './researchModel'

const SOURCE_SCOPE_LABELS = new Map(SOURCE_SCOPES.map((scope) => [scope.value, scope.label]))

const cloneSettings = (settings = DEFAULT_RESEARCH_SETTINGS) => ({
  sourceScopes: [...settings.sourceScopes],
  depth: settings.depth,
  modeParameters: { ...(settings.modeParameters ?? {}) },
})

const requestFromResponse = (response) => response ? {
  question: response.query,
  sourceScopes: [...response.settings.sourceScopes],
  depth: response.settings.depth,
  mode: response.mode,
  modeParameters: { ...(response.settings.modeParameters ?? {}) },
} : null

const resultText = (response) => {
  const sections = [
    response.summary, response.canonicalAccount, ...response.ancientAccounts,
    response.historicalContext, ...response.languageNotes, response.unknowns,
  ].filter(Boolean)
  const parts = sections.flatMap((section) => [
    section.title,
    section.narrative,
    ...section.claims.map((claim) => claim.statement),
  ]).filter(Boolean)
  return parts.join('\n\n') || `Verified evidence for: ${response.query}`
}

const abortError = (error) => error?.name === 'AbortError' || error?.code === 'ERR_CANCELED'

const compactConversationContext = (response) => {
  const entityNames = [...response.people, ...response.places]
    .map((entity) => entity.name)
    .filter((name, index, names) => name && names.indexOf(name) === index)
    .slice(0, 16)
  const sourceReferences = response.sources
    .map((source) => source.reference)
    .filter((reference, index, references) => reference && references.indexOf(reference) === index)
    .slice(0, 16)
  return entityNames.length || sourceReferences.length
    ? { entityNames, sourceReferences }
    : null
}

const readLocalStudies = () => {
  try {
    const stored = JSON.parse(localStorage.getItem('unbound_saved_studies') || '[]')
    return Array.isArray(stored)
      ? stored.filter((item) => item && typeof item === 'object' && !Array.isArray(item))
      : []
  } catch {
    return []
  }
}

const readerHashFromOpenTarget = (target) => {
  if (target.startsWith('#scriptures')) return target
  const current = parseReaderHash()
  const apiMatch = /^\/api\/v1\/texts\/([^/]+)\/(\d+)\/(\d+)\/details$/.exec(target)
  if (apiMatch) {
    return readerHash({
      ...current,
      book: decodeURIComponent(apiMatch[1]),
      chapter: Number(apiMatch[2]),
      verse: Number(apiMatch[3]),
    })
  }
  if (target.startsWith('bible://')) {
    try {
      const parsed = new URL(target)
      const path = parsed.pathname.split('/').filter(Boolean)
      return readerHash({
        ...current,
        book: decodeURIComponent(parsed.hostname),
        chapter: Number(path[0]),
        verse: path[1] ? Number(path[1]) : null,
      })
    } catch {
      return null
    }
  }
  return null
}

function ResultNotice({ state, response, onRetry }) {
  if (state === 'insufficient') {
    const scopeLabels = response?.settings.sourceScopes
      .map((scope) => SOURCE_SCOPE_LABELS.get(scope) ?? scope)
      .join(', ') || 'the selected library sources'
    return (
      <section className="research-result-notice research-result-notice--insufficient">
        <h2>Not enough verified evidence</h2>
        <p>The selected library sources did not contain enough relevant material to answer this question safely.</p>
        <p>Sources without enough verified material: {scopeLabels}.</p>
        <p>Try a narrower question or intentionally add another source scope.</p>
        <button type="button" onClick={onRetry}>Retry research</button>
      </section>
    )
  }
  if (state === 'evidence-only') {
    return (
      <section className="research-result-notice research-result-notice--evidence-only">
        <h2>Verified evidence only</h2>
        <p>The synthesis provider was unavailable, so no AI explanation was created. The verified sources below are still available for study.</p>
        <button type="button" onClick={onRetry}>Retry research</button>
      </section>
    )
  }
  return response ? null : null
}

export default function ScriptureResearchPage({ onPageChange }) {
  const { status: authStatus } = useAuth()
  const initialGuestSession = useMemo(() => (
    authStatus === 'anonymous' ? loadGuestResearchSession() : createEmptyResearchSession()
  ), [authStatus])
  const initialGuestResponse = useMemo(() => {
    if (!initialGuestSession.activeNodeId) return null
    return initialGuestSession.nodes.find((node) => node.id === initialGuestSession.activeNodeId)?.response ?? null
  }, [initialGuestSession])

  const [question, setQuestion] = useState(initialGuestResponse?.query ?? '')
  const [settings, setSettings] = useState(() => cloneSettings(initialGuestResponse?.settings ?? initialGuestSession.settings))
  const [mode, setMode] = useState(initialGuestResponse?.mode ?? DEFAULT_RESEARCH_MODE)
  const [pageState, setPageState] = useState(initialGuestResponse ? (
    initialGuestResponse.groundingStatus === 'insufficient' ? 'insufficient'
      : initialGuestResponse.groundingStatus === 'evidence-only' ? 'evidence-only' : 'success'
  ) : 'empty')
  const [activeResponse, setActiveResponse] = useState(initialGuestResponse)
  const [guestSession, setGuestSession] = useState(initialGuestSession)
  const [authenticatedSession, setAuthenticatedSession] = useState(() => createEmptyResearchSession())
  const [errorMessage, setErrorMessage] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [shareOpen, setShareOpen] = useState(false)
  const [shareData, setShareData] = useState(null)
  const [studyId, setStudyId] = useState(null)
  const activeControllerRef = useRef(null)
  const requestGenerationRef = useRef(0)
  const lastRequestRef = useRef(requestFromResponse(initialGuestResponse))
  const mountedRef = useRef(true)
  const guestHydratedRef = useRef(authStatus === 'anonymous')
  const hasInteractedRef = useRef(false)

  useEffect(() => () => {
    mountedRef.current = false
    requestGenerationRef.current += 1
    activeControllerRef.current?.abort()
  }, [])

  useEffect(() => {
    if (authStatus !== 'anonymous' || guestHydratedRef.current) return
    guestHydratedRef.current = true
    if (hasInteractedRef.current || pageState !== 'empty' || activeResponse) return
    const restored = loadGuestResearchSession()
    const restoredResponse = restored.activeNodeId
      ? restored.nodes.find((node) => node.id === restored.activeNodeId)?.response ?? null
      : null
    setGuestSession(restored)
    setSettings(cloneSettings(restoredResponse?.settings ?? restored.settings))
    if (!restoredResponse) return
    setQuestion(restoredResponse.query)
    setMode(restoredResponse.mode)
    setActiveResponse(restoredResponse)
    setPageState(restoredResponse.groundingStatus === 'insufficient' ? 'insufficient'
      : restoredResponse.groundingStatus === 'evidence-only' ? 'evidence-only' : 'success')
    lastRequestRef.current = requestFromResponse(restoredResponse)
  }, [activeResponse, authStatus, pageState])

  const storeGuestResponse = useCallback((response, localParentNodeId, requestSettings) => {
    const id = response.trailNode?.id ?? response.id
    setGuestSession((current) => {
      const withoutSameNode = current.nodes.filter((node) => node.id !== id)
      const next = {
        nodes: [...withoutSameNode, { id, parentNodeId: localParentNodeId ?? null, response }].slice(-64),
        activeNodeId: id,
        settings: cloneSettings(requestSettings),
      }
      saveGuestResearchSession(next)
      return next
    })
  }, [])

  const executeResearch = useCallback(async (requestInput) => {
    if (pageState === 'loading') return
    hasInteractedRef.current = true
    activeControllerRef.current?.abort()
    const controller = new AbortController()
    activeControllerRef.current = controller
    const generation = ++requestGenerationRef.current
    const localParentNodeId = authStatus === 'anonymous' ? guestSession.activeNodeId : null
    const normalizedRequest = {
      question: requestInput.question.trim(),
      sourceScopes: [...requestInput.sourceScopes],
      depth: requestInput.depth,
      mode: requestInput.mode,
      modeParameters: { ...(requestInput.modeParameters ?? {}) },
      ...(authStatus === 'authenticated' && requestInput.parentNodeId
        ? { parentNodeId: requestInput.parentNodeId }
        : {}),
      ...(requestInput.conversationContext
        ? { conversationContext: {
          entityNames: [...requestInput.conversationContext.entityNames],
          sourceReferences: [...requestInput.conversationContext.sourceReferences],
        } }
        : {}),
    }
    lastRequestRef.current = normalizedRequest
    setQuestion(normalizedRequest.question)
    setSettings(cloneSettings(normalizedRequest))
    setMode(normalizedRequest.mode)
    setErrorMessage('')
    setStatusMessage('')
    setPageState('loading')

    try {
      const response = await runResearch(normalizedRequest, { signal: controller.signal })
      if (!mountedRef.current || generation !== requestGenerationRef.current || controller.signal.aborted) return
      setActiveResponse(response)
      setStudyId(null)
      if (response.groundingStatus === 'insufficient') setPageState('insufficient')
      else if (response.groundingStatus === 'evidence-only') setPageState('evidence-only')
      else setPageState('success')
      if (authStatus === 'anonymous') storeGuestResponse(response, localParentNodeId, normalizedRequest)
      else if (authStatus === 'authenticated') {
        const id = response.trailNode?.id ?? response.id
        setAuthenticatedSession((current) => ({
          nodes: [
            ...current.nodes.filter((node) => node.id !== id),
            { id, parentNodeId: normalizedRequest.parentNodeId ?? null, response },
          ].slice(-64),
          activeNodeId: id,
          settings: cloneSettings(normalizedRequest),
        }))
      }
    } catch (error) {
      if (abortError(error) || controller.signal.aborted || generation !== requestGenerationRef.current) return
      setErrorMessage(error?.message || 'The research service could not complete this request.')
      setPageState('error')
    }
  }, [authStatus, guestSession.activeNodeId, pageState, storeGuestResponse])

  const submitComposer = useCallback((input) => executeResearch(input), [executeResearch])
  const submitExample = useCallback((exampleQuestion, exampleSettings, exampleMode) => {
    executeResearch({
      question: exampleQuestion,
      sourceScopes: exampleSettings.sourceScopes,
      depth: exampleSettings.depth,
      mode: exampleMode,
      modeParameters: exampleSettings.modeParameters,
    })
  }, [executeResearch])
  const retry = useCallback(() => {
    if (lastRequestRef.current) executeResearch(lastRequestRef.current)
  }, [executeResearch])

  const followUp = useCallback((followUpQuestion) => {
    if (!activeResponse) return
    const guestContext = authStatus === 'anonymous'
      ? compactConversationContext(activeResponse)
      : null
    executeResearch({
      question: followUpQuestion,
      sourceScopes: activeResponse.settings.sourceScopes,
      depth: activeResponse.settings.depth,
      mode: activeResponse.mode,
      modeParameters: activeResponse.settings.modeParameters,
      ...(authStatus === 'authenticated' && activeResponse.trailNode?.id
        ? { parentNodeId: activeResponse.trailNode.id }
        : {}),
      ...(guestContext ? { conversationContext: guestContext } : {}),
    })
  }, [activeResponse, authStatus, executeResearch])

  const persistResearch = useCallback(async () => {
    if (!activeResponse) return null
    if (studyId) return studyId
    const title = `Scripture Research: ${activeResponse.query.slice(0, 80)}`
    const study = await api.post('/studies', { title })
    await api.post(`/studies/${study.id}/messages`, { role: 'user', content: activeResponse.query })
    await api.post(`/studies/${study.id}/messages`, { role: 'assistant', content: resultText(activeResponse) })
    for (const source of activeResponse.sources) {
      await api.post(`/studies/${study.id}/sources`, {
        title: source.title,
        url: source.openTarget || null,
        citation: source.reference,
      })
    }
    setStudyId(study.id)
    return study.id
  }, [activeResponse, studyId])

  const saveResearch = useCallback(async () => {
    if (!activeResponse) return
    if (authStatus !== 'authenticated') {
      const now = new Date()
      const localStudy = {
        id: `research-${now.getTime()}-${Math.random().toString(16).slice(2)}`,
        title: `Scripture Research: ${activeResponse.query.slice(0, 80)}`,
        type: 'scripture-research',
        date: now.toLocaleDateString(),
        timestamp: now.toISOString(),
        question: activeResponse.query,
        result: resultText(activeResponse),
        sources: activeResponse.sources.map((source) => ({
          id: source.id,
          title: source.title,
          reference: source.reference,
          openTarget: source.openTarget,
        })),
        messages: [
          { type: 'user', content: activeResponse.query },
          { type: 'ai', content: resultText(activeResponse) },
        ],
      }
      localStorage.setItem(
        'unbound_saved_studies',
        JSON.stringify([...readLocalStudies(), localStudy]),
      )
      setStatusMessage('Research saved to My Library on this device.')
      return
    }
    try {
      await persistResearch()
      setStatusMessage('Research saved privately to My Library.')
    } catch (error) {
      setStatusMessage(`Research could not be saved: ${error.message}`)
    }
  }, [activeResponse, authStatus, persistResearch])

  const shareResearch = useCallback(async () => {
    if (!activeResponse) return
    let persistedId = studyId
    if (authStatus === 'authenticated' && !persistedId) {
      try { persistedId = await persistResearch() }
      catch (error) {
        setStatusMessage(`Research could not be prepared for sharing: ${error.message}`)
        return
      }
    }
    setShareData({
      studyId: persistedId,
      title: activeResponse.query,
      type: 'Scripture Research AI',
      verses: activeResponse.sources.map((source) => source.reference),
      content: resultText(activeResponse),
    })
    setShareOpen(true)
  }, [activeResponse, authStatus, persistResearch, studyId])

  const newResearch = useCallback(() => {
    hasInteractedRef.current = true
    activeControllerRef.current?.abort()
    requestGenerationRef.current += 1
    setQuestion('')
    setSettings(cloneSettings())
    setMode(DEFAULT_RESEARCH_MODE)
    setPageState('empty')
    setActiveResponse(null)
    setGuestSession(createEmptyResearchSession())
    setAuthenticatedSession(createEmptyResearchSession())
    setErrorMessage('')
    setStatusMessage('')
    setStudyId(null)
    setShareOpen(false)
    lastRequestRef.current = null
    if (authStatus === 'anonymous') clearGuestResearchSession()
  }, [authStatus])

  const activeSession = authStatus === 'authenticated' ? authenticatedSession : guestSession
  const activeTrail = useMemo(() => {
    if (!activeSession.activeNodeId) return null
    const lookup = new Map(activeSession.nodes.map((node) => [node.id, node]))
    const activeStored = lookup.get(activeSession.activeNodeId)
    if (!activeStored) return null
    const ancestry = []
    let current = activeStored
    while (current) {
      ancestry.unshift({
        id: current.id,
        parentNodeId: current.parentNodeId,
        question: current.response.query,
        label: current.response.trailNode?.label ?? null,
      })
      current = current.parentNodeId ? lookup.get(current.parentNodeId) : null
    }
    const active = ancestry.at(-1)
    const children = activeSession.nodes.filter((node) => node.parentNodeId === active.id).map((node) => ({
      id: node.id, parentNodeId: node.parentNodeId, question: node.response.query, label: node.response.trailNode?.label ?? null,
    }))
    return { ancestry, active, children, childrenTruncated: false }
  }, [activeSession])

  const selectTrailNode = useCallback((node) => {
    const session = authStatus === 'authenticated' ? authenticatedSession : guestSession
    const stored = session.nodes.find((item) => item.id === node.id)
    if (!stored) return
    if (authStatus === 'authenticated') {
      setAuthenticatedSession((current) => ({ ...current, activeNodeId: node.id, settings: cloneSettings(stored.response.settings) }))
    } else {
      setGuestSession((current) => {
        const next = { ...current, activeNodeId: node.id, settings: cloneSettings(stored.response.settings) }
        saveGuestResearchSession(next)
        return next
      })
    }
    setActiveResponse(stored.response)
    setQuestion(stored.response.query)
    setSettings(cloneSettings(stored.response.settings))
    setMode(stored.response.mode)
    setPageState(stored.response.groundingStatus === 'insufficient' ? 'insufficient'
      : stored.response.groundingStatus === 'evidence-only' ? 'evidence-only' : 'success')
  }, [authStatus, authenticatedSession, guestSession])

  const openTarget = useCallback((target) => {
    if (!target) return
    const nextHash = readerHashFromOpenTarget(target)
    if (!nextHash) return
    onPageChange?.('apocrypha')
    if (window.location.hash !== nextHash) window.location.hash = nextHash
  }, [onPageChange])

  const completionAnnouncement = pageState === 'success'
    ? 'Grounded research is ready.'
    : pageState === 'insufficient'
      ? 'Research completed with insufficient verified evidence.'
      : pageState === 'evidence-only'
        ? 'Verified evidence is ready without AI synthesis.'
        : ''

  const actionBar = activeResponse ? (
    <>
      <button type="button" onClick={saveResearch}>Save research</button>
      <button type="button" onClick={shareResearch}>Share research</button>
      <button type="button" onClick={newResearch}>New Research</button>
    </>
  ) : null

  return (
    <div className="scripture-research-page">
      <header className="scripture-research-page__header">
        <h1>Scripture Research AI <span aria-hidden="true">✦</span></h1>
        <p>Ask any question to understand scripture, ancient texts, biblical history, and original languages.</p>
      </header>

      <ResearchComposer
        value={question}
        onChange={(value) => { hasInteractedRef.current = true; setQuestion(value) }}
        settings={settings}
        onSettingsChange={(value) => { hasInteractedRef.current = true; setSettings(value) }}
        mode={mode}
        onModeChange={(value) => { hasInteractedRef.current = true; setMode(value) }}
        onSubmit={submitComposer}
        loading={pageState === 'loading'}
        searchEvents={searchResearchEvents}
        onExample={submitExample}
      />

      {pageState === 'loading' && <ResearchLoadingState mode={lastRequestRef.current?.mode ?? mode} />}
      {pageState === 'error' && (
        <section className="research-error">
          <h2>Research could not be completed</h2>
          <p role="alert">{errorMessage}</p>
          <button type="button" onClick={retry}>Retry research</button>
        </section>
      )}
      <ResultNotice state={pageState} response={activeResponse} onRetry={retry} />

      {activeResponse && pageState !== 'loading' && pageState !== 'error' && (
        <>
          {activeTrail && <ResearchTrail trail={activeTrail} onSelectNode={selectTrailNode} />}
          <ResearchWorkspace
            response={activeResponse}
            onRelatedQuestion={followUp}
            onEventResearch={followUp}
            onPersonResearch={(person) => followUp(`Research ${person.name}`)}
            onPlaceResearch={(place) => followUp(`Research ${place.name}`)}
            onOpenTarget={openTarget}
            actionBar={actionBar}
            continueResearch={activeResponse.relatedQuestions}
          />
        </>
      )}

      {(statusMessage || completionAnnouncement) && (
        <p role="status" aria-live="polite" aria-atomic="true">
          {statusMessage || completionAnnouncement}
        </p>
      )}
      <ShareStudyModal isOpen={shareOpen} onClose={() => setShareOpen(false)} shareData={shareData} />
    </div>
  )
}
