import { describe, expect, it } from 'vitest'

import type { DocumentInfo } from '../api/types'
import { chosenDocumentId, extractableDocuments } from './extraction'

function makeDocument(id: string, status: DocumentInfo['status'] = 'ready'): DocumentInfo {
  return {
    id,
    filename: `${id}.pdf`,
    mime_type: 'application/pdf',
    page_count: 1,
    ocr_used: false,
    status,
    error: null,
    created_at: '2026-10-22T10:00:00Z',
  }
}

const DOCUMENTS = [makeDocument('a'), makeDocument('broken', 'failed'), makeDocument('b')]

describe('extractableDocuments', () => {
  it('keeps only the ready documents', () => {
    expect(extractableDocuments(DOCUMENTS).map((document) => document.id)).toEqual(['a', 'b'])
  })
})

describe('chosenDocumentId', () => {
  it('keeps the document the user picked', () => {
    expect(chosenDocumentId(DOCUMENTS, new Set(['a']), 'b')).toBe('b')
  })

  it('offers the first checked document when nothing was picked', () => {
    expect(chosenDocumentId(DOCUMENTS, new Set(['b']), null)).toBe('b')
  })

  it('offers the first ready document when none is checked', () => {
    expect(chosenDocumentId(DOCUMENTS, new Set(), null)).toBe('a')
  })

  it('forgets a pick that can no longer be used', () => {
    expect(chosenDocumentId(DOCUMENTS, new Set(), 'broken')).toBe('a')
    expect(chosenDocumentId(DOCUMENTS, new Set(['b']), 'deleted')).toBe('b')
  })

  it('gives null when no document is ready', () => {
    expect(chosenDocumentId([makeDocument('x', 'processing')], new Set(), null)).toBeNull()
  })
})