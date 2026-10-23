// State of the conversation: the messages, asking a question or extracting the
// fields of a document inside the current session, and showing the messages of
// a session that was opened.

import { useReducer, useRef } from 'react'

import { askInSession, extractInSession } from '../api/client'
import type { DocumentInfo, SessionSummary } from '../api/types'
import {
  chatReducer,
  isWaiting,
  nextMessageId,
  toAskResponse,
  toExtractResponse,
  type ChatMessage,
} from '../lib/chat'
import { errorText } from '../lib/errors'
import { useMessages } from '../lib/i18n'

interface ChatOptions {
  selectedIds: ReadonlySet<string>
  // Returns the id of the session to ask in (created on the backend if needed).
  ensureSession: () => Promise<string>
  // Called with the updated session (title, message count) once the answer is saved.
  onSaved: (session: SessionSummary) => void
}

export function useChat({ selectedIds, ensureSession, onSaved }: ChatOptions) {
  const t = useMessages()
  const [messages, dispatch] = useReducer(chatReducer, [])
  // Each message needs a unique key for React; a counter is enough here.
  const nextId = useRef(1)

  async function ask(question: string): Promise<void> {
    const questionId = nextId.current++
    const answerId = nextId.current++
    dispatch({ type: 'asked', questionId, answerId, question, mode: 'ask' })

    const start = performance.now()
    try {
      const sessionId = await ensureSession()
      const saved = await askInSession(sessionId, {
        question,
        document_ids: [...selectedIds],
      })
      const seconds = (performance.now() - start) / 1000
      const response = toAskResponse(saved.question.content, saved.answer)
      if (response === null) {
        throw new Error(t.unexpectedError)
      }
      const ref = { sessionId, messageId: saved.answer.id }
      dispatch({ type: 'answered', answerId, response, seconds, saved: ref })
      onSaved(saved.session)
    } catch (error) {
      dispatch({ type: 'failed', answerId, error: errorText(error, t.unexpectedError) })
    }
  }

  /** Extract the key fields of one document; the result is saved in the session. */
  async function extract(document: DocumentInfo): Promise<void> {
    const requestId = nextId.current++
    const answerId = nextId.current++
    // The backend saves the same text; it is written here to show it at once.
    const request = t.extractRequest(document.filename)
    dispatch({ type: 'asked', questionId: requestId, answerId, question: request, mode: 'extract' })

    const start = performance.now()
    try {
      const sessionId = await ensureSession()
      const saved = await extractInSession(sessionId, { document_id: document.id })
      const seconds = (performance.now() - start) / 1000
      const response = toExtractResponse(saved.question.content, saved.answer)
      if (response === null) {
        throw new Error(t.unexpectedError)
      }
      const ref = { sessionId, messageId: saved.answer.id }
      dispatch({ type: 'extracted', answerId, response, seconds, saved: ref })
      onSaved(saved.session)
    } catch (error) {
      dispatch({ type: 'failed', answerId, error: errorText(error, t.unexpectedError) })
    }
  }

  /** Replace the conversation with the messages of another session (or none). */
  function load(loaded: ChatMessage[]): void {
    dispatch({ type: 'loaded', messages: loaded })
    // New messages get ids after the restored ones, so React keys stay unique.
    nextId.current = nextMessageId(loaded)
  }

  return { messages, isWaiting: isWaiting(messages), ask, extract, load }
}