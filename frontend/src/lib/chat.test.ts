import { describe, expect, it } from 'vitest'

import type { AgentRun, AskResponse, Citation, Extraction, StoredMessage } from '../api/types'
import {
  chatReducer,
  isWaiting,
  nextMessageId,
  restoreMessages,
  type ChatMessage,
  type ExtractResponse,
} from './chat'

const RESPONSE: AskResponse = {
  question: 'What is the notice period?',
  status: 'answered',
  answer: 'It is 60 days [contract.pdf, p. 4].',
  refusal_reason: null,
  citations: [],
  invalid_citations: [],
  warnings: [],
  best_score: 0.77,
  review: null,
  agent_trace: [],
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

const TRACE: AgentRun[] = [
  { name: 'analyst', kind: 'agent', status: 'ok', duration_ms: 3306, summary: 'type invoice' },
  { name: 'extractor', kind: 'agent', status: 'ok', duration_ms: 4864, summary: '7 of 7' },
  { name: 'critic', kind: 'agent', status: 'ok', duration_ms: 4, summary: 'no issue' },
]

const EXTRACTION: Extraction = {
  document_id: 'doc-2',
  filename: 'invoice.pdf',
  document_type: 'invoice',
  fields: [
    {
      name: 'invoice_number',
      label: 'Invoice number',
      value: 'HDS-INV-2026-0042',
      page: 1,
      source: { ...CITATION, label: 'invoice_number', display: '[invoice.pdf, p. 1]' },
    },
  ],
}

const EXTRACT_RESPONSE: ExtractResponse = {
  request: 'Extract the key fields of invoice.pdf',
  status: 'answered',
  message: 'Extracted 1 of 1 fields from invoice.pdf (invoice).',
  refusal_reason: null,
  extraction: EXTRACTION,
  review: { verdict: 'ok', issues: [], model_checked: false },
  agent_trace: TRACE,
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
    review: null,
    agent_trace: [],
    extraction: null,
    created_at: '2026-10-21T10:00:00Z',
    ...fields,
  }
}

const SESSION_ID = 'session-1'
const SAVED = { sessionId: SESSION_ID, messageId: 'message-1' }

function asked(): ChatMessage[] {
  return chatReducer([], {
    type: 'asked',
    questionId: 1,
    answerId: 2,
    question: 'What is the notice period?',
    mode: 'ask',
  })
}

