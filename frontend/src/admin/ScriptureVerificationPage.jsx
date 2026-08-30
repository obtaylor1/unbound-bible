import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import AuthDialog from '../auth/AuthDialog'
import { useAuth } from '../auth/authContext'
import {
  formatVerifiedDate,
  isVerifiedSourceStatus,
  SOURCE_VERIFICATION_LABELS,
} from '../reader/sourceVerification'
import { fetchScriptureVerificationInventory } from './scriptureVerificationApi'
import './ScriptureVerificationPage.css'

const VERIFICATION_FAMILIES = Object.freeze([
  {
    id: 'world-messianic-bible',
    title: 'World Messianic Bible',
    description: 'Hebrew-source Old Testament works compared with the official edition.',
    includes: (work) => work.groupId === 'world-messianic-bible',
    affected: true,
  },
  {
    id: 'murdock-peshitta-1852',
    title: 'Murdock Peshitta',
    description: 'Syriac-source New Testament works compared for edition and transcription accuracy.',
    includes: (work) => work.groupId === 'murdock-peshitta-1852',
    affected: true,
  },
  {
    id: 'kjv-1611-fallback',
    title: 'KJV fallback works',
    description: 'Public-domain fallback works. The fallback label remains after source verification.',
    includes: (work) => work.groupId === 'kjv-1611-fallback',
    affected: true,
  },
  {
    id: 'rh-charles-jubilees-1902',
    title: 'R. H. Charles Jubilees',
    description: 'Jubilees is compared with the reviewed 1902 historical edition.',
    includes: (work) => work.groupId === 'rh-charles-jubilees-1902',
    affected: true,
  },
  {
    id: 'already-provenanced',
    title: 'Already-provenanced works',
    description: 'Supplied works with separately documented public source histories.',
    includes: (work) => work.groupId === 'already-provenanced',
    affected: false,
  },
])

const STATUS_OPTIONS = Object.entries(SOURCE_VERIFICATION_LABELS)

function familyFor(work) {
  return VERIFICATION_FAMILIES.find((family) => family.includes(work)) ?? null
}

function pluralWorks(count) {
  return `${count} ${count === 1 ? 'work' : 'works'}`
}

function familyVerificationSummary(works) {
  const verified = works.filter((work) => isVerifiedSourceStatus(work.status)).length
  const reviewRequired = works.filter((work) => work.status === 'review_required').length
  if (verified === works.length) {
    return {
      badge: `${verified} of ${works.length} verified`,
      kicker: 'Source verification complete for this family',
    }
  }
  if (verified > 0) {
    return {
      badge: `${verified} of ${works.length} verified`,
      kicker: reviewRequired > 0
        ? `${reviewRequired} source ${reviewRequired === 1 ? 'review requires' : 'reviews require'} attention`
        : 'Source verification in progress',
    }
  }
  return {
    badge: 'Awaiting review',
    kicker: reviewRequired > 0
      ? `${reviewRequired} source ${reviewRequired === 1 ? 'review requires' : 'reviews require'} attention`
      : 'Awaiting source review',
  }
}

function Evidence({ work }) {
  const [open, setOpen] = useState(false)
  const comparisonTotal = Object.values(work.comparison).reduce((sum, value) => sum + value, 0)
  const hasEvidence = Boolean(
    work.provenanceUrl
    || work.rightsUrl
    || work.artifactSha256
    || work.comparisonReportSha256
    || work.reviewer
    || work.reviewedAt
    || comparisonTotal,
  )

  if (!hasEvidence) return <span className="verification-pending">Evidence pending</span>

  return (
    <details className="verification-evidence" open={open}>
      <summary
        aria-expanded={open}
        onClick={(event) => { event.preventDefault(); setOpen((value) => !value) }}
        onKeyDown={(event) => {
          if (!['Enter', ' '].includes(event.key)) return
          event.preventDefault()
          setOpen((value) => !value)
        }}
      >Review evidence</summary>
      <div className="verification-evidence__body">
        {(work.provenanceUrl || work.rightsUrl) && (
          <div className="verification-evidence__links">
            {work.provenanceUrl && <a href={work.provenanceUrl} target="_blank" rel="noreferrer">Source record</a>}
            {work.rightsUrl && <a href={work.rightsUrl} target="_blank" rel="noreferrer">Rights record</a>}
          </div>
        )}
        <dl className="verification-evidence__facts">
          <div><dt>Artifact checksum</dt><dd>{work.artifactSha256 ? <code>{work.artifactSha256}</code> : 'Pending'}</dd></div>
          <div><dt>Report checksum</dt><dd>{work.comparisonReportSha256 ? <code>{work.comparisonReportSha256}</code> : 'Pending'}</dd></div>
          <div><dt>Reviewer</dt><dd>{work.reviewer ?? 'Pending'}</dd></div>
          <div><dt>Review date</dt><dd>{formatVerifiedDate(work.reviewedAt) ?? 'Pending'}</dd></div>
        </dl>
        <div className="verification-comparison" aria-label="Comparison totals">
          <span><strong>{work.comparison.exact}</strong> exact</span>
          <span><strong>{work.comparison.formatting}</strong> formatting</span>
          <span><strong>{work.comparison.wording}</strong> wording</span>
          <span><strong>{work.comparison.missing}</strong> missing</span>
          <span><strong>{work.comparison.extra}</strong> extra</span>
        </div>
      </div>
    </details>
  )
}

