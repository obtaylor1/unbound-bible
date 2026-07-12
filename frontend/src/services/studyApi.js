import { DEMO_ENABLED } from '../config/runtime'

const normalizeSources = (context = []) => context.map((source) => {
  if (typeof source === 'string') {
    return { title: 'Library reference', citation: source, excerpt: '' }
  }

  return {
    title: source.title || 'Library reference',
    citation: source.citation || source.reference || '',
    excerpt: source.excerpt || source.text || ''
  }
})

const findDemoAnswer = async (question) => {
  const { MOCK_ASK_ANSWERS } = await import('../data/mockData')
  const normalized = question.toLowerCase()
  const entries = Object.entries(MOCK_ASK_ANSWERS)
  const direct = entries.find(([key]) => key === normalized.trim())
  if (direct) return direct[1]

  const matchers = [
    [['forgive', 'forgiveness'], 'what does the bible say about forgiveness?'],
    [['ethiopian', 'canon', 'king james'], 'how does the ethiopian bible compare with the king james version on this passage?'],
    [['history', 'background', 'context'], 'what is the historical background of this chapter?'],
    [['cross-reference', 'theme'], 'what are the major cross-references for this theme?'],
    [['hebrew', 'greek', 'aramaic', 'geʽez', 'original language'], 'what does the original hebrew, greek, aramaic, or geʽez suggest?'],
    [['teen', 'teenager'], 'how would i explain this passage to a teenager?']
  ]

  const matchedKey = matchers.find(([needles]) => needles.some((needle) => normalized.includes(needle)))?.[1]
  return matchedKey ? MOCK_ASK_ANSWERS[matchedKey] : null
}

export async function askStudyQuestion(question, { allowDemo = DEMO_ENABLED } = {}) {
  try {
    const response = await fetch('/api/v1/chat/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question })
    })

    if (!response.ok) throw new Error(`The study library is temporarily unavailable (${response.status}).`)

    const data = await response.json()
    if (!data || typeof data.answer !== 'string' || !data.answer.trim()) {
      throw new Error('The study library returned an unreadable answer.')
    }

    return {
      answer: data.answer,
      sources: normalizeSources(data.context_used || data.sources || []),
      followUps: data.follow_ups || [],
      provenance: data.is_demo ? 'demo' : 'live',
      groundingStatus: data.grounding_status || 'unknown',
      provider: data.provider || 'legacy',
      model: data.model || 'unknown'
    }
  } catch (error) {
    if (!allowDemo) throw error
    const demo = await findDemoAnswer(question)
    if (!demo) throw error

    return {
      answer: demo.answer,
      sources: normalizeSources(demo.sources || []),
      followUps: demo.followUps || [],
      provenance: 'demo',
      groundingStatus: 'demo',
      provider: 'demo',
      model: 'bundled-demo'
    }
  }
}
