// Split an answer into plain text and citation markers, so each marker can be
// rendered as a button. The backend writes every citation as "[file, p. X]"
// and sends the same text in citation.display, so the match is exact.

import type { Citation } from '../api/types'

export type AnswerSegment =
  | { kind: 'text'; text: string }
  | { kind: 'citation'; display: string; citations: Citation[] }

/** Escape the characters that have a special meaning in a regular expression. */
function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function splitAnswer(answer: string, citations: readonly Citation[]): AnswerSegment[] {
  // Several passages can share one marker (two passages of the same page).
  const byDisplay = new Map<string, Citation[]>()
  for (const citation of citations) {
    byDisplay.set(citation.display, [...(byDisplay.get(citation.display) ?? []), citation])
  }
  if (byDisplay.size === 0) {
    return answer === '' ? [] : [{ kind: 'text', text: answer }]
  }

  // Longest markers first, so one marker is never cut by a shorter one.
  const displays = [...byDisplay.keys()].sort((a, b) => b.length - a.length)
  const pattern = new RegExp(displays.map(escapeRegExp).join('|'), 'g')

  const segments: AnswerSegment[] = []
  let last = 0
  for (const match of answer.matchAll(pattern)) {
    const start = match.index
    if (start > last) {
      segments.push({ kind: 'text', text: answer.slice(last, start) })
    }
    segments.push({ kind: 'citation', display: match[0], citations: byDisplay.get(match[0]) ?? [] })
    last = start + match[0].length
  }
  if (last < answer.length) {
    segments.push({ kind: 'text', text: answer.slice(last) })
  }
  return segments
}

/** The label shown on a citation button: "[contract.pdf, p. 4]" becomes "contract.pdf, p. 4". */
export function citationLabel(display: string): string {
  return display.replace(/^\[/, '').replace(/\]$/, '')
}

/** The source opened in the side panel: one marker of one answer. */
export interface OpenSource {
  answerId: number
  display: string
  citations: Citation[]
}