import { describe, expect, it } from 'vitest'

import type { AgentRun } from '../api/types'
import { dictionaries } from './i18n'
import { formatDuration, traceSteps } from './trace'

const t = dictionaries.en

function run(name: string, status: AgentRun['status'], duration_ms: number): AgentRun {
  return { name, kind: name === 'retrieval' ? 'tool' : 'agent', status, duration_ms, summary: 'x' }
}

describe('formatDuration', () => {
  it('writes "< 1 ms" rather than "0 ms" for a step faster than a millisecond', () => {
    expect(formatDuration(0)).toBe('< 1 ms')
    expect(formatDuration(0.4)).toBe('< 1 ms')
    expect(formatDuration(1)).toBe('1 ms')
  })

  it('writes milliseconds under one second', () => {
    expect(formatDuration(4)).toBe('4 ms')
    expect(formatDuration(142.6)).toBe('143 ms')
    expect(formatDuration(999)).toBe('999 ms')
  })

  it('writes seconds with one decimal above', () => {
    expect(formatDuration(1000)).toBe('1.0 s')
    expect(formatDuration(3306)).toBe('3.3 s')
    // The decimal separator follows the language of the interface.
    expect(formatDuration(3306, 'fr-FR')).toBe('3,3 s')
  })
})

describe('traceSteps', () => {
  it('keeps the order of the plan and names each step from the dictionary', () => {
    const steps = traceSteps(
      [run('retrieval', 'ok', 142), run('writer', 'ok', 5230), run('critic', 'ok', 2410)],
      t,
    )

    expect(steps.map((step) => [step.label, step.status, step.duration])).toEqual([
      ['Retrieval', 'ok', '142 ms'],
      ['Writer', 'ok', '5.2 s'],
      ['Critic', 'ok', '2.4 s'],
    ])
  })

  it('gives no duration to a step that did not run', () => {
    const steps = traceSteps([run('analyst', 'refused', 1720), run('extractor', 'skipped', 0)], t)

    expect(steps[0]).toMatchObject({ label: 'Document Analyst', status: 'refused', duration: '1.7 s' })
    expect(steps[1]).toMatchObject({ label: 'Extractor', status: 'skipped', duration: null })
  })

  it('shows the name of an agent the dictionary does not know', () => {
    expect(traceSteps([run('planner', 'ok', 10)], t)[0].label).toBe('planner')
  })

  it('gives each step a unique key, even when a name repeats', () => {
    const steps = traceSteps([run('critic', 'ok', 1), run('critic', 'ok', 2)], t)

    expect(new Set(steps.map((step) => step.key)).size).toBe(2)
  })
})