function WorkTable({ family, familyWorks, works }) {
  const summary = familyVerificationSummary(familyWorks)
  return (
    <section className={`verification-family verification-family--${family.affected ? 'active' : 'documented'}`} aria-labelledby={`${family.id}-title`}>
      <header className="verification-family__header">
        <div>
          <p className="verification-family__kicker">{summary.kicker}</p>
          <h2 id={`${family.id}-title`}>{family.title}</h2>
          <p>{family.description}</p>
        </div>
        <div className="verification-family__summary">
          <span className="verification-family__size">{pluralWorks(familyWorks.length)}</span>
          <span className="verification-family__count" aria-label={`Family status: ${summary.badge}`}>{summary.badge}</span>
        </div>
      </header>
      <div className="verification-table-wrap">
        <table>
          <caption className="sr-only">{family.title} source verification inventory</caption>
          <thead>
            <tr><th scope="col">Work</th><th scope="col">Verification</th><th scope="col">Source</th><th scope="col">Evidence</th></tr>
          </thead>
          <tbody>
            {works.map((work) => (
              <tr key={work.workId}>
                <th scope="row" data-label="Work">
                  <span className="verification-work__name">{work.workName}</span>
                  <span className="verification-work__id">{work.workId}</span>
                </th>
                <td data-label="Verification">
                  <span className={`verification-status verification-status--${work.status}`}>
                    <span aria-hidden="true" className="verification-status__mark">{isVerifiedSourceStatus(work.status) ? '✓' : work.status === 'review_required' ? '!' : '…'}</span>
                    {work.statusLabel}
                  </span>
                  {work.fallback && <span className="verification-fallback">KJV fallback</span>}
                </td>
                <td data-label="Source">
                  <strong>{work.sourceLabel}</strong>
                  {(work.sourceEdition || work.sourceRevision) && <span>{[work.sourceEdition, work.sourceRevision].filter(Boolean).join(' · ')}</span>}
                  <span>{work.license}</span>
                </td>
                <td data-label="Evidence"><Evidence work={work} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function AccessState({ kind, onRetry, onSignIn }) {
  const content = {
    unauthorized: {
      heading: 'Sign in to review sources',
      message: 'This evidence inventory is available to an authenticated administrator.',
    },
    forbidden: {
      heading: 'Administrator access required',
      message: 'Your account does not have permission to open the source verification inventory.',
    },
    error: {
      heading: 'Verification inventory unavailable',
      message: 'The verification inventory is temporarily unavailable. Your scripture collection has not been changed.',
    },
    integrity: {
      heading: 'Inventory integrity check failed',
      message: 'The response could not be matched to the approved 83-work source contract. No inventory totals or verification claims are being presented.',
    },
  }[kind]
  return (
    <section className="verification-state" role={['error', 'integrity'].includes(kind) ? 'alert' : undefined}>
      <span className="verification-state__icon" aria-hidden="true">{['error', 'integrity'].includes(kind) ? '!' : '⌾'}</span>
      <h1>{content.heading}</h1>
      <p>{content.message}</p>
      {kind === 'unauthorized' && <button className="verification-button" type="button" onClick={onSignIn}>Sign in</button>}
      {['error', 'integrity'].includes(kind) && <button className="verification-button" type="button" onClick={onRetry}>Try again</button>}
    </section>
  )
}

export default function ScriptureVerificationPage() {
  const { status: authStatus, user: authUser } = useAuth()
  const [request, setRequest] = useState({ state: 'loading', inventory: null })
  const [retryKey, setRetryKey] = useState(0)
  const [statusFilter, setStatusFilter] = useState('all')
  const [familyFilter, setFamilyFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [authOpen, setAuthOpen] = useState(false)
  const authSnapshot = `${authStatus}:${authUser?.id ?? ''}`
  const authSnapshotRef = useRef(authSnapshot)
  const unauthorizedAuthSnapshotRef = useRef(null)
  const authRecoveryStartedRef = useRef(false)

  useEffect(() => { authSnapshotRef.current = authSnapshot }, [authSnapshot])

  const recoverAfterAuthentication = useCallback(() => {
    if (authRecoveryStartedRef.current) return
    authRecoveryStartedRef.current = true
    setAuthOpen(false)
    setRetryKey((value) => value + 1)
  }, [])

  useEffect(() => {
    if (
      request.state === 'unauthorized'
      && authStatus === 'authenticated'
      && unauthorizedAuthSnapshotRef.current !== authSnapshot
    ) recoverAfterAuthentication()
  }, [authSnapshot, authStatus, recoverAfterAuthentication, request.state])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setRequest({ state: 'loading', inventory: null })
    fetchScriptureVerificationInventory({ signal: controller.signal })
      .then((inventory) => {
        if (active) setRequest({ state: 'ready', inventory })
      })
      .catch((error) => {
        if (!active || error?.name === 'AbortError') return
        if (error?.status === 401) {
          unauthorizedAuthSnapshotRef.current = authSnapshotRef.current
          authRecoveryStartedRef.current = false
          setRequest({ state: 'unauthorized', inventory: null })
          if (authSnapshotRef.current.startsWith('anonymous:')) setAuthOpen(true)
        }
        else if (error?.status === 403) setRequest({ state: 'forbidden', inventory: null })
        else setRequest({ state: 'error', inventory: null })
      })
    return () => { active = false; controller.abort() }
  }, [retryKey])

  const groups = useMemo(() => {
    const works = request.inventory?.works ?? []
    const normalizedQuery = query.trim().toLocaleLowerCase()
    const filtered = works.filter((work) => {
      const family = familyFor(work)
      return (statusFilter === 'all' || work.status === statusFilter)
        && (familyFilter === 'all' || family?.id === familyFilter)
        && (!normalizedQuery || [work.workName, work.workId, work.sourceLabel]
          .some((value) => value.toLocaleLowerCase().includes(normalizedQuery)))
    })
    return VERIFICATION_FAMILIES.map((family) => ({
      family,
      familyWorks: works.filter((work) => family.includes(work)),
      works: filtered.filter((work) => family.includes(work))
        .sort((left, right) => left.workName.localeCompare(right.workName)),
    })).filter((group) => group.works.length > 0)
  }, [familyFilter, query, request.inventory, statusFilter])

  if (request.state === 'loading') {
    return <section className="verification-state" role="status">Loading scripture source verification…</section>
  }
  if (request.state !== 'ready') {
    return (
      <>
        <AccessState
          kind={request.state}
          onRetry={() => setRetryKey((value) => value + 1)}
          onSignIn={() => setAuthOpen(true)}
        />
        <AuthDialog
          open={authOpen}
          onClose={() => setAuthOpen(false)}
          onAuthenticated={recoverAfterAuthentication}
        />
      </>
    )
  }

  if (!request.inventory?.integrity?.valid) {
    return <AccessState kind="integrity" onRetry={() => setRetryKey((value) => value + 1)} />
  }

  const allWorks = request.inventory.works
  if (allWorks.length === 0) {
    return (
      <section className="verification-state">
        <span className="verification-state__icon" aria-hidden="true">◇</span>
        <h1>No supplied works are available</h1>
        <p>The verification inventory is connected, but it does not contain any work records yet.</p>
      </section>
    )
  }

  const displayedCount = groups.reduce((sum, group) => sum + group.works.length, 0)
  const awaitingCount = allWorks.filter((work) => familyFor(work)?.affected && !isVerifiedSourceStatus(work.status)).length
  const hasFilters = statusFilter !== 'all' || familyFilter !== 'all' || query !== ''

  return (
    <div className="scripture-verification-page">
      <header className="verification-hero">
        <div>
          <p className="verification-eyebrow">Administrator evidence desk</p>
          <h1>Scripture source verification</h1>
          <p className="verification-hero__intro">Review the mixed-source English research collection work by work. Readability is preserved while provenance is checked against public source evidence.</p>
        </div>
        <div className="verification-summary" aria-label="Verification summary">
          <p>{allWorks.length} supplied works</p>
          <p>{awaitingCount} awaiting exact provenance</p>
        </div>
      </header>

      <section className="verification-controls" aria-labelledby="verification-filters-title">
        <div>
          <p className="verification-eyebrow">Inventory controls</p>
          <span className="sr-only" id="verification-filters-title">Filter supplied works</span>
        </div>
        <label>
          <span>Search</span>
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Book or source" aria-label="Search supplied works" />
        </label>
        <label>
          <span>Status</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filter by verification status">
            <option value="all">All statuses</option>
            {STATUS_OPTIONS.map(([status, label]) => <option value={status} key={status}>{label}</option>)}
          </select>
        </label>
        <label>
          <span>Source family</span>
          <select value={familyFilter} onChange={(event) => setFamilyFilter(event.target.value)} aria-label="Filter by source family">
            <option value="all">All source families</option>
            {VERIFICATION_FAMILIES.map((family) => <option value={family.id} key={family.id}>{family.title}</option>)}
          </select>
        </label>
        <div className="verification-controls__result" aria-live="polite">
          <strong>Showing {displayedCount} of {allWorks.length} works</strong>
          <button type="button" onClick={() => { setQuery(''); setStatusFilter('all'); setFamilyFilter('all') }} disabled={!hasFilters}>Clear filters</button>
        </div>
      </section>

      {displayedCount === 0
        ? <section className="verification-empty" role="status"><h2>No matching works</h2><p>No supplied works match these filters.</p><button className="verification-button" type="button" onClick={() => { setQuery(''); setStatusFilter('all'); setFamilyFilter('all') }}>Clear filters</button></section>
        : groups.map(({ family, familyWorks, works }) => (
          <WorkTable family={family} familyWorks={familyWorks} works={works} key={family.id} />
        ))}
    </div>
  )
}
