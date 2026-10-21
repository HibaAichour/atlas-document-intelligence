import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

import type { AskResponse } from '../api/types'
import type { ChatMessage } from '../lib/chat'
import { useMessages, type Messages } from '../lib/i18n'

// Same limit as the backend (MAX_QUERY_LENGTH), so a question is never refused.
const MAX_QUESTION_LENGTH = 1000

interface ChatPanelProps {
  messages: ChatMessage[]
  isWaiting: boolean
  canAsk: boolean // false when no usable document is selected
  onAsk: (question: string) => void
}

export function ChatPanel({ messages, isWaiting, canAsk, onAsk }: ChatPanelProps) {
  const t = useMessages()
  const [draft, setDraft] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const question = draft.trim()
  const canSend = canAsk && !isWaiting && question !== ''

  // Keep the latest message in view.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  function send() {
    if (!canSend) return
    onAsk(question)
    setDraft('')
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    send()
  }

  // Enter sends the question; Shift+Enter starts a new line.
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      send()
    }
  }

  return (
    <main className="conversation glass">
      <div className="messages" aria-live="polite">
        {messages.length === 0 ? (
          <div className="conversation-intro">
            <h1>{t.introTitle}</h1>
            <p>{t.introText}</p>
          </div>
        ) : (
          messages.map((message) => <MessageView key={message.id} message={message} t={t} />)
        )}
        <div ref={endRef} />
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <textarea
          className="composer-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={canAsk ? t.questionPlaceholder : t.selectDocumentFirst}
          aria-label={t.questionLabel}
          maxLength={MAX_QUESTION_LENGTH}
          rows={2}
          disabled={!canAsk}
        />
        <button type="submit" className="button button-primary composer-send" disabled={!canSend}>
          {t.askButton}
        </button>
      </form>
    </main>
  )
}

function MessageView({ message, t }: { message: ChatMessage; t: Messages }) {
  if (message.role === 'user') {
    return <p className="message-question">{message.text}</p>
  }
  if (message.status === 'pending') {
    return (
      <div className="answer answer-pending">
        <span className="pending-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <p className="answer-note">{t.answerPending}</p>
      </div>
    )
  }
  if (message.status === 'error') {
    return (
      <div className="answer answer-error" role="alert">
        <p className="answer-title">{t.answerFailed}</p>
        <p className="answer-note">{message.error}</p>
      </div>
    )
  }
  return <AnswerView response={message.response} seconds={message.seconds} t={t} />
}

function AnswerView({
  response,
  seconds,
  t,
}: {
  response: AskResponse
  seconds: number
  t: Messages
}) {
  const timing = t.answeredIn(seconds)

  if (response.status === 'refused') {
    const reason =
      response.refusal_reason === 'no_relevant_passages'
        ? t.refusalNoPassages
        : t.refusalNotFound
    return (
      <div className="answer answer-refused">
        <p className="answer-title">{t.refusalTitle}</p>
        <p className="answer-note">
          {reason} {timing}
        </p>
      </div>
    )
  }

  return (
    <div className="answer">
      <p className="answer-text">{response.answer}</p>
      {response.warnings.includes('invalid_citations_removed') && (
        <p className="answer-warning">{t.warningInvalidCitations}</p>
      )}
      {response.warnings.includes('no_valid_citation') && (
        <p className="answer-warning">{t.warningNoCitation}</p>
      )}
      <p className="answer-note">
        {t.sourceCount(response.citations.length)} {timing}
      </p>
    </div>
  )
}