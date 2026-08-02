export default function ComparisonSummary({
  reference,
  summary,
  onShowDifferences,
  onExplainVerse,
  onViewOriginalWords,
}) {
  const differenceLabel = summary.differenceCount === 1
    ? '1 wording difference found'
    : `${summary.differenceCount} wording differences found`

  return (
    <section className="comparison-summary" aria-labelledby="comparison-summary-title">
      <div className="comparison-summary-copy">
        <span className="comparison-summary-mark" aria-hidden="true">✦</span>
        <div>
          <p className="compare-eyebrow">Quick summary</p>
          <h2 id="comparison-summary-title">{reference} comparison</h2>
          <p>{summary.message}</p>
          <span>{differenceLabel}</span>
        </div>
      </div>
      <div className="comparison-summary-actions">
        <button type="button" aria-label="Explain This Verse" onClick={onExplainVerse}>
          <strong>Explain This Verse</strong>
          <span>AI explanation</span>
        </button>
        <button type="button" className="is-cyan" aria-label="Show Differences" onClick={onShowDifferences}>
          <strong>Show Differences</strong>
          <span>See wording changes</span>
        </button>
        <button type="button" className="is-gold" aria-label="View Original Words" onClick={onViewOriginalWords}>
          <strong>View Original Words</strong>
          <span>Hebrew / Greek</span>
        </button>
      </div>
    </section>
  )
}
