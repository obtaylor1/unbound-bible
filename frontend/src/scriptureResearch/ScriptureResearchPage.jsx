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
import './ScriptureResearchPage.css'

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

const createPersistenceState = (responseId = null, principalKey = null) => ({
  responseId,
  principalKey,
  studyId: null,
  inFlight: null,
  completed: new Set(),
})

const invalidatedPersistenceError = () => Object.assign(
  new Error('The signed-in research session changed.'),
  { name: 'AbortError' },
)

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

const mergedGuestNodes = (...collections) => {
  const byId = new Map()
  collections.flat().forEach((node) => {
    byId.delete(node.id)
    byId.set(node.id, { ...node })
  })
  const nodes = [...byId.values()].slice(-64)
  const retainedIds = new Set(nodes.map((node) => node.id))
  nodes.forEach((node, index) => {
    if (
      node.parentNodeId === node.id
      || (node.parentNodeId && !retainedIds.has(node.parentNodeId))
    ) nodes[index] = { ...node, parentNodeId: null }
  })

  const lookup = new Map(nodes.map((node) => [node.id, node]))
  nodes.forEach((node, index) => {
    const seen = new Set([node.id])
    let parentNodeId = node.parentNodeId
    while (parentNodeId) {
      if (seen.has(parentNodeId)) {
        const detached = { ...node, parentNodeId: null }
        nodes[index] = detached
        lookup.set(detached.id, detached)
        break
      }
      seen.add(parentNodeId)
      parentNodeId = lookup.get(parentNodeId)?.parentNodeId ?? null
    }
  })
  return nodes
}

