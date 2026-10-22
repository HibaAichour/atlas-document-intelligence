import { describe, expect, it } from 'vitest'

import type { Citation } from '../api/types'
import {
  citationLabel,
  isOpenAnswerSource,
  isOpenFieldSource,
  splitAnswer,
  type OpenSource,
} from './citations'

function makeCitation(label: string, page: number, filename = 'contract.pdf'): Citation {
  return {
    label,
    display: `[${filename}, p. ${page}]`,
    chunk_id: `chunk-${label}`,
    document_id: 'doc-1',
    filename,
    page_number: page,
    position: 0,
    text: `Text of ${label}`,
    score: 0.8,
  }
}

describe('splitAnswer', () => {
  it('returns the whole text when there is no citation', () => {
    expect(splitAnswer('No source here.', [])).toEqual([{ kind: 'text', text: 'No source here.' }])
    expect(splitAnswer('', [])).toEqual([])
  })

  it('cuts the answer around a citation marker', () => {
    const s1 = makeCitation('S1', 4)

    expect(splitAnswer('The notice is 60 days [contract.pdf, p. 4].', [s1])).toEqual([
      { kind: 'text', text: 'The notice is 60 days ' },
      { kind: 'citation', display: '[contract.pdf, p. 4]', citations: [s1] },
      { kind: 'text', text: '.' },
    ])
  })

  it('finds every occurrence of the same marker', () => {
    const s1 = makeCitation('S1', 4)
    const segments = splitAnswer('A [contract.pdf, p. 4]. B [contract.pdf, p. 4].', [s1])

    expect(segments.filter((segment) => segment.kind === 'citation')).toHaveLength(2)
  })

  it('groups the passages that share a page under one marker', () => {
    const s1 = makeCitation('S1', 4)
    const s2 = makeCitation('S2', 4)
    const segments = splitAnswer('Fees [contract.pdf, p. 4]', [s1, s2])

    expect(segments[1]).toEqual({
      kind: 'citation',
      display: '[contract.pdf, p. 4]',
      citations: [s1, s2],
    })
  })

  it('keeps different sources apart, even when one name contains the other', () => {
    const short = makeCitation('S1', 1)
    const long = makeCitation('S2', 12)
    const other = makeCitation('S3', 1, 'invoice (scan).png')
    const answer = 'One [contract.pdf, p. 1]. Two [contract.pdf, p. 12]. Three [invoice (scan).png, p. 1].'

    const markers = splitAnswer(answer, [short, long, other]).filter(
      (segment) => segment.kind === 'citation',
    )

    expect(markers.map((marker) => marker.citations[0].label)).toEqual(['S1', 'S2', 'S3'])
  })
})

describe('citationLabel', () => {
  it('removes the square brackets', () => {
    expect(citationLabel('[contract.pdf, p. 4]')).toBe('contract.pdf, p. 4')
  })
})

describe('isOpenAnswerSource and isOpenFieldSource', () => {
  const answer: OpenSource = {
    kind: 'answer',
    answerId: 2,
    display: '[contract.pdf, p. 4]',
    citations: [makeCitation('S1', 4)],
  }
  const field: OpenSource = {
    kind: 'field',
    answerId: 6,
    field: 'total_amount',
    label: 'Total due',
    value: '15,950.00',
    citations: [makeCitation('total_amount', 1, 'invoice.pdf')],
  }

  it('recognises the marker of an answer that is open', () => {
    expect(isOpenAnswerSource(answer, 2, '[contract.pdf, p. 4]')).toBe(true)
    expect(isOpenAnswerSource(answer, 4, '[contract.pdf, p. 4]')).toBe(false)
    expect(isOpenAnswerSource(null, 2, '[contract.pdf, p. 4]')).toBe(false)
  })

  it('opens one field only, even when several fields share a page', () => {
    expect(isOpenFieldSource(field, 6, 'total_amount')).toBe(true)
    expect(isOpenFieldSource(field, 6, 'currency')).toBe(false)
  })

  it('never mixes a field with an answer marker', () => {
    expect(isOpenAnswerSource(field, 6, '[invoice.pdf, p. 1]')).toBe(false)
    expect(isOpenFieldSource(answer, 2, 'total_amount')).toBe(false)
  })
})