describe('chatReducer', () => {
  it('adds the question and a pending answer', () => {
    const messages = asked()

    expect(messages).toEqual([
      { id: 1, role: 'user', text: 'What is the notice period?' },
      { id: 2, role: 'assistant', status: 'pending', mode: 'ask' },
    ])
    expect(isWaiting(messages)).toBe(true)
  })

  it('remembers that a pending answer is an extraction', () => {
    const messages = chatReducer([], {
      type: 'asked',
      questionId: 1,
      answerId: 2,
      question: 'Extract the key fields of invoice.pdf',
      mode: 'extract',
    })

    expect(messages[1]).toEqual({ id: 2, role: 'assistant', status: 'pending', mode: 'extract' })
    expect(isWaiting(messages)).toBe(true)
  })

  it('replaces the pending answer with the extracted fields', () => {
    const messages = chatReducer(asked(), {
      type: 'extracted',
      answerId: 2,
      response: EXTRACT_RESPONSE,
      seconds: 8.2,
      saved: SAVED,
    })

    expect(messages[1]).toEqual({
      id: 2,
      role: 'assistant',
      status: 'extracted',
      response: EXTRACT_RESPONSE,
      seconds: 8.2,
      saved: SAVED,
    })
    expect(isWaiting(messages)).toBe(false)
  })

  it('replaces the pending answer with the response', () => {
    const messages = chatReducer(asked(), {
      type: 'answered',
      answerId: 2,
      response: RESPONSE,
      seconds: 12.5,
      saved: SAVED,
    })

    expect(messages[1]).toEqual({
      id: 2,
      role: 'assistant',
      status: 'done',
      response: RESPONSE,
      seconds: 12.5,
      saved: SAVED,
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
      saved: SAVED,
    })
    const second = chatReducer(first, {
      type: 'asked',
      questionId: 3,
      answerId: 4,
      question: 'Who signed it?',
      mode: 'ask',
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
      { id: 3, role: 'assistant', status: 'pending', mode: 'ask' },
    ]

    expect(nextMessageId(messages)).toBe(8)
  })
})

describe('restoreMessages', () => {
  it('turns a saved answer into the same response as a live answer', () => {
    const restored = restoreMessages(
      [
        stored(0, { role: 'user', content: 'What is the notice period?' }),
        stored(1, {
          role: 'assistant',
          content: 'It is 60 days [contract.pdf, p. 4].',
          status: 'answered',
          citations: [CITATION],
          best_score: 0.77,
        }),
      ],
      SESSION_ID,
    )

    expect(restored).toEqual([
      { id: 1, role: 'user', text: 'What is the notice period?' },
      {
        id: 2,
        role: 'assistant',
        status: 'done',
        response: { ...RESPONSE, citations: [CITATION] },
        seconds: null,
        saved: { sessionId: SESSION_ID, messageId: 'message-1' },
      },
    ])
  })

  it('keeps the reason of a refusal and links each answer to its own question', () => {
    const restored = restoreMessages(
      [
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
      ],
      SESSION_ID,
    )

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
    const restored = restoreMessages(
      [
        stored(1, { role: 'assistant', content: 'Answer.', status: 'answered' }),
        stored(0, { role: 'user', content: 'Question?' }),
      ],
      SESSION_ID,
    )

    expect(restored.map((message) => message.id)).toEqual([1, 2])
    expect(restored[0]).toEqual({ id: 1, role: 'user', text: 'Question?' })
  })

  it('skips an assistant message that has no status', () => {
    const restored = restoreMessages(
      [
        stored(0, { role: 'user', content: 'Question?' }),
        stored(1, { role: 'assistant', content: 'Broken.', status: null }),
      ],
      SESSION_ID,
    )

    expect(restored).toEqual([{ id: 1, role: 'user', text: 'Question?' }])
  })

  it('keeps the review and the agents of a saved answer', () => {
    const review = { verdict: 'ok' as const, issues: [], model_checked: true }
    const restored = restoreMessages(
      [
        stored(0, { role: 'user', content: 'Question?' }),
        stored(1, {
          role: 'assistant',
          content: 'Answer.',
          status: 'answered',
          review,
          agent_trace: TRACE,
        }),
      ],
      SESSION_ID,
    )

    const answer = restored[1]
    expect(answer.role === 'assistant' && answer.status === 'done').toBe(true)
    if (answer.role === 'assistant' && answer.status === 'done') {
      expect(answer.response.review).toEqual(review)
      expect(answer.response.agent_trace).toEqual(TRACE)
    }
  })

  it('turns a saved extraction into the same response as a live one', () => {
    const restored = restoreMessages(
      [
        stored(0, { role: 'user', mode: 'extract', content: EXTRACT_RESPONSE.request }),
        stored(1, {
          role: 'assistant',
          mode: 'extract',
          content: EXTRACT_RESPONSE.message,
          status: 'answered',
          extraction: EXTRACTION,
          review: EXTRACT_RESPONSE.review,
          agent_trace: TRACE,
        }),
      ],
      SESSION_ID,
    )

    expect(restored).toEqual([
      { id: 1, role: 'user', text: EXTRACT_RESPONSE.request },
      {
        id: 2,
        role: 'assistant',
        status: 'extracted',
        response: EXTRACT_RESPONSE,
        seconds: null,
        saved: { sessionId: SESSION_ID, messageId: 'message-1' },
      },
    ])
  })

  it('restores the refusal of an unsupported document', () => {
    const restored = restoreMessages(
      [
        stored(0, { role: 'user', mode: 'extract', content: 'Extract the key fields of notes.pdf' }),
        stored(1, {
          role: 'assistant',
          mode: 'extract',
          content: 'This document is neither an invoice nor a contract.',
          status: 'refused',
          refusal_reason: 'unsupported_document',
        }),
      ],
      SESSION_ID,
    )

    const refusal = restored[1]
    expect(refusal.role === 'assistant' && refusal.status === 'extracted').toBe(true)
    if (refusal.role === 'assistant' && refusal.status === 'extracted') {
      expect(refusal.response.status).toBe('refused')
      expect(refusal.response.refusal_reason).toBe('unsupported_document')
      expect(refusal.response.extraction).toBeNull()
    }
  })

  it('skips a saved extraction that lost its fields', () => {
    const restored = restoreMessages(
      [
        stored(0, { role: 'user', mode: 'extract', content: 'Extract' }),
        stored(1, { role: 'assistant', mode: 'extract', content: 'x', status: 'answered' }),
      ],
      SESSION_ID,
    )

    expect(restored).toEqual([{ id: 1, role: 'user', text: 'Extract' }])
  })

  it('keeps where each result is saved, so it can be exported', () => {
    const restored = restoreMessages(
      [
        stored(0, { role: 'user', content: 'First?' }),
        stored(1, { role: 'assistant', content: 'Answer.', status: 'answered' }),
        stored(2, { role: 'user', mode: 'extract', content: 'Extract' }),
        stored(3, {
          role: 'assistant',
          mode: 'extract',
          content: 'x',
          status: 'answered',
          extraction: EXTRACTION,
        }),
      ],
      SESSION_ID,
    )

    const saved = restored.map((message) =>
      message.role === 'assistant' && (message.status === 'done' || message.status === 'extracted')
        ? message.saved
        : null,
    )
    expect(saved).toEqual([
      null,
      { sessionId: SESSION_ID, messageId: 'message-1' },
      null,
      { sessionId: SESSION_ID, messageId: 'message-3' },
    ])
  })

  it('gives an empty conversation for a new session', () => {
    expect(restoreMessages([], SESSION_ID)).toEqual([])
  })
})