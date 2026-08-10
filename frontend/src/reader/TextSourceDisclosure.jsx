import TranslationOverview from './TranslationOverview'

function isCompositeEnglishEdition(edition) {
  return typeof edition?.code === 'string'
    && edition.code.trim().toUpperCase() === 'EOTC-COMPOSITE-EN'
}

function safeProvenanceUrl(value) {
  if (typeof value !== 'string' || !value.trim()) return null
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null
  } catch {
    return null
  }
}

function canonLabel(value) {
  if (value === 'ethio81') return 'Ethiopian 81-book canon'
  if (value === 'supplemental') return 'Supplemental text'
  return value
}

function verificationLabel(value) {
  if (typeof value !== 'string' || !value.trim()) return null
  const text = value.trim().replace(/[-_]+/g, ' ')
  return `${text.charAt(0).toLocaleUpperCase()}${text.slice(1)}`
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

export default function TextSourceDisclosure({ source, edition }) {
  const hasSource = source && typeof source === 'object'
  if (!hasSource && !isCompositeEnglishEdition(edition)) return null

  const sourceLabel = typeof source?.sourceLabel === 'string' && source.sourceLabel.trim()
    ? source.sourceLabel.trim()
    : 'Source details unavailable'
  const provenanceUrl = safeProvenanceUrl(source?.provenanceUrl)

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
          {source.verificationStatus === 'provisional' ? (
            <span className="text-source-disclosure__badge">
              Provisional source record
            </span>
          ) : null}
        </div>
      ) : null}

      <TranslationOverview edition={edition} />

      {hasSource ? (
        <details>
          <summary>About this text</summary>
          <div className="text-source-disclosure__body">
            <dl>
              <Detail label="Translator" value={source.translator} />
              <Detail label="Source language" value={source.sourceLanguage} />
              <Detail label="Text tradition" value={source.sourceTradition} />
              <Detail label="Published" value={source.publishedYear} />
              <Detail label="License" value={source.license} />
              <Detail label="Attribution" value={source.attribution} />
              <Detail
                label="Modification note"
                value={source.modified === true ? source.modificationNote : null}
              />
              <Detail
                label="Verification"
                value={verificationLabel(source.verificationStatus)}
              />
              <Detail label="Canon placement" value={canonLabel(source.canonScope)} />
            </dl>
            {provenanceUrl ? (
              <a href={provenanceUrl} target="_blank" rel="noopener noreferrer">
                View source record (opens in a new tab)
              </a>
            ) : null}
          </div>
        </details>
      ) : null}
    </section>
  )
}
