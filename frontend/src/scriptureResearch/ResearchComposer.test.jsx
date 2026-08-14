import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import BetweenEventsComposer from './BetweenEventsComposer'
import ResearchComposer from './ResearchComposer'
import ResearchModeToolbar from './ResearchModeToolbar'
import { DEFAULT_RESEARCH_MODE, DEFAULT_RESEARCH_SETTINGS } from './researchModel'

function ControlledComposer({
  onSubmit = vi.fn(), onExample = vi.fn(), onModeChangeSpy,
  loading = false, transcriptionAvailable = false, onVoiceRequest,
  searchEvents = vi.fn().mockResolvedValue({ events: [] }),
} = {}) {
  const [value, setValue] = useState('')
  const [settings, setSettings] = useState({
    ...DEFAULT_RESEARCH_SETTINGS,
    sourceScopes: [...DEFAULT_RESEARCH_SETTINGS.sourceScopes],
    modeParameters: {},
  })
  const [mode, setMode] = useState(DEFAULT_RESEARCH_MODE)
  const changeMode = (nextMode) => {
    onModeChangeSpy?.(nextMode)
    setMode(nextMode)
  }
  return <ResearchComposer
    value={value} onChange={setValue}
    settings={settings} onSettingsChange={setSettings}
    mode={mode} onModeChange={changeMode}
    onSubmit={onSubmit} loading={loading}
    transcriptionAvailable={transcriptionAvailable}
    onVoiceRequest={onVoiceRequest} searchEvents={searchEvents}
    onExample={onExample}
  />
}

const events = [
  { id: 'eden', title: 'Life in Eden' },
  { id: 'expulsion', title: 'Expulsion from Eden' },
  { id: 'abel', title: 'Abel is born' },
]

