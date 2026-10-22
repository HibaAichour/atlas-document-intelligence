import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

import type { AskResponse, DocumentInfo, MessageMode } from '../api/types'
import type { ChatMessage } from '../lib/chat'
import { citationLabel, isOpenAnswerSource, splitAnswer, type OpenSource } from '../lib/citations'
import { chosenDocumentId, extractableDocuments } from '../lib/extraction'
import { useMessages, type Messages } from '../lib/i18n'
import { AgentTrace } from './AgentTrace'
import { CriticReview } from './CriticReview'
import { ExtractionView } from './ExtractionView'

// Same limit as the backend (MAX_QUERY_LENGTH), so a question is never refused.
const MAX_QUESTION_LENGTH = 1000

interface ChatPanelProps {
  messages: ChatMessage[]
  isWaiting: boolean
  canAsk: boolean // false when no usable document is selected
  onAsk: (question: string) => void
  documents: DocumentInfo[]
  selectedIds: ReadonlySet<string> // the checked documents: the first one is offered for extraction
  canExtract: boolean // false while a saved session is being restored
  onExtract: (document: DocumentInfo) => void
  openSource: OpenSource | null
  onOpenSource: (source: OpenSource) => void
}

export function ChatPanel({
  messages,
  isWaiting,
  canAsk,
  onAsk,
  documents,
  selectedIds,
  canExtract,
  onExtract,
  openSource,
  onOpenSource,
}: ChatPanelProps) {
  const t = useMessages()
  const [mode, setMode] = useState<MessageMode>('ask')
  const [draft, setDraft] = useState('')
  // The document the user picked in the list (null: none picked yet).
  const [picked, setPicked] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  const question = draft.trim()
  const extractable = extractableDocuments(documents)
  // Computed, not stored: follows uploads, deletions and the checked documents.
  const documentId = chosenDocumentId(documents, selectedIds, picked)
  const chosen = extractable.find((document) => document.id === documentId)
  const canSend =
    mode === 'ask'
      ? canAsk && !isWaiting && question !== ''
      : canExtract && !isWaiting && chosen !== undefined

  // Keep the latest message in view.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  function send() {
    if (!canSend) return
    if (mode === 'ask') {
      onAsk(question)
      setDraft('')
    } else if (chosen !== undefined) {
      onExtract(chosen)
    }
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
          messages.map((message) => (
            <MessageView
              key={message.id}
              message={message}
              openSource={openSource}
              onOpenSource={onOpenSource}
              t={t}
            />
          ))
        )}
        <div ref={endRef} />
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <div className="mode-switch" role="group" aria-label={t.modeLabel}>
          {(['ask', 'extract'] as const).map((option) => (
            <button
              key={option}
              type="button"
              className={option === mode ? 'mode-option mode-option-on' : 'mode-option'}
              aria-pressed={option === mode}
              onClick={() => setMode(option)}
            >
              {option === 'ask' ? t.modeAsk : t.modeExtract}
            </button>
          ))}
        </div>

        <div className="composer-row">
          {mode === 'ask' ? (
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
          ) : (
            <select
              className="composer-input composer-select"
              value={documentId ?? ''}
              onChange={(event) => setPicked(event.target.value)}
              aria-label={t.extractDocumentLabel}
              disabled={extractable.length === 0}
            >
              {extractable.length === 0 && <option value="">{t.noDocumentToExtract}</option>}
              {extractable.map((document) => (
                <option key={document.id} value={document.id}>
                  {document.filename}
                </option>
              ))}
            </select>
          )}
          <button type="submit" className="button button-primary composer-send" disabled={!canSend}>
            {mode === 'ask' ? t.askButton : t.extractButton}
          </button>
        </div>
        {mode === 'extract' && <p className="composer-hint">{t.extractHint}</p>}
      </form>
    </main>
  )
}

interface MessageViewProps {
  message: ChatMessage
  openSource: OpenSource | null
  onOpenSource: (source: OpenSource) => void
  t: Messages
}

function MessageView({ message, openSource, onOpenSource, t }: MessageViewProps) {
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
        <p className="answer-note">{message.mode === 'extract' ? t.extractPending : t.answerPending}</p>
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
  if (message.status === 'extracted') {
    return (
      <ExtractionView
        answerId={message.id}
        response={message.response}
        seconds={message.seconds}
        openSource={openSource}
        onOpenSource={onOpenSource}
        t={t}
      />
    )
  }
  return (
    <AnswerView
      answerId={message.id}
      response={message.response}
      seconds={message.seconds}
      openSource={openSource}
      onOpenSource={onOpenSource}
      t={t}
    />
  )
}

interface AnswerViewProps {
  answerId: number
  response: AskResponse
  seconds: number | null // null for an answer restored from a saved session
  openSource: OpenSource | null
  onOpenSource: (source: OpenSource) => void
  t: Messages
}

function AnswerView({ answerId, response, seconds, openSource, onOpenSource, t }: AnswerViewProps) {
  // The response time is only known for an answer received in this tab.
  const timing = seconds === null ? null : <> {t.answeredIn(seconds)}</>

  if (response.status === 'refused') {
    const reason =
      response.refusal_reason === 'no_relevant_passages'
        ? t.refusalNoPassages
        : t.refusalNotFound
    return (
      <div className="answer answer-refused">
        <p className="answer-title">{t.refusalTitle}</p>
        <p className="answer-note">
          {reason}
          {timing}
        </p>
        <AgentTrace trace={response.agent_trace} t={t} />
      </div>
    )
  }

  return (
    <div className="answer">
      <p className="answer-text">
        {splitAnswer(response.answer, response.citations).map((segment, index) => {
          if (segment.kind === 'text') {
            return <span key={index}>{segment.text}</span>
          }
          const label = citationLabel(segment.display)
          const isOpen = isOpenAnswerSource(openSource, answerId, segment.display)
          return (
            <button
              key={index}
              type="button"
              className={isOpen ? 'citation citation-open' : 'citation'}
              aria-pressed={isOpen}
              aria-label={t.openSource(label)}
              onClick={() =>
                onOpenSource({
                  kind: 'answer',
                  answerId,
                  display: segment.display,
                  citations: segment.citations,
                })
              }
            >
              {label}
            </button>
          )
        })}
      </p>
      {response.warnings.includes('invalid_citations_removed') && (
        <p className="answer-warning">{t.warningInvalidCitations}</p>
      )}
      {response.warnings.includes('no_valid_citation') && (
        <p className="answer-warning">{t.warningNoCitation}</p>
      )}
      <p className="answer-note">
        {t.sourceCount(response.citations.length)}
        {timing}
      </p>
      <CriticReview review={response.review} t={t} />
      <AgentTrace trace={response.agent_trace} t={t} />
    </div>
  )
}
