import { describe, expect, it } from 'vitest'

import type { AskResponse, Citation, StoredMessage } from '../api/types'
import { chatReducer, isWaiting, nextMessageId, restoreMessages, type ChatMessage } from './chat'

const RESPONSE: AskResponse = {
  question: 'What is the notice period?',
  status: 'answered',
  answer: 'It is 60 days [contract.pdf, p. 4].',
  refusal_reason: null,
  citations: [],
  invalid_citations: [],
  warnings: [],
  best_score: 0.77,
}

const CITATION: Citation = {
  label: 'S1',
  display: '[contract.pdf, p. 4]',
  chunk_id: 'chunk-1',
  document_id: 'doc-1',
  filename: 'contract.pdf',
  page_number: 4,
  position: 0,
  text: 'Either party may terminate with sixty (60) days written notice.',
  score: 0.77,
}

/** A saved message as GET /api/sessions/{id} returns it. */
function stored(position: number, fields: Partial<StoredMessage>): StoredMessage {
  return {
    id: `message-${position}`,
    position,
    role: 'user',
    mode: 'ask',
    content: '',
    status: null,
    refusal_reason: null,
    citations: [],
    invalid_citations: [],
    warnings: [],
    best_score: null,
    agent_trace: [],
    created_at: '2026-10-21T10:00:00Z',
    ...fields,
  }
}

function asked(): ChatMessage[] {
  return chatReducer([], {
    type: 'asked',
    questionId: 1,
    answerId: 2,
    question: 'What is the notice period?',
  })
}

describe('chatReducer', () => {
  it('adds the question and a pending answer', () => {
    const messages = asked()

    expect(messages).toEqual([
      { id: 1, role: 'user', text: 'What is the notice period?' },
      { id: 2, role: 'assistant', status: 'pending' },
    ])
    expect(isWaiting(messages)).toBe(true)
  })

  it('replaces the pending answer with the response', () => {
    const messages = chatReducer(asked(), {
      type: 'answered',
      answerId: 2,
      response: RESPONSE,
      seconds: 12.5,
    })

    expect(messages[1]).toEqual({
      id: 2,
      role: 'assistant',
      status: 'done',
      response: RESPONSE,
      seconds: 12.5,
    })
    expect(isWaiting(messages)).toBe(false)
  })

  it('replaces the pending answer with an error', () => {
    const messages = chatReducer(asked(), { type: 'failed', answerId: 2, error: 'Timeout' })

    expect(messages[1]).toEqual({ id: 2, role: 'assistant', status: 'error', error: 'Timeout' })
    expect(isWaiting(messages)).toBe(false)
  })

  it('keeps the earlier messages unchanged', () => {
    const first = chatReducer(asked(), {
      type: 'answered',
      answerId: 2,
      response: RESPONSE,
      seconds: 3,
    })
    const second = chatReducer(first, {
      type: 'asked',
      questionId: 3,
      answerId: 4,
      question: 'Who signed it?',
    })

    expect(second).toHaveLength(4)
    expect(second.slice(0, 2)).toEqual(first)
    expect(first).toHaveLength(2)
  })

  it('replaces the whole conversation when a session is loaded', () => {
    const loaded: ChatMessage[] = [{ id: 1, role: 'user', text: 'Saved question' }]

    expect(chatReducer(asked(), { type: 'loaded', messages: loaded })).toBe(loaded)
    expect(chatReducer(asked(), { type: 'loaded', messages: [] })).toEqual([])
  })
})

describe('nextMessageId', () => {
  it('starts at 1 for an empty conversation', () => {
    expect(nextMessageId([])).toBe(1)
  })

  it('continues after the largest id, even when ids are not in order', () => {
    const messages: ChatMessage[] = [
      { id: 7, role: 'user', text: 'a' },
      { id: 3, role: 'assistant', status: 'pending' },
    ]

    expect(nextMessageId(messages)).toBe(8)
  })
})

describe('restoreMessages', () => {
  it('turns a saved answer into the same response as a live answer', () => {
    const restored = restoreMessages([
      stored(0, { role: 'user', content: 'What is the notice period?' }),
      stored(1, {
        role: 'assistant',
        content: 'It is 60 days [contract.pdf, p. 4].',
        status: 'answered',
        citations: [CITATION],
        best_score: 0.77,
      }),
    ])

    expect(restored).toEqual([
      { id: 1, role: 'user', text: 'What is the notice period?' },
      {
        id: 2,
        role: 'assistant',
        status: 'done',
        response: { ...RESPONSE, citations: [CITATION] },
        seconds: null,
      },
    ])
  })

  it('keeps the reason of a refusal and links each answer to its own question', () => {
    const restored = restoreMessages([
      stored(0, { role: 'user', content: 'First?' }),
      stored(1, { role: 'assistant', content: 'Answer.', status: 'answered' }),
      stored(2, { role: 'user', content: "What is the CEO's salary?" }),
      stored(3, {
        role: 'assistant',
        content: 'I could not find this information in the available documents.',
        status: 'refused',
        refusal_reason: 'no_relevant_passages',
        best_score: 0.54,
      }),
    ])

    const refusal = restored[3]
    expect(refusal.role === 'assistant' && refusal.status === 'done').toBe(true)
    if (refusal.role === 'assistant' && refusal.status === 'done') {
      expect(refusal.response.question).toBe("What is the CEO's salary?")
      expect(refusal.response.status).toBe('refused')
      expect(refusal.response.refusal_reason).toBe('no_relevant_passages')
      expect(refusal.seconds).toBeNull()
    }
  })

  it('puts the messages in position order, whatever order they arrive in', () => {
    const restored = restoreMessages([
      stored(1, { role: 'assistant', content: 'Answer.', status: 'answered' }),
      stored(0, { role: 'user', content: 'Question?' }),
    ])

    expect(restored.map((message) => message.id)).toEqual([1, 2])
    expect(restored[0]).toEqual({ id: 1, role: 'user', text: 'Question?' })
  })

  it('skips an assistant message that has no status', () => {
    const restored = restoreMessages([
      stored(0, { role: 'user', content: 'Question?' }),
      stored(1, { role: 'assistant', content: 'Broken.', status: null }),
    ])

    expect(restored).toEqual([{ id: 1, role: 'user', text: 'Question?' }])
  })

  it('gives an empty conversation for a new session', () => {
    expect(restoreMessages([])).toEqual([])
  })
})