const readerHashFromOpenTarget = (target, source) => {
  if (target.startsWith('#scriptures')) {
    const params = new URLSearchParams(target.split('?')[1] ?? '')
    if (params.has('translation') || !source?.translation) return target
    return readerHash({ ...parseReaderHash(target), translation: source.translation })
  }
  const current = parseReaderHash()
  const [apiPath, apiQuery = ''] = target.split('?')
  const apiMatch = /^\/api\/v1\/texts\/([^/]+)\/(\d+)\/(\d+)\/details$/.exec(apiPath)
  if (apiMatch) {
    const targetTranslation = new URLSearchParams(apiQuery).get('translation')
    return readerHash({
      ...current,
      book: decodeURIComponent(apiMatch[1]),
      chapter: Number(apiMatch[2]),
      verse: Number(apiMatch[3]),
      translation: targetTranslation || source?.translation || current.translation,
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
        translation: parsed.searchParams.get('translation') || source?.translation || current.translation,
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
  const { status: authStatus, user: authUser } = useAuth()
  const principalKey = authStatus === 'authenticated'
    ? `user:${authUser?.id ?? 'unknown'}`
    : authStatus === 'anonymous' ? 'guest' : 'loading'
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
  const [persistenceBusy, setPersistenceBusy] = useState(false)
  const activeControllerRef = useRef(null)
  const requestGenerationRef = useRef(0)
  const lastRequestRef = useRef(requestFromResponse(initialGuestResponse))
  const mountedRef = useRef(true)
  const guestHydratedRef = useRef(authStatus === 'anonymous')
  const hasInteractedRef = useRef(false)
  const authStatusRef = useRef(authStatus)
  const principalRef = useRef(principalKey)
  const settledPrincipalRef = useRef(principalKey === 'loading' ? null : principalKey)
  const activeResponseRef = useRef(activeResponse)
  const persistenceRef = useRef(createPersistenceState())
  authStatusRef.current = authStatus
  principalRef.current = principalKey
  activeResponseRef.current = activeResponse

  const resetPersistence = useCallback(() => {
    persistenceRef.current = createPersistenceState()
    setPersistenceBusy(false)
    setStudyId(null)
  }, [])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      requestGenerationRef.current += 1
      activeControllerRef.current?.abort()
      persistenceRef.current = createPersistenceState()
    }
  }, [])

  useEffect(() => {
    if (principalKey === 'loading') return
    const previousPrincipal = settledPrincipalRef.current
    settledPrincipalRef.current = principalKey
    if (previousPrincipal === null || previousPrincipal === principalKey) return
    const interruptedGuestRequest = previousPrincipal === 'guest'
      && principalKey.startsWith('user:')
      && pageState === 'loading'

    activeControllerRef.current?.abort()
    requestGenerationRef.current += 1
    resetPersistence()
    setShareOpen(false)
    setShareData(null)
    setErrorMessage('')
    setStatusMessage('')
    if (!interruptedGuestRequest) lastRequestRef.current = null

    if (principalKey === 'guest') {
      const restored = loadGuestResearchSession()
      const restoredResponse = restored.activeNodeId
        ? restored.nodes.find((node) => node.id === restored.activeNodeId)?.response ?? null
        : null
      guestHydratedRef.current = true
      setGuestSession(restored)
      setAuthenticatedSession(createEmptyResearchSession())
      setActiveResponse(restoredResponse)
      setQuestion(restoredResponse?.query ?? '')
      setSettings(cloneSettings(restoredResponse?.settings ?? restored.settings))
      setMode(restoredResponse?.mode ?? DEFAULT_RESEARCH_MODE)
      setPageState(restoredResponse
        ? restoredResponse.groundingStatus === 'insufficient' ? 'insufficient'
          : restoredResponse.groundingStatus === 'evidence-only' ? 'evidence-only' : 'success'
        : 'empty')
      lastRequestRef.current = requestFromResponse(restoredResponse)
      return
    }

    if (previousPrincipal === 'guest') {
      setAuthenticatedSession({
        nodes: guestSession.nodes,
        activeNodeId: guestSession.activeNodeId,
        settings: cloneSettings(guestSession.settings),
      })
      if (interruptedGuestRequest) {
        setErrorMessage('Your sign-in changed while research was running. Retry research to continue securely with this account.')
        setPageState('error')
      }
      return
    }

    setAuthenticatedSession(createEmptyResearchSession())
    setActiveResponse(null)
    setQuestion('')
    setSettings(cloneSettings())
    setMode(DEFAULT_RESEARCH_MODE)
    setPageState('empty')
  }, [guestSession, pageState, principalKey, resetPersistence])

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

  useEffect(() => {
    if (
      authStatus !== 'authenticated'
      || authenticatedSession.activeNodeId
      || !guestSession.activeNodeId
    ) return
    setAuthenticatedSession({
      nodes: guestSession.nodes,
      activeNodeId: guestSession.activeNodeId,
      settings: cloneSettings(guestSession.settings),
    })
  }, [authStatus, authenticatedSession.activeNodeId, guestSession])

  const storeGuestResponse = useCallback((response, localParentNodeId, requestSettings) => {
    const id = response.trailNode?.id ?? response.id
    setGuestSession((current) => {
      const latest = loadGuestResearchSession()
      const candidateParentId = localParentNodeId
        ?? current.activeNodeId
        ?? latest.activeNodeId
      const parentNodeId = candidateParentId && candidateParentId !== id
        ? candidateParentId
        : null
      const nodes = mergedGuestNodes(
        latest.nodes,
        current.nodes,
        [{ id, parentNodeId, response }],
      )
      const next = {
        nodes,
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
    const requestAuthStatus = authStatusRef.current
    const requestPrincipalKey = principalRef.current
    const localParentNodeId = requestAuthStatus === 'anonymous' ? guestSession.activeNodeId : null
    const normalizeRequest = (input) => ({
      question: input.question.trim(),
      sourceScopes: [...input.sourceScopes],
      depth: input.depth,
      mode: input.mode,
      modeParameters: { ...(input.modeParameters ?? {}) },
      ...(requestAuthStatus === 'authenticated' && input.parentNodeId
        ? { parentNodeId: input.parentNodeId }
        : {}),
      ...(requestAuthStatus !== 'authenticated' && input.conversationContext
        ? { conversationContext: {
          entityNames: [...input.conversationContext.entityNames],
          sourceReferences: [...input.conversationContext.sourceReferences],
        } }
        : {}),
    })
    const normalizedRequest = normalizeRequest(requestInput)
    const retryParentIntent = requestInput.revalidateParent
      ? {
        request: normalizeRequest(requestInput.revalidateParent),
        localNodeId: requestInput.revalidateParent.localNodeId,
      }
      : null
    const parentRevalidation = requestAuthStatus === 'authenticated'
      ? retryParentIntent
      : null
    lastRequestRef.current = retryParentIntent
      ? {
        ...normalizedRequest,
        revalidateParent: {
          ...retryParentIntent.request,
          localNodeId: retryParentIntent.localNodeId,
        },
      }
      : normalizedRequest
    setQuestion(normalizedRequest.question)
    setSettings(cloneSettings(normalizedRequest))
    setMode(normalizedRequest.mode)
    setErrorMessage('')
    setStatusMessage('')
    setPageState('loading')

    let requestPhase = parentRevalidation ? 'parent-revalidation' : 'research'
    try {
      const requestIsCurrent = () => (
        mountedRef.current
        && generation === requestGenerationRef.current
        && !controller.signal.aborted
        && (requestPrincipalKey === 'loading' || principalRef.current === requestPrincipalKey)
      )
      let authoritativeParent = null
      let effectiveRequest = normalizedRequest
      if (parentRevalidation) {
        authoritativeParent = await runResearch(parentRevalidation.request, { signal: controller.signal })
        if (!requestIsCurrent()) return
        const authoritativeParentId = authoritativeParent.trailNode?.id
        if (!authoritativeParentId) {
          throw new Error('The prior research could not be securely revalidated. Retry research to continue.')
        }
        if (['insufficient', 'evidence-only'].includes(authoritativeParent.groundingStatus)) {
          setErrorMessage('The prior research could not be revalidated with enough grounded evidence. Retry research to try this follow-up again.')
          setPageState('error')
          return
        }
        effectiveRequest = {
          ...normalizedRequest,
          parentNodeId: authoritativeParentId,
        }
        lastRequestRef.current = effectiveRequest
        setAuthenticatedSession((current) => ({
          nodes: [
            ...current.nodes.filter((node) => ![
              parentRevalidation.localNodeId,
              authoritativeParentId,
            ].includes(node.id)),
            {
              id: authoritativeParentId,
              parentNodeId: null,
              response: authoritativeParent,
            },
          ].slice(-64),
          activeNodeId: authoritativeParentId,
          settings: cloneSettings(authoritativeParent.settings),
        }))
        requestPhase = 'child-research'
      }

      const response = await runResearch(effectiveRequest, { signal: controller.signal })
      if (!requestIsCurrent()) return
      const serverPersisted = requestAuthStatus === 'authenticated' && Boolean(response.trailNode?.id)
      const retainedResponse = serverPersisted || !response.trailNode
        ? response
        : { ...response, trailNode: null }
      const completionAuthStatus = authStatusRef.current
      resetPersistence()
      setActiveResponse(retainedResponse)
      if (response.groundingStatus === 'insufficient') setPageState('insufficient')
      else if (response.groundingStatus === 'evidence-only') setPageState('evidence-only')
      else setPageState('success')
      if (completionAuthStatus === 'authenticated') {
        const id = retainedResponse.trailNode?.id ?? retainedResponse.id
        const authoritativeParentId = authoritativeParent?.trailNode?.id ?? null
        const replacedIds = new Set([
          id,
          authoritativeParentId,
          parentRevalidation?.localNodeId,
        ].filter(Boolean))
        setAuthenticatedSession((current) => ({
          nodes: [
            ...current.nodes.filter((node) => !replacedIds.has(node.id)),
            ...(authoritativeParent ? [{
              id: authoritativeParentId,
              parentNodeId: null,
              response: authoritativeParent,
            }] : []),
            {
              id,
              parentNodeId: serverPersisted ? effectiveRequest.parentNodeId ?? null : null,
              response: retainedResponse,
            },
          ].slice(-64),
          activeNodeId: id,
          settings: cloneSettings(normalizedRequest),
        }))
      } else storeGuestResponse(retainedResponse, localParentNodeId, normalizedRequest)
    } catch (error) {
      if (
        abortError(error)
        || controller.signal.aborted
        || generation !== requestGenerationRef.current
        || (requestPrincipalKey !== 'loading' && principalRef.current !== requestPrincipalKey)
      ) return
      setErrorMessage(requestPhase === 'parent-revalidation'
        ? `The prior research could not be revalidated right now. ${error?.message || 'Retry research to try this follow-up again.'}`
        : error?.message || 'The research service could not complete this request.')
      setPageState('error')
    }
  }, [guestSession.activeNodeId, pageState, resetPersistence, storeGuestResponse])

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
    const parentNodeId = authStatus === 'authenticated'
      ? activeResponse.trailNode?.id
      : null
    const localContext = authStatus !== 'authenticated' && !parentNodeId
      ? compactConversationContext(activeResponse)
      : null
    executeResearch({
      question: followUpQuestion,
      sourceScopes: activeResponse.settings.sourceScopes,
      depth: activeResponse.settings.depth,
      mode: activeResponse.mode,
      modeParameters: activeResponse.settings.modeParameters,
      ...(parentNodeId
        ? { parentNodeId }
        : {}),
      ...(!parentNodeId ? {
        revalidateParent: {
          ...requestFromResponse(activeResponse),
          localNodeId: activeResponse.trailNode?.id ?? activeResponse.id,
        },
      } : {}),
      ...(localContext ? { conversationContext: localContext } : {}),
    })
  }, [activeResponse, authStatus, executeResearch])

  const persistResearch = useCallback(async () => {
    if (!activeResponse || authStatus !== 'authenticated') return null
    const response = activeResponse
    const responseId = response.trailNode?.id ?? response.id
    const requestPrincipalKey = principalRef.current
    let state = persistenceRef.current
    if (state.responseId !== responseId || state.principalKey !== requestPrincipalKey) {
      state = createPersistenceState(responseId, requestPrincipalKey)
      persistenceRef.current = state
      setStudyId(null)
    }
    if (state.inFlight) return state.inFlight

    const assertCurrent = () => {
      const currentResponse = activeResponseRef.current
      const currentResponseId = currentResponse?.trailNode?.id ?? currentResponse?.id
      if (
        persistenceRef.current !== state
        || principalRef.current !== requestPrincipalKey
        || currentResponseId !== responseId
      ) throw invalidatedPersistenceError()
    }
    const writeOnce = async (key, url, payload) => {
      if (state.completed.has(key)) return
      assertCurrent()
      await api.post(url, payload)
      assertCurrent()
      state.completed.add(key)
    }

    const operation = (async () => {
      if (!state.studyId) {
        const title = `Scripture Research: ${response.query.slice(0, 80)}`
        const study = await api.post('/studies', { title })
        assertCurrent()
        state.studyId = study.id
        setStudyId(study.id)
      }
      const baseUrl = `/studies/${state.studyId}`
      await writeOnce('message:user', `${baseUrl}/messages`, { role: 'user', content: response.query })
      await writeOnce('message:assistant', `${baseUrl}/messages`, { role: 'assistant', content: resultText(response) })
      for (const [index, source] of response.sources.entries()) {
        await writeOnce(`source:${source.id ?? index}`, `${baseUrl}/sources`, {
          title: source.title,
          url: source.openTarget || null,
          citation: source.reference,
        })
      }
      return state.studyId
    })()

    state.inFlight = operation
    setPersistenceBusy(true)
    try {
      return await operation
    } finally {
      if (persistenceRef.current === state) {
        state.inFlight = null
        setPersistenceBusy(false)
      }
    }
  }, [activeResponse, authStatus])

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
    const requestPrincipalKey = principalRef.current
    try {
      await persistResearch()
      if (principalRef.current !== requestPrincipalKey) return
      setStatusMessage('Research saved privately to My Library.')
    } catch (error) {
      if (abortError(error) || principalRef.current !== requestPrincipalKey) return
      setStatusMessage(`Research could not be saved: ${error.message}`)
    }
  }, [activeResponse, authStatus, persistResearch])

  const shareResearch = useCallback(async () => {
    if (!activeResponse) return
    if (authStatus !== 'authenticated') {
      setShareOpen(false)
      setShareData(null)
      setStatusMessage('Sign in using the Sign in button in the top navigation to share this research.')
      return
    }
    const requestPrincipalKey = principalRef.current
    let persistedId = studyId
    if (!persistedId) {
      try { persistedId = await persistResearch() }
      catch (error) {
        if (abortError(error) || principalRef.current !== requestPrincipalKey) return
        setStatusMessage(`Research could not be prepared for sharing: ${error.message}`)
        return
      }
    }
    if (principalRef.current !== requestPrincipalKey) return
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
    resetPersistence()
    setShareOpen(false)
    setShareData(null)
    lastRequestRef.current = null
    if (authStatus === 'anonymous') clearGuestResearchSession()
  }, [authStatus, resetPersistence])

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
    resetPersistence()
    setQuestion(stored.response.query)
    setSettings(cloneSettings(stored.response.settings))
    setMode(stored.response.mode)
    setPageState(stored.response.groundingStatus === 'insufficient' ? 'insufficient'
      : stored.response.groundingStatus === 'evidence-only' ? 'evidence-only' : 'success')
  }, [authStatus, authenticatedSession, guestSession, resetPersistence])

  const openTarget = useCallback((target, source) => {
    if (!target) return
    const nextHash = readerHashFromOpenTarget(target, source)
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
      <button type="button" onClick={saveResearch} disabled={persistenceBusy}>Save research</button>
      <button type="button" onClick={shareResearch} disabled={persistenceBusy}>Share research</button>
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
