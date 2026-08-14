import { useId } from 'react'
import BetweenEventsComposer from './BetweenEventsComposer'
import ResearchModeToolbar from './ResearchModeToolbar'
import { RESEARCH_DEPTHS, SOURCE_SCOPES } from './researchModel'

const DEPTH_DESCRIPTIONS = {
  quick: 'A concise answer using the strongest available sources.',
  study: 'A broader study with supporting context and references.',
  'deep-research': 'A detailed investigation across the selected sources.',
  scholar: 'The most extensive analysis with scholarly source detail.',
}

const EXAMPLES = [
  {
    label: 'Eden to Abel',
    question: 'What happened between Eden and Abel?',
    mode: 'what-happened-between',
    modeParameters: { from_event_id: 'eden', to_event_id: 'abel-killed' },
  },
  { label: 'Explain Enoch', question: 'Explain Enoch and its place in biblical tradition', mode: 'explain-a-book' },
  { label: 'Malachi to Matthew', question: 'What happened between Malachi and Matthew?', mode: 'what-happened-between' },
  { label: 'Genesis 6 and Enoch', question: 'Compare the Genesis 6 account with 1 Enoch', mode: 'compare-accounts' },
  { label: 'Cush', question: 'Research Cush across Scripture and ancient sources', mode: 'people-and-places' },
  { label: "Ge'ez", question: "What can the Ge'ez language reveal about biblical texts?", mode: 'original-languages' },
]

export default function ResearchComposer({
  value,
  onChange,
  settings,
  onSettingsChange,
  mode,
  onModeChange,
  onSubmit,
  loading,
  transcriptionAvailable = false,
  onVoiceRequest,
  searchEvents,
  onExample,
}) {
  const question = typeof value === 'string' ? value : ''
  const sourceScopes = settings.sourceScopes
  const questionId = useId()
  const depthDescriptionPrefix = useId()

  const submit = () => {
    const normalizedQuestion = question.trim()
    if (!normalizedQuestion || loading) return
    onSubmit({
      question: normalizedQuestion,
      sourceScopes: [...sourceScopes],
      depth: settings.depth,
      mode,
      modeParameters: { ...(settings.modeParameters ?? {}) },
    })
  }

  const changeScope = (scope) => {
    let nextScopes
    if (scope === 'all-sources') {
      nextScopes = ['all-sources']
    } else if (sourceScopes.includes('all-sources')) {
      nextScopes = [scope]
    } else if (sourceScopes.includes(scope)) {
      if (sourceScopes.length === 1) return
      nextScopes = sourceScopes.filter((item) => item !== scope)
    } else {
      nextScopes = [...sourceScopes, scope]
    }
    onSettingsChange({ ...settings, sourceScopes: nextScopes })
  }

  const submitBetweenEvents = ({ question: eventQuestion, modeParameters }) => {
    if (loading) return
    onSubmit({
      question: eventQuestion,
      sourceScopes: [...sourceScopes],
      depth: settings.depth,
      mode,
      modeParameters,
    })
  }

  const handleQuestionKeyDown = (event) => {
    if (event.key !== 'Enter') return
    if (event.nativeEvent.isComposing || event.isComposing) return
    if (event.shiftKey || event.altKey || event.ctrlKey || event.metaKey) return
    event.preventDefault()
    submit()
  }

  return (
    <section className="research-composer" aria-label="Scripture research composer">
      <div className="research-composer__question">
        <label htmlFor={questionId}>Research question</label>
        <textarea
          id={questionId}
          value={question}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleQuestionKeyDown}
          rows={4}
          disabled={loading}
        />
        <div className="research-composer__actions">
          <button
            type="button"
            aria-label={transcriptionAvailable ? 'Start voice research' : 'Voice research is unavailable'}
            title={transcriptionAvailable ? 'Start voice research' : 'Voice research is unavailable'}
            disabled={!transcriptionAvailable || loading}
            onClick={onVoiceRequest}
          >
            <span aria-hidden="true">◉</span>
          </button>
          <button type="button" disabled={!question.trim() || loading} onClick={submit}>
            <span aria-hidden="true">✦</span> Ask
          </button>
        </div>
      </div>

      <fieldset className="research-composer__scopes">
        <legend>Source scope</legend>
        {SOURCE_SCOPES.map((scope) => (
          <button
            type="button"
            key={scope.value}
            aria-pressed={sourceScopes.includes(scope.value)}
            disabled={loading}
            onClick={() => changeScope(scope.value)}
          >
            {scope.label}
          </button>
        ))}
      </fieldset>

      <fieldset className="research-composer__depths">
        <legend>Research depth</legend>
        {RESEARCH_DEPTHS.map((depth) => {
          const descriptionId = `${depthDescriptionPrefix}-${depth.value}`
          return (
            <span className="research-composer__depth" key={depth.value}>
              <button
                type="button"
                aria-pressed={settings.depth === depth.value}
                disabled={loading}
                aria-describedby={descriptionId}
                onClick={() => onSettingsChange({ ...settings, depth: depth.value })}
              >
                {depth.label}
              </button>
              <span id={descriptionId}>{DEPTH_DESCRIPTIONS[depth.value]}</span>
            </span>
          )
        })}
      </fieldset>

      <ResearchModeToolbar mode={mode} onModeChange={onModeChange} disabled={loading} />

      {mode === 'what-happened-between' && (
        <BetweenEventsComposer
          question={question}
          onSubmit={submitBetweenEvents}
          searchEvents={searchEvents}
          loading={loading}
        />
      )}

      <div className="research-composer__examples" aria-label="Research examples">
        {EXAMPLES.map((example) => (
          <button
            type="button"
            key={example.label}
            disabled={loading}
            onClick={() => onExample?.(
              example.question,
              {
                ...settings,
                sourceScopes: [...sourceScopes],
                modeParameters: {
                  ...(settings.modeParameters ?? {}),
                  ...(example.modeParameters ?? {}),
                },
              },
              example.mode ?? mode,
            )}
          >
            {example.label}
          </button>
        ))}
      </div>
    </section>
  )
}
