// Small pure helpers for the session list and for remembering the open session.

import type { SessionSummary } from '../api/types'
import type { Messages } from './i18n'

/** Key under which the browser remembers the open session between visits. */
export const CURRENT_SESSION_KEY = 'atlas.currentSessionId'

/** The part of localStorage used here, so tests can pass a fake. */
export type KeyValueStore = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

/** The browser's localStorage, or null where it cannot be used (blocked by a
 * privacy setting, or no browser at all as in the tests). */
function browserStorage(): KeyValueStore | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** The id of the session open at the last visit, or null. */
export function readCurrentSessionId(
  storage: KeyValueStore | null = browserStorage(),
): string | null {
  try {
    return storage?.getItem(CURRENT_SESSION_KEY) ?? null
  } catch {
    return null
  }
}

/** Remember the open session (null: a new, unsaved session). Never throws:
 * without storage the app still works, it just opens a new session next time. */
export function saveCurrentSessionId(
  sessionId: string | null,
  storage: KeyValueStore | null = browserStorage(),
): void {
  try {
    if (sessionId === null) {
      storage?.removeItem(CURRENT_SESSION_KEY)
    } else {
      storage?.setItem(CURRENT_SESSION_KEY, sessionId)
    }
  } catch {
    // Storage full or blocked: nothing to do.
  }
}

/** The title shown for a session ("Untitled session" if it has none yet). */
export function sessionTitle(title: string | null, t: Messages): string {
  return title ?? t.untitledSession
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

/** When a session was last used: "Today, 18:12", "Yesterday", "19 Oct" or
 * "19 Oct 2025", in the user's time zone. */
export function formatSessionDate(isoDate: string, now: Date, t: Messages): string {
  const date = new Date(isoDate)
  if (sameDay(date, now)) {
    const time = new Intl.DateTimeFormat(t.dateLocale, {
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
    return t.today(time)
  }
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1)
  if (sameDay(date, yesterday)) {
    return t.yesterday
  }
  return new Intl.DateTimeFormat(t.dateLocale, {
    day: 'numeric',
    month: 'short',
    year: date.getFullYear() === now.getFullYear() ? undefined : 'numeric',
  }).format(date)
}

/** The line under a session title: "4 messages · Today, 18:12". */
export function sessionMeta(session: SessionSummary, now: Date, t: Messages): string {
  return `${t.messageCount(session.message_count)} · ${formatSessionDate(session.updated_at, now, t)}`
}

/** Put a new or updated session at the top of the list (most recent first). */
export function upsertSession(
  sessions: readonly SessionSummary[],
  session: SessionSummary,
): SessionSummary[] {
  return [session, ...sessions.filter((item) => item.id !== session.id)]
}