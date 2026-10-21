// The conversation as a list of messages, updated by a reducer (a pure function
// that returns the next state for an action), so it can be tested without React.

import type { AskResponse } from '../api/types'

export type ChatMessage =
  | { id: number; role: 'user'; text: string }
  | { id: number; role: 'assistant'; status: 'pending' }
  | { id: number; role: 'assistant'; status: 'done'; response: AskResponse; seconds: number }
  | { id: number; role: 'assistant'; status: 'error'; error: string }

export type ChatAction =
  | { type: 'asked'; questionId: number; answerId: number; question: string }
  | { type: 'answered'; answerId: number; response: AskResponse; seconds: number }
  | { type: 'failed'; answerId: number; error: string }

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
  }
}

/** True while an answer is being generated: only one question at a time. */
export function isWaiting(messages: readonly ChatMessage[]): boolean {
  return messages.some((message) => message.role === 'assistant' && message.status === 'pending')
}