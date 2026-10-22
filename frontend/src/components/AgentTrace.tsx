import type { AgentRun } from '../api/types'
import type { Messages } from '../lib/i18n'
import { traceSteps } from '../lib/trace'

interface AgentTraceProps {
  trace: readonly AgentRun[]
  t: Messages
}

/** The agents (and the retrieval tool) that ran for an answer, in order, with their durations. */
export function AgentTrace({ trace, t }: AgentTraceProps) {
  if (trace.length === 0) {
    return null // an answer saved before step 9 has no trace
  }
  const statusText = { ok: null, refused: t.stepRefused, skipped: t.stepSkipped, failed: t.stepFailed }
  return (
    <div className="trace">
      <span className="trace-label">{t.traceLabel}</span>
      <ol className="trace-steps">
        {traceSteps(trace, t).map((step) => (
          <li key={step.key} className={`trace-step trace-${step.status}`}>
            <span className="trace-name">{step.label}</span>
            {step.duration !== null && <span className="trace-time">{step.duration}</span>}
            {statusText[step.status] !== null && (
              <span className="trace-status">{statusText[step.status]}</span>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
