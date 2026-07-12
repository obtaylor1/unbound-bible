import { afterEach, describe, expect, it, vi } from 'vitest'
import { askStudyQuestion } from './studyApi'

describe('askStudyQuestion', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('normalizes a grounded API answer', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ answer: 'A grounded answer', sources: [{ reference: 'Genesis 1:1', text: 'In the beginning' }], is_demo: false, provider: 'ollama', model: 'local', grounding_status: 'grounded' })
    }))

    await expect(askStudyQuestion('Question')).resolves.toMatchObject({
      answer: 'A grounded answer',
      provenance: 'live',
      sources: [{ citation: 'Genesis 1:1' }],
      groundingStatus: 'grounded',
      provider: 'ollama'
    })
  })

  it('rejects malformed answers', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }))
    await expect(askStudyQuestion('Question')).rejects.toThrow('unreadable answer')
  })

  it('uses authoritative backend demo metadata', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ answer: 'Preview response.', sources: [], is_demo: true, provider: 'demo', model: 'bundled-demo', grounding_status: 'demo' })
    }))
    await expect(askStudyQuestion('Question')).resolves.toMatchObject({ provenance: 'demo' })
  })

  it('returns an explicitly labeled demo answer only when enabled', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    const result = await askStudyQuestion('What does the Bible say about forgiveness?', { allowDemo: true })
    expect(result.provenance).toBe('demo')
    expect(result.answer).toBeTruthy()
  })

  it('surfaces the API error when demo mode is disabled', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    await expect(askStudyQuestion('Question')).rejects.toThrow('temporarily unavailable')
  })
})
