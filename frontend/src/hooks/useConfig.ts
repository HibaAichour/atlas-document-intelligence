// The configuration of the deployment, read once when the page loads.

import { useEffect, useState } from 'react'

import { getConfig } from '../api/client'
import type { ConfigState } from '../lib/config'

export function useConfig(): ConfigState {
  const [state, setState] = useState<ConfigState>({ kind: 'loading' })

  useEffect(() => {
    // Cancels the request if the component disappears before it finishes.
    const controller = new AbortController()
    getConfig(controller.signal)
      .then((config) => setState({ kind: 'loaded', config }))
      .catch(() => {
        if (controller.signal.aborted) return
        setState({ kind: 'failed' })
      })
    return () => controller.abort()
  }, [])

  return state
}