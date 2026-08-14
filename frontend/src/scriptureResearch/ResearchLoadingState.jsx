import { useEffect, useMemo, useState } from 'react'

const BASE_STAGES = [
  'Searching selected library sources…',
  'Ranking relevant passages…',
  'Comparing available evidence…',
]

export default function ResearchLoadingState({ mode }) {
  const stages = useMemo(() => [
    ...BASE_STAGES,
    ...(mode === 'what-happened-between' ? ['Building the timeline…'] : []),
    'Verifying citations…',
    'Preparing the research summary…',
  ], [mode])
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
