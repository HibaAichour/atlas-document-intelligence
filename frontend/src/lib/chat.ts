// The conversation as a list of messages, updated by a reducer (a pure function
// that returns the next state for an action), so it can be tested without React.

import type { AskResponse, StoredMessage } from '../api/types'

export type ChatMessage =
  | { id: number; role: 'user'; text: string }
  | { id: number; role: 'assistant'; status: 'pending' }
  // seconds is null for an answer restored from a saved session: the time was
  // measured by the browser when the question was asked, and is not saved.
  | {
      id: number
      role: 'assistant'
      status: 'done'
      response: AskResponse
      seconds: number | null
    }
  | { id: number; role: 'assistant'; status: 'error'; error: string }

export type ChatAction =
  | { type: 'asked'; questionId: number; answerId: number; question: string }
  | { type: 'answered'; answerId: number; response: AskResponse; seconds: number }
  | { type: 'failed'; answerId: number; error: string }
  | { type: 'loaded'; messages: ChatMessage[] }

export function chatReducer(messages: ChatMessage[], action: ChatAction): ChatMessage[] {
  switch (action.type) {
    case 'asked':
      return [
        ...messages,
        { id: action.questionId, role: 'user', text: action.question },
        { id: action.answerId, role: 'assistant', status: 'pending' },
      ]
    case 'answered':
      return messages.map((message) =>
        message.id === action.answerId
          ? {
              id: message.id,
              role: 'assistant',
              status: 'done',
              response: action.response,
              seconds: action.seconds,
            }
          : message,
      )
    case 'failed':
      return messages.map((message) =>
        message.id === action.answerId
          ? { id: message.id, role: 'assistant', status: 'error', error: action.error }
          : message,
      )
    case 'loaded':
      // Another session was opened (or a new one started): its messages
      // replace the whole conversation.
      return action.messages
  }
}

/** True while an answer is being generated: only one question at a time. */
export function isWaiting(messages: readonly ChatMessage[]): boolean {
  return messages.some((message) => message.role === 'assistant' && message.status === 'pending')
}

/** The id to give the next message: one more than the largest id in use. */
export function nextMessageId(messages: readonly ChatMessage[]): number {
  return messages.reduce((largest, message) => Math.max(largest, message.id), 0) + 1
}

/** Turn the saved messages of a session into the messages shown in the chat.
 *
 * Each saved answer becomes the same AskResponse as a live answer, with the
 * question asked just before it, so citations, refusals and warnings are shown
 * by the same code. Ids are position + 1: unique and stable within a session.
 */
export function restoreMessages(stored: readonly StoredMessage[]): ChatMessage[] {
  const ordered = [...stored].sort((a, b) => a.position - b.position)
  const restored: ChatMessage[] = []
  let lastQuestion = ''
  for (const message of ordered) {
    const id = message.position + 1
    if (message.role === 'user') {
      lastQuestion = message.content
      restored.push({ id, role: 'user', text: message.content })
    } else if (message.status !== null) {
      restored.push({
        id,
        role: 'assistant',
        status: 'done',
        response: {
          question: lastQuestion,
          status: message.status,
          answer: message.content,
          refusal_reason: message.refusal_reason,
          citations: message.citations,
          invalid_citations: message.invalid_citations,
          warnings: message.warnings,
          best_score: message.best_score,
        },
        seconds: null,
      })
    }
    // An assistant message without a status cannot be shown as an answer: skipped.
  }
  return restored
}