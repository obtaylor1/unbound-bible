import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ResearchLoadingState from './ResearchLoadingState'

describe('ResearchLoadingState', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('does not claim to build a timeline for an ordinary between-mode question', () => {
    render(<ResearchLoadingState mode="what-happened-between" modeParameters={{}} />)

    act(() => vi.advanceTimersByTime(3_600))

    expect(screen.queryByText('Building the timeline…')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Verifying citations…')
  })

  it('includes a timeline stage only for a complete event range', () => {
    render(<ResearchLoadingState
      mode="what-happened-between"
      modeParameters={{ from_event_id: 'eden', to_event_id: 'abel-killed' }}
    />)

    act(() => vi.advanceTimersByTime(3_600))

    expect(screen.getByRole('status')).toHaveTextContent('Building the timeline…')
  })

  it('does not claim to build a timeline when either event ID is missing', () => {
    render(<ResearchLoadingState
      mode="what-happened-between"
      modeParameters={{ from_event_id: 'eden' }}
    />)

    act(() => vi.advanceTimersByTime(3_600))

    expect(screen.queryByText('Building the timeline…')).not.toBeInTheDocument()
  })
})
