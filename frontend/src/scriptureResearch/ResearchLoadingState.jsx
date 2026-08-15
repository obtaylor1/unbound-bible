import { useEffect, useMemo, useState } from 'react'

const BASE_STAGES = [
  'Searching selected library sources…',
  'Ranking relevant passages…',
  'Comparing available evidence…',
]

export default function ResearchLoadingState({ mode, modeParameters = {} }) {
  const hasCompleteEventRange = mode === 'what-happened-between'
    && typeof modeParameters.from_event_id === 'string'
    && modeParameters.from_event_id.trim().length > 0
    && typeof modeParameters.to_event_id === 'string'
    && modeParameters.to_event_id.trim().length > 0
  const stages = useMemo(() => [
    ...BASE_STAGES,
    ...(hasCompleteEventRange ? ['Building the timeline…'] : []),
    'Verifying citations…',
    'Preparing the research summary…',
  ], [hasCompleteEventRange])
  const [stageIndex, setStageIndex] = useState(0)

  useEffect(() => {
    setStageIndex(0)
    const timer = window.setInterval(() => {
      setStageIndex((current) => Math.min(current + 1, stages.length - 1))
    }, 1200)
    return () => window.clearInterval(timer)
  }, [stages])

  return (
    <section className="research-loading" aria-labelledby="research-loading-title">
      <h2 id="research-loading-title">Building your grounded research</h2>
      <p role="status" aria-live="polite" aria-atomic="true">{stages[stageIndex]}</p>
      <p>Only verified material from your selected library sources will be used.</p>
    </section>
  )
}
