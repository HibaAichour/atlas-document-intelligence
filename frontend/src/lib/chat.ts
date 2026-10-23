// The conversation as a list of messages, updated by a reducer (a pure function
// that returns the next state for an action), so it can be tested without React.

import type {
  AgentRun,
  AnswerStatus,
  AskResponse,
  Extraction,
  MessageMode,
  RefusalReason,
  Review,
  StoredMessage,
} from '../api/types'
import type { SavedRef } from './export'

/** The result of an extraction, as the chat shows it (live or restored). */
export interface ExtractResponse {
  request: string // the user's message, e.g. "Extract the key fields of invoice.pdf"
  status: AnswerStatus
  message: string // the text written by the backend (refusal message if refused)
  refusal_reason: RefusalReason | null
  extraction: Extraction | null // null for a refusal
  review: Review | null
  agent_trace: AgentRun[]
}

export type ChatMessage =
  | { id: number; role: 'user'; text: string }
  // The mode chooses the waiting text: a question or an extraction.
  | { id: number; role: 'assistant'; status: 'pending'; mode: MessageMode }
  // seconds is null for a result restored from a saved session: the time was
  // measured by the browser when the request was sent, and is not saved.
  // saved tells where the result is stored, so it can be exported.
  | {
      id: number
      role: 'assistant'
      status: 'done'
      response: AskResponse
      seconds: number | null
      saved: SavedRef
    }
  | {
      id: number
      role: 'assistant'
      status: 'extracted'
      response: ExtractResponse
      seconds: number | null
      saved: SavedRef
    }
  | { id: number; role: 'assistant'; status: 'error'; error: string }

export type ChatAction =
  | { type: 'asked'; questionId: number; answerId: number; question: string; mode: MessageMode }
  | {
      type: 'answered'
      answerId: number
      response: AskResponse
      seconds: number
      saved: SavedRef
    }
  | {
      type: 'extracted'
      answerId: number
      response: ExtractResponse
      seconds: number
      saved: SavedRef
    }
  | { type: 'failed'; answerId: number; error: string }
  | { type: 'loaded'; messages: ChatMessage[] }

export function chatReducer(messages: ChatMessage[], action: ChatAction): ChatMessage[] {
  switch (action.type) {
    case 'asked':
      return [
        ...messages,
        { id: action.questionId, role: 'user', text: action.question },
        { id: action.answerId, role: 'assistant', status: 'pending', mode: action.mode },
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
              saved: action.saved,
            }
          : message,
      )
    case 'extracted':
      return messages.map((message) =>
        message.id === action.answerId
          ? {
              id: message.id,
              role: 'assistant',
              status: 'extracted',
              response: action.response,
              seconds: action.seconds,
              saved: action.saved,
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

/** True while an answer is being generated: only one request at a time. */
export function isWaiting(messages: readonly ChatMessage[]): boolean {
  return messages.some((message) => message.role === 'assistant' && message.status === 'pending')
}

/** The id to give the next message: one more than the largest id in use. */
export function nextMessageId(messages: readonly ChatMessage[]): number {
  return messages.reduce((largest, message) => Math.max(largest, message.id), 0) + 1
}

/** Turn a saved answer into the AskResponse the chat shows, with its question.
 * Returns null for an assistant message without a status (cannot be shown). */
export function toAskResponse(question: string, message: StoredMessage): AskResponse | null {
  if (message.status === null) {
    return null
  }
  return {
    question,
    status: message.status,
    answer: message.content,
    refusal_reason: message.refusal_reason,
    citations: message.citations,
    invalid_citations: message.invalid_citations,
    warnings: message.warnings,
    best_score: message.best_score,
    review: message.review,
    agent_trace: message.agent_trace,
  }
}

/** Turn a saved extraction into the ExtractResponse the chat shows, with its request.
 * Returns null for a message without a status, or an answer without its fields. */
export function toExtractResponse(request: string, message: StoredMessage): ExtractResponse | null {
  if (message.status === null) {
    return null
  }
  if (message.status === 'answered' && message.extraction === null) {
    return null
  }
  return {
    request,
    status: message.status,
    message: message.content,
    refusal_reason: message.refusal_reason,
    extraction: message.extraction,
    review: message.review,
    agent_trace: message.agent_trace,
  }
}

/** Turn the saved messages of a session into the messages shown in the chat.
 *
 * Each saved answer becomes the same response as a live one, with the request
 * sent just before it, so citations, refusals, extracted fields and warnings
 * are shown by the same code. Ids are position + 1: unique and stable within a
 * session. Each result keeps its saved id, so it can be exported.
 */
export function restoreMessages(
  stored: readonly StoredMessage[],
  sessionId: string,
): ChatMessage[] {
  const ordered = [...stored].sort((a, b) => a.position - b.position)
  const restored: ChatMessage[] = []
  let lastRequest = ''
  for (const message of ordered) {
    const id = message.position + 1
    const saved = { sessionId, messageId: message.id }
    if (message.role === 'user') {
      lastRequest = message.content
      restored.push({ id, role: 'user', text: message.content })
      continue
    }
    // An assistant message that cannot be shown as a result is skipped.
    if (message.mode === 'extract') {
      const response = toExtractResponse(lastRequest, message)
      if (response !== null) {
        restored.push({
          id,
          role: 'assistant',
          status: 'extracted',
          response,
          seconds: null,
          saved,
        })
      }
      continue
    }
    const response = toAskResponse(lastRequest, message)
    if (response !== null) {
      restored.push({ id, role: 'assistant', status: 'done', response, seconds: null, saved })
    }
  }
  return restored
}