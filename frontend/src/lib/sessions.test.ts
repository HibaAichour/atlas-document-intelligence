import { describe, expect, it } from 'vitest'

import type { SessionSummary } from '../api/types'
import { dictionaries } from './i18n'
import {
  CURRENT_SESSION_KEY,
  formatSessionDate,
  readCurrentSessionId,
  saveCurrentSessionId,
  sessionMeta,
  sessionTitle,
  upsertSession,
  type KeyValueStore,
} from './sessions'

const t = dictionaries.en

/** An in-memory stand-in for localStorage. */
function fakeStorage(): KeyValueStore & { values: Map<string, string> } {
  const values = new Map<string, string>()
  return {
    values,
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => void values.set(key, value),
    removeItem: (key) => void values.delete(key),
  }
}

/** A storage that refuses everything, like a browser with storage blocked. */
const brokenStorage: KeyValueStore = {
  getItem: () => {
    throw new Error('SecurityError')
  },
  setItem: () => {
    throw new Error('QuotaExceededError')
  },
  removeItem: () => {
    throw new Error('SecurityError')
  },
}

function summary(id: string, fields: Partial<SessionSummary> = {}): SessionSummary {
  return {
    id,
    title: `Session ${id}`,
    created_at: '2026-10-20T09:00:00Z',
    updated_at: '2026-10-20T09:00:00Z',
    message_count: 2,
    ...fields,
  }
}

// Dates built from local parts, so the tests pass in any time zone.
const NOW = new Date(2026, 9, 21, 18, 30)

describe('current session id', () => {
  it('is saved, read back and forgotten', () => {
    const storage = fakeStorage()

    saveCurrentSessionId('session-1', storage)
    expect(readCurrentSessionId(storage)).toBe('session-1')
    expect(storage.values.get(CURRENT_SESSION_KEY)).toBe('session-1')

    saveCurrentSessionId(null, storage)
    expect(readCurrentSessionId(storage)).toBeNull()
  })

  it('is null when nothing was saved', () => {
    expect(readCurrentSessionId(fakeStorage())).toBeNull()
  })

  it('never throws when the storage is blocked or missing', () => {
    expect(readCurrentSessionId(brokenStorage)).toBeNull()
    expect(() => saveCurrentSessionId('session-1', brokenStorage)).not.toThrow()
    expect(readCurrentSessionId(null)).toBeNull()
    expect(() => saveCurrentSessionId(null, null)).not.toThrow()
  })
})

describe('sessionTitle', () => {
  it('uses the saved title', () => {
    expect(sessionTitle('What is the notice period?', t)).toBe('What is the notice period?')
  })

  it('names a session without a title', () => {
    expect(sessionTitle(null, t)).toBe('Untitled session')
  })
})

describe('formatSessionDate', () => {
  it('shows the time for today', () => {
    const date = new Date(2026, 9, 21, 18, 12).toISOString()

    expect(formatSessionDate(date, NOW, t)).toBe('Today, 18:12')
  })

  it('says "Yesterday" for the day before, even just after midnight', () => {
    const date = new Date(2026, 9, 20, 23, 50).toISOString()
    const justAfterMidnight = new Date(2026, 9, 21, 0, 5)

    expect(formatSessionDate(date, justAfterMidnight, t)).toBe('Yesterday')
  })

  it('shows day and month earlier in the year', () => {
    const date = new Date(2026, 9, 19, 10, 0).toISOString()

    expect(formatSessionDate(date, NOW, t)).toBe('19 Oct')
  })

  it('adds the year for an older session', () => {
    const date = new Date(2025, 11, 3, 10, 0).toISOString()

    expect(formatSessionDate(date, NOW, t)).toBe('3 Dec 2025')
  })
})

describe('sessionMeta', () => {
  it('combines the message count and the date', () => {
    const session = summary('a', {
      message_count: 4,
      updated_at: new Date(2026, 9, 21, 18, 12).toISOString(),
    })

    expect(sessionMeta(session, NOW, t)).toBe('4 messages · Today, 18:12')
  })
})

describe('upsertSession', () => {
  it('adds a new session at the top', () => {
    const list = [summary('a'), summary('b')]

    expect(upsertSession(list, summary('c')).map((s) => s.id)).toEqual(['c', 'a', 'b'])
  })

  it('moves an updated session to the top without duplicating it', () => {
    const list = [summary('a'), summary('b')]
    const updated = summary('b', { message_count: 4 })

    const result = upsertSession(list, updated)

    expect(result.map((s) => s.id)).toEqual(['b', 'a'])
    expect(result[0].message_count).toBe(4)
    expect(list.map((s) => s.id)).toEqual(['a', 'b'])
  })
})