describe('ResearchComposer', () => {
  it('renders supplied defaults and enforces exclusive, non-empty source scopes', async () => {
    const user = userEvent.setup()
    render(<ControlledComposer />)
    expect(screen.getByRole('button', { name: 'Biblical Canon' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Deep Research' })).toHaveAttribute('aria-pressed', 'true')

    await user.click(screen.getByRole('button', { name: 'Ethiopian Tradition' }))
    expect(screen.getByRole('button', { name: 'Biblical Canon' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Ethiopian Tradition' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'All Sources' }))
    expect(screen.getByRole('button', { name: 'All Sources' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Biblical Canon' })).toHaveAttribute('aria-pressed', 'false')
    await user.click(screen.getByRole('button', { name: 'Commentary' }))
    expect(screen.getByRole('button', { name: 'All Sources' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Commentary' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'Commentary' }))
    expect(screen.getByRole('button', { name: 'Commentary' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('selects exactly one depth and exposes descriptions accessibly', async () => {
    const user = userEvent.setup()
    render(<ControlledComposer />)
    const quick = screen.getByRole('button', { name: 'Quick Answer' })
    await user.click(quick)
    expect(quick).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Deep Research' })).toHaveAttribute('aria-pressed', 'false')
    expect(quick).toHaveAccessibleDescription()
  })

  it('submits exact controlled values on Enter, preserves text, and keeps Shift+Enter as editing', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<ControlledComposer onSubmit={onSubmit} />)
    const question = screen.getByRole('textbox', { name: 'Research question' })
    await user.type(question, 'Genesis 4')
    await user.keyboard('{Shift>}{Enter}{/Shift}')
    expect(onSubmit).not.toHaveBeenCalled()
    await user.keyboard('{Enter}')
    expect(onSubmit).toHaveBeenCalledWith({
      question: 'Genesis 4', sourceScopes: ['biblical-canon'],
      depth: 'deep-research', mode: 'what-happened-between', modeParameters: {},
    })
    expect(question).toHaveValue('Genesis 4\n')
  })

  it('ignores IME and modified Enter, and disables Ask while blank or loading', async () => {
    const onSubmit = vi.fn()
    const { rerender } = render(<ControlledComposer onSubmit={onSubmit} />)
    const question = screen.getByRole('textbox', { name: 'Research question' })
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
    fireEvent.change(question, { target: { value: 'Enoch' } })
    fireEvent.keyDown(question, { key: 'Enter', isComposing: true })
    fireEvent.keyDown(question, { key: 'Enter', ctrlKey: true })
    expect(onSubmit).not.toHaveBeenCalled()
    rerender(<ControlledComposer onSubmit={onSubmit} loading />)
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
    fireEvent.keyDown(screen.getByRole('textbox', { name: 'Research question' }), { key: 'Enter' })
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('offers the six compact examples without auto-running them', async () => {
    const user = userEvent.setup()
    const onExample = vi.fn()
    const onSubmit = vi.fn()
    render(<ControlledComposer onExample={onExample} onSubmit={onSubmit} />)
    for (const name of ['Eden to Abel', 'Explain Enoch', 'Malachi to Matthew', 'Genesis 6 and Enoch', 'Cush', "Ge'ez"]) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Explain Enoch' }))
    expect(onExample).toHaveBeenCalledWith(
      'Explain Enoch and its place in biblical tradition',
      {
        sourceScopes: ['biblical-canon'],
        depth: 'deep-research',
        modeParameters: {},
      },
      'explain-a-book',
    )
    const firstSettings = onExample.mock.calls[0][1]
    expect(firstSettings).not.toBe(DEFAULT_RESEARCH_SETTINGS)
    expect(firstSettings.sourceScopes).not.toBe(DEFAULT_RESEARCH_SETTINGS.sourceScopes)
    firstSettings.sourceScopes.push('commentary')
    await user.click(screen.getByRole('button', { name: 'Cush' }))
    expect(onExample.mock.calls[1]).toEqual([
      'Research Cush across Scripture and ancient sources',
      { sourceScopes: ['biblical-canon'], depth: 'deep-research', modeParameters: {} },
      'people-and-places',
    ])
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('contains no nested form and exposes a real, capability-gated voice action', async () => {
    const user = userEvent.setup()
    const voice = vi.fn()
    const { container, rerender } = render(<ControlledComposer onVoiceRequest={voice} />)
    expect(container.querySelector('form')).toBeNull()
    const unavailable = screen.getByRole('button', { name: 'Voice research is unavailable' })
    expect(unavailable).toBeDisabled()
    expect(unavailable).toHaveAttribute('title', 'Voice research is unavailable')
    rerender(<ControlledComposer transcriptionAvailable onVoiceRequest={voice} />)
    await user.click(screen.getByRole('button', { name: 'Start voice research' }))
    expect(voice).toHaveBeenCalledOnce()
  })

  it('renders between-event controls only in the matching mode while natural questions remain available', async () => {
    const user = userEvent.setup()
    render(<ControlledComposer searchEvents={vi.fn().mockResolvedValue({ events })} />)
    expect(await screen.findByRole('combobox', { name: 'From' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Research question' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Explain a Book' }))
    expect(screen.queryByRole('combobox', { name: 'From' })).not.toBeInTheDocument()
  })
})

describe('ResearchModeToolbar', () => {
  it('uses exactly six non-navigating toolbar buttons and only reports selection', async () => {
    const user = userEvent.setup()
    const onModeChange = vi.fn()
    const { container } = render(<ResearchModeToolbar mode="what-happened-between" onModeChange={onModeChange} />)
    expect(screen.getByRole('toolbar', { name: 'Research mode' })).toBeInTheDocument()
    expect(screen.getAllByRole('button')).toHaveLength(6)
    expect(screen.getByRole('button', { name: 'What Happened Between?' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'Explain a Book' }))
    expect(onModeChange).toHaveBeenCalledWith('explain-a-book')
    expect(container.querySelector('a')).toBeNull()
  })
})

describe('BetweenEventsComposer', () => {
  it('loads verified events and submits only a distinct forward range', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    const searchEvents = vi.fn().mockResolvedValue({ events })
    render(<BetweenEventsComposer question="Trace the interval" onSubmit={onSubmit} searchEvents={searchEvents} />)
    expect(searchEvents).toHaveBeenCalledWith('', expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(screen.getByRole('status')).toHaveTextContent('Loading events')
    const from = await screen.findByRole('combobox', { name: 'From' })
    const to = screen.getByRole('combobox', { name: 'To' })
    const build = screen.getByRole('button', { name: 'Build Timeline' })
    await user.selectOptions(from, 'abel')
    await user.selectOptions(to, 'abel')
    expect(build).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent(/different events/i)
    await user.selectOptions(to, 'eden')
    expect(build).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent(/before/i)
    await user.selectOptions(from, 'eden')
    await user.selectOptions(to, 'abel')
    expect(build).toBeEnabled()
    await user.click(build)
    expect(onSubmit).toHaveBeenCalledWith({
      question: 'Trace the interval',
      modeParameters: { from_event_id: 'eden', to_event_id: 'abel' },
    })
  })

  it('composes a question from selected event titles when the current question is blank', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<BetweenEventsComposer question=" " onSubmit={onSubmit} searchEvents={vi.fn().mockResolvedValue({ events })} />)
    await user.selectOptions(await screen.findByRole('combobox', { name: 'From' }), 'eden')
    await user.selectOptions(screen.getByRole('combobox', { name: 'To' }), 'abel')
    await user.click(screen.getByRole('button', { name: 'Build Timeline' }))
    expect(onSubmit).toHaveBeenCalledWith({
      question: 'What happened between Life in Eden and Abel is born?',
      modeParameters: { from_event_id: 'eden', to_event_id: 'abel' },
    })
  })

  it('reports empty and failed catalogs', async () => {
    const { rerender } = render(<BetweenEventsComposer question="" onSubmit={vi.fn()} searchEvents={vi.fn().mockResolvedValue({ events: [] })} />)
    expect(await screen.findByRole('status')).toHaveTextContent('No verified events are available')
    rerender(<BetweenEventsComposer question="" onSubmit={vi.fn()} searchEvents={vi.fn().mockRejectedValue(new Error('offline'))} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load verified events')
  })

  it('aborts stale requests and ignores late results, including after unmount', async () => {
    let resolveFirst
    let resolveSecond
    const first = new Promise((resolve) => { resolveFirst = resolve })
    const second = new Promise((resolve) => { resolveSecond = resolve })
    const one = vi.fn(() => first)
    const two = vi.fn(() => second)
    const { rerender, unmount } = render(<BetweenEventsComposer question="" onSubmit={vi.fn()} searchEvents={one} />)
    const firstSignal = one.mock.calls[0][1].signal
    rerender(<BetweenEventsComposer question="" onSubmit={vi.fn()} searchEvents={two} />)
    expect(firstSignal.aborted).toBe(true)
    resolveFirst({ events: [{ id: 'stale', title: 'Stale' }] })
    resolveSecond({ events })
    expect(await screen.findByRole('combobox', { name: 'From' })).not.toHaveTextContent('Stale')
    const secondSignal = two.mock.calls[0][1].signal
    unmount()
    expect(secondSignal.aborted).toBe(true)
    await waitFor(() => expect(firstSignal.aborted).toBe(true))
  })
})
