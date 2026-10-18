import { useEffect, useState } from 'react'
import './App.css'

type HealthResponse = {
  status: string
  version: string
}

// The three possible states of the backend check.
type BackendState =
  | { kind: 'loading' }
  | { kind: 'online'; data: HealthResponse }
  | { kind: 'offline'; error: string }

function App() {
  const [backend, setBackend] = useState<BackendState>({ kind: 'loading' })

  useEffect(() => {
    // Lets us cancel the request if the component unmounts before it finishes.
    const controller = new AbortController()

    fetch('/api/health', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        return response.json() as Promise<HealthResponse>
      })
      .then((data) => setBackend({ kind: 'online', data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const message = error instanceof Error ? error.message : 'Unknown error'
        setBackend({ kind: 'offline', error: message })
      })

    return () => controller.abort()
  }, [])

  return (
    <main className="page">
      <header>
        <h1>ATLAS</h1>
        <p className="subtitle">Autonomous Multi-Agent Document Intelligence Platform</p>
      </header>

      <section className="status-card" aria-live="polite">
        <h2>Backend status</h2>
        {backend.kind === 'loading' && <p className="status">Checking…</p>}
        {backend.kind === 'online' && (
          <p className="status status-online">Online · API version {backend.data.version}</p>
        )}
        {backend.kind === 'offline' && (
          <p className="status status-offline">Offline · {backend.error}</p>
        )}
      </section>
    </main>
  )
}

export default App