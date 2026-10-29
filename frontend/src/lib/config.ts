// What the interface does with the configuration of the deployment (GET /api/config).

import type { AppConfig } from '../api/types'

/** The configuration, once the request has ended: loaded, or failed. */
export type ConfigState =
  | { kind: 'loading' }
  | { kind: 'loaded'; config: AppConfig }
  | { kind: 'failed' }

/** Whether the "Upload a file" button is shown.
 *
 * Hidden while the configuration is loading: in the online demo, the button
 * would otherwise appear, then disappear. Shown when the request fails: a
 * local backend must stay usable, and the demo backend refuses uploads anyway.
 */
export function uploadsAllowed(state: ConfigState): boolean {
  switch (state.kind) {
    case 'loading':
      return false
    case 'loaded':
      return !state.config.demo_mode
    case 'failed':
      return true
  }
}