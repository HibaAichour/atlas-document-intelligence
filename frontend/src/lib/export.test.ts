import { describe, expect, it } from 'vitest'

import type { AskResponse } from '../api/types'
import type { ExtractResponse } from './chat'
import { canExportAnswer, canExportExtraction, exportUrl } from './export'

const ANSWER: AskResponse = {
  question: 'How much was invoiced in Q2 2026?',
  status: 'answered',
  answer: 'USD 45,370.00 [review.pptx, p. 5].',
  refusal_reason: null,
  citations: [],
  invalid_citations: [],
  warnings: [],
  best_score: 0.8,
  review: null,
  agent_trace: [],
}

const EXTRACTION: ExtractResponse = {
  request: 'Extract the key fields of invoice.pdf',
  status: 'answered',
  message: 'Extracted 1 of 1 fields.',
  refusal_reason: null,
  extraction: { document_id: 'doc-1', filename: 'invoice.pdf', document_type: 'invoice', fields: [] },
  review: null,
  agent_trace: [],
}

describe('exportUrl', () => {
  it('points to the export route of the saved message, in English by default', () => {
    const saved = { sessionId: 'f21a002e', messageId: 'a4a295bd' }

    expect(exportUrl(saved, 'docx')).toBe(
      '/api/sessions/f21a002e/messages/a4a295bd/export?format=docx&lang=en',
    )
    expect(exportUrl(saved, 'pptx')).toBe(
      '/api/sessions/f21a002e/messages/a4a295bd/export?format=pptx&lang=en',
    )
  })

  it('asks for the file in the language of the interface', () => {
    const saved = { sessionId: 'f21a002e', messageId: 'a4a295bd' }

    expect(exportUrl(saved, 'docx', 'fr')).toBe(
      '/api/sessions/f21a002e/messages/a4a295bd/export?format=docx&lang=fr',
    )
  })

  it('escapes the ids', () => {
    expect(exportUrl({ sessionId: 'a/b', messageId: 'c d' }, 'docx')).toBe(
      '/api/sessions/a%2Fb/messages/c%20d/export?format=docx&lang=en',
    )
  })
})

describe('canExport', () => {
  it('allows an answer, not a refusal', () => {
    expect(canExportAnswer(ANSWER)).toBe(true)
    expect(
      canExportAnswer({ ...ANSWER, status: 'refused', refusal_reason: 'no_relevant_passages' }),
    ).toBe(false)
  })

  it('allows extracted fields, not a refused document', () => {
    expect(canExportExtraction(EXTRACTION)).toBe(true)
    expect(
      canExportExtraction({
        ...EXTRACTION,
        status: 'refused',
        refusal_reason: 'unsupported_document',
        extraction: null,
      }),
    ).toBe(false)
  })
})