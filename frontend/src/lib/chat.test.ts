import { describe, expect, it } from 'vitest'

import type { AskResponse } from '../api/types'
import { chatReducer, isWaiting, type ChatMessage } from './chat'

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
})