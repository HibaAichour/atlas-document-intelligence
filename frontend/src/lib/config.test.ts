import { describe, expect, it } from 'vitest'

import type { AppConfig } from '../api/types'
import { uploadsAllowed } from './config'

const LOCAL: AppConfig = { demo_mode: false, llm_provider: 'ollama' }
const DEMO: AppConfig = { demo_mode: true, llm_provider: 'openai_compatible' }

describe('uploadsAllowed', () => {
  it('hides the button while the configuration is loading', () => {
    expect(uploadsAllowed({ kind: 'loading' })).toBe(false)
  })

  it('shows it locally and hides it in the online demo', () => {
    expect(uploadsAllowed({ kind: 'loaded', config: LOCAL })).toBe(true)
    expect(uploadsAllowed({ kind: 'loaded', config: DEMO })).toBe(false)
  })

  it('shows it when the configuration cannot be read', () => {
    expect(uploadsAllowed({ kind: 'failed' })).toBe(true)
  })
})