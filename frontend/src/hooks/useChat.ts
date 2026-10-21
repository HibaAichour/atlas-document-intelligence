// State of the conversation: the messages, and asking a new question.

import { useReducer, useRef } from 'react'

import { askQuestion } from '../api/client'
import { chatReducer, isWaiting } from '../lib/chat'
import { errorText } from '../lib/errors'
import { useMessages } from '../lib/i18n'

export function useChat(selectedIds: ReadonlySet<string>) {
  const t = useMessages()
  const [messages, dispatch] = useReducer(chatReducer, [])
  // Each message needs a unique key for React; a counter is enough here.
  const nextId = useRef(1)

  async function ask(question: string): Promise<void> {
    const questionId = nextId.current++
    const answerId = nextId.current++
    dispatch({ type: 'asked', questionId, answerId, question })

    const start = performance.now()
    try {
      const response = await askQuestion({ question, document_ids: [...selectedIds] })
      const seconds = (performance.now() - start) / 1000
      dispatch({ type: 'answered', answerId, response, seconds })
    } catch (error) {
      dispatch({ type: 'failed', answerId, error: errorText(error, t.unexpectedError) })
    }
  }

  return { messages, isWaiting: isWaiting(messages), ask }
}