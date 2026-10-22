// The agents that ran for an answer, as the chat shows them under it.
// The texts come from the dictionary, never from the backend's technical summary.

import type { AgentRun } from '../api/types'
import type { Messages } from './i18n'

export interface TraceStep {
  key: string // unique within one trace, for React
  label: string // e.g. "Writer"
  status: AgentRun['status']
  duration: string | null // null for a step that did not run
}

/** "< 1 ms" for a step faster than a millisecond (code checks), "4 ms" under
 * one second, "3.3 s" above. "0 ms" would suggest that the step did nothing. */
export function formatDuration(milliseconds: number): string {
  if (milliseconds < 1) {
    return '< 1 ms'
  }
  if (milliseconds < 1000) {
    return `${Math.round(milliseconds)} ms`
  }
  return `${(milliseconds / 1000).toFixed(1)} s`
}

/** The steps of a trace in the order they ran, with their labels and durations. */
export function traceSteps(trace: readonly AgentRun[], t: Messages): TraceStep[] {
  return trace.map((run, index) => ({
    key: `${index}-${run.name}`,
    label: t.agentNames[run.name] ?? run.name,
    status: run.status,
    duration: run.status === 'skipped' ? null : formatDuration(run.duration_ms),
  }))
}