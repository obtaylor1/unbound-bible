import { RESEARCH_MODES } from './researchModel'

export default function ResearchModeToolbar({ mode, onModeChange, disabled = false }) {
  return (
    <div className="research-mode-toolbar" role="group" aria-label="Research modes">
      {RESEARCH_MODES.map((option) => (
        <button
          className="research-mode-toolbar__button"
          type="button"
          key={option.value}
          aria-pressed={mode === option.value}
          disabled={disabled}
          onClick={() => onModeChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
