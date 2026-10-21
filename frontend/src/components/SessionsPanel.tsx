import { useState } from 'react'

import type { SessionSummary } from '../api/types'
import type { ListState } from '../hooks/useDocuments'
import { useMessages } from '../lib/i18n'
import { sessionMeta, sessionTitle } from '../lib/sessions'

interface SessionsPanelProps {
  sessions: SessionSummary[]
  listState: ListState
  listError: string | null
  currentId: string | null // null: a new session, not saved yet
  disabled: boolean // true while an answer is generated or a session is opening
  openError: string | null
  onOpen: (sessionId: string) => void
  onNew: () => void
}

export function SessionsPanel({
  sessions,
  listState,
  listError,
  currentId,
  disabled,
  openError,
  onOpen,
  onNew,
}: SessionsPanelProps) {
  const t = useMessages()
  // "Today" and "Yesterday" are computed against the time the page was opened.
  const [now] = useState(() => new Date())
  // A session without messages (its first question failed) is shown as the new
  // session while it is open, and is not listed otherwise.
  const saved = sessions.filter((session) => session.message_count > 0)
  const isDraft = currentId === null || !saved.some((session) => session.id === currentId)
  const lockedHint = disabled ? t.waitBeforeSwitching : undefined

  return (
    <section className="sessions glass" aria-label={t.sessionsTitle}>
      <div className="documents-header">
        <h2 className="documents-title">{t.sessionsTitle}</h2>
        <button
          type="button"
          className="button button-quiet"
          onClick={onNew}
          disabled={disabled || isDraft}
          title={lockedHint}
        >
          {t.newSessionButton}
        </button>
      </div>

      {openError && (
        <p className="message message-error" role="alert">
          {openError}
        </p>
      )}
      {listState === 'error' && (
        <p className="message message-error" role="alert">
          {listError} {t.sessionsErrorHint}
        </p>
      )}
      {listState === 'loading' && <p className="note">{t.loadingSessions}</p>}

      <ul className="session-list">
        {isDraft && (
          <li>
            <div className="session session-current session-draft" aria-current="true">
              <span className="session-title">{t.newSessionTitle}</span>
              <span className="session-meta">{t.newSessionNote}</span>
            </div>
          </li>
        )}
        {saved.map((session) => {
          const isCurrent = session.id === currentId
          const title = sessionTitle(session.title, t)
          return (
            <li key={session.id}>
              <button
                type="button"
                className={isCurrent ? 'session session-current' : 'session'}
                aria-current={isCurrent ? 'true' : undefined}
                onClick={() => onOpen(session.id)}
                disabled={disabled && !isCurrent}
                title={isCurrent ? undefined : (lockedHint ?? title)}
              >
                <span className="session-title">{title}</span>
                <span className="session-meta">{sessionMeta(session, now, t)}</span>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}