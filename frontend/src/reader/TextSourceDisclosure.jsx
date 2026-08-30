import { useEffect, useRef, useState } from 'react'
import TranslationOverview from './TranslationOverview'
import { isCompositeEnglishEdition } from './compositeEdition'
import {
  SOURCE_VERIFICATION_LABELS,
  boundedPublicText,
  formatVerifiedDate,
  isVerifiedSourceStatus,
  normalizedTransformations,
  safePublicSourceUrl,
  sourceVerificationLabel,
} from './sourceVerification'

function canonLabel(value) {
  if (value === 'ethio81') return 'Ethiopian 81-book canon'
  if (value === 'supplemental') return 'Supplemental text'
  return value
}

function Detail({ label, value }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="text-source-disclosure__detail">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

export function SourceVerificationBadge({ status, className = '' }) {
  const priorStatus = useRef(status)
  const [announcedStatus, setAnnouncedStatus] = useState(null)

  useEffect(() => {
    if (priorStatus.current !== status) setAnnouncedStatus(status)
    priorStatus.current = status
  }, [status])

  const modifier = Object.hasOwn(SOURCE_VERIFICATION_LABELS, status)
    ? ` text-source-disclosure__badge--${status}`
    : ' text-source-disclosure__badge--unknown'

  return (
    <span
      className={`text-source-disclosure__badge${modifier}${className ? ` ${className}` : ''}`}
      role={announcedStatus === status ? 'status' : undefined}
    >
      {sourceVerificationLabel(status)}
    </span>
  )
}

export default function TextSourceDisclosure({ source, edition }) {
  const hasSource = source && typeof source === 'object'
  if (!hasSource && !isCompositeEnglishEdition(edition)) return null

  const sourceLabel = boundedPublicText(source?.sourceLabel, 200) || 'Source details unavailable'
  const verificationStatus = boundedPublicText(source?.verificationStatus, 32)
  const provenanceUrl = safePublicSourceUrl(source?.provenanceUrl)
  const rightsUrl = safePublicSourceUrl(source?.rightsUrl)
  const verifiedDate = isVerifiedSourceStatus(verificationStatus)
    ? formatVerifiedDate(source?.verifiedAt)
    : null
  const transformations = normalizedTransformations(source?.transformations)

  return (
    <section className="text-source-disclosure" aria-label="Text source">
      {hasSource ? (
        <div className="text-source-disclosure__identity">
          <span className="text-source-disclosure__eyebrow">Text source</span>
          <strong>{sourceLabel}</strong>
          {source.fallback === true ? (
            <span className="text-source-disclosure__badge text-source-disclosure__badge--fallback">
              KJV fallback
            </span>
          ) : null}
          <SourceVerificationBadge status={verificationStatus} />
        </div>
      ) : null}

      <TranslationOverview edition={edition} />

      {hasSource ? (
        <details>
          <summary>About this text</summary>
          <div className="text-source-disclosure__body">
            <dl>
              <Detail label="Translator" value={boundedPublicText(source.translator, 200)} />
              <Detail label="Source language" value={boundedPublicText(source.sourceLanguage, 100)} />
              <Detail label="Text tradition" value={boundedPublicText(source.sourceTradition, 200)} />
              <Detail
                label="Published"
                value={
                  Number.isSafeInteger(source.publishedYear)
                  && source.publishedYear >= 1
                  && source.publishedYear <= 9999
                    ? source.publishedYear
                    : null
                }
              />
              <Detail label="License" value={boundedPublicText(source.license, 100)} />
              <Detail label="Attribution" value={boundedPublicText(source.attribution, 2000)} />
              <Detail label="Source edition" value={boundedPublicText(source.sourceEdition, 200)} />
              <Detail label="Source revision" value={boundedPublicText(source.sourceRevision, 200)} />
              <Detail
                label="Rights jurisdiction"
                value={boundedPublicText(source.rightsJurisdiction, 500)}
              />
              <Detail
                label="Modification note"
                value={
                  source.modified === true
                    ? boundedPublicText(source.modificationNote, 2000)
                    : null
                }
              />
              <Detail label="Verified" value={verifiedDate} />
              {transformations.length ? (
                <div className="text-source-disclosure__detail">
                  <dt>Documented changes</dt>
                  <dd>
                    <ul className="text-source-disclosure__transformations">
                      {transformations.map((transformation) => (
                        <li key={transformation}>{transformation}</li>
                      ))}
                    </ul>
                  </dd>
                </div>
              ) : null}
              <Detail
                label="Canon placement"
                value={canonLabel(boundedPublicText(source.canonScope, 20))}
              />
            </dl>
            <div className="text-source-disclosure__links">
              {provenanceUrl ? (
                <a href={provenanceUrl} target="_blank" rel="noopener noreferrer">
                  View source record (opens in a new tab)
                </a>
              ) : null}
              {rightsUrl ? (
                <a href={rightsUrl} target="_blank" rel="noopener noreferrer">
                  View rights record (opens in a new tab)
                </a>
              ) : null}
            </div>
          </div>
        </details>
      ) : null}
    </section>
  )
}
