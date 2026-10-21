// State of the session list: loading it, opening a session, starting a new one,
// and remembering the open session so that a reload brings it back.

import { useEffect, useLayoutEffect, useRef, useState } from 'react'

import { ApiError, createSession, getSession, listSessions } from '../api/client'
import type { SessionDetail, SessionSummary } from '../api/types'
import { errorText } from '../lib/errors'
import { useMessages } from '../lib/i18n'
import { readCurrentSessionId, saveCurrentSessionId, upsertSession } from '../lib/sessions'
import type { ListState } from './useDocuments'

/** Called when a saved session has been opened, or with null when a new one starts. */
export type OnSessionOpened = (session: SessionDetail | null) => void

export function useSessions(onOpened: OnSessionOpened) {
  const t = useMessages()
  // The session open at the last visit, read once when the page loads.
  const [initialId] = useState(readCurrentSessionId)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [listState, setListState] = useState<ListState>('loading')
  const [listError, setListError] = useState<string | null>(null)
  // null: a new session, created on the backend with its first question.
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [isOpening, setIsOpening] = useState(initialId !== null)
  const [openError, setOpenError] = useState<string | null>(null)

  // Always call the latest onOpened, even from the request started at load time.
  const onOpenedRef = useRef(onOpened)
  useLayoutEffect(() => {
    onOpenedRef.current = onOpened
  })

  useEffect(() => {
    // Cancels both requests if the component disappears before they finish.
    const controller = new AbortController()

    listSessions(controller.signal)
      .then((items) => {
        setSessions(items)
        setListState('loaded')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setListError(errorText(error, t.unexpectedError))
        setListState('error')
      })

    if (initialId !== null) {
      getSession(initialId, controller.signal)
        .then((session) => {
          setCurrentId(session.id)
          onOpenedRef.current(session)
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) return
          if (error instanceof ApiError && error.status === 404) {
            // The session no longer exists: start a new one, and forget it.
            saveCurrentSessionId(null)
          } else {
            // Backend down: keep the id, so the next reload can try again.
            setOpenError(`${t.sessionOpenFailed} ${errorText(error, t.unexpectedError)}`)
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsOpening(false)
        })
    }
    return () => controller.abort()
  }, [initialId, t])

  /** Open a saved session: its messages and documents replace the current ones. */
  async function open(sessionId: string): Promise<void> {
    if (sessionId === currentId || isOpening) return
    setIsOpening(true)
    setOpenError(null)
    try {
      const session = await getSession(sessionId)
      setCurrentId(session.id)
      saveCurrentSessionId(session.id)
      onOpened(session)
    } catch (error) {
      setOpenError(`${t.sessionOpenFailed} ${errorText(error, t.unexpectedError)}`)
    } finally {
      setIsOpening(false)
    }
  }

  /** Start a new, empty session. Nothing is saved until its first question. */
  function startNew(): void {
    setCurrentId(null)
    setOpenError(null)
    saveCurrentSessionId(null)
    onOpened(null)
  }

  /** The id of the session to ask in, created on the backend if it is a new one. */
  async function ensureSession(): Promise<string> {
    if (currentId !== null) return currentId
    const session = await createSession()
    setCurrentId(session.id)
    saveCurrentSessionId(session.id)
    return session.id
  }

  /** Show the session as updated (title, message count, date) after a question. */
  function saved(session: SessionSummary): void {
    setSessions((current) => upsertSession(current, session))
  }

  return {
    sessions,
    listState,
    listError,
    currentId,
    isOpening,
    openError,
    open,
    startNew,
    ensureSession,
    saved,
  }
}