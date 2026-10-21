import { useEffect, useState } from 'react'

import { getHealth } from '../api/client'
import { useMessages } from '../lib/i18n'

type Health = { kind: 'checking' } | { kind: 'online'; version: string } | { kind: 'offline' }

/** Small indicator in the header: can the frontend reach the backend? */
export function HealthStatus() {
  const t = useMessages()
  const [health, setHealth] = useState<Health>({ kind: 'checking' })

  useEffect(() => {
    const controller = new AbortController()
    getHealth(controller.signal)
      .then((info) => setHealth({ kind: 'online', version: info.version }))
      .catch(() => {
        if (controller.signal.aborted) return
        setHealth({ kind: 'offline' })
      })
    return () => controller.abort()
  }, [])

  return (
    <p className={`health health-${health.kind}`} aria-live="polite">
      <span className="health-dot" aria-hidden="true" />
      {health.kind === 'checking' && t.healthChecking}
      {health.kind === 'online' && t.healthOnline(health.version)}
      {health.kind === 'offline' && t.healthOffline}
    </p>
  )
}