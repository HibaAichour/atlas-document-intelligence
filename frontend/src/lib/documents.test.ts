import { describe, expect, it } from 'vitest'

import type { DocumentInfo } from '../api/types'
import { describeDocument, isUsable } from './documents'
import { dictionaries } from './i18n'

const t = dictionaries.en

function makeDocument(overrides: Partial<DocumentInfo>): DocumentInfo {
  return {
    id: 'doc-1',
    filename: 'contract.pdf',
    mime_type: 'application/pdf',
    page_count: 6,
    ocr_used: false,
    status: 'ready',
    error: null,
    created_at: '2026-10-21T10:41:22Z',
    ...overrides,
  }
}

describe('describeDocument', () => {
  it('gives the number of pages', () => {
    expect(describeDocument(makeDocument({ page_count: 6 }), t)).toBe('6 pages')
    expect(describeDocument(makeDocument({ page_count: 1 }), t)).toBe('1 page')
  })

  it('says when OCR was used', () => {
    expect(describeDocument(makeDocument({ page_count: 1, ocr_used: true }), t)).toBe(
      '1 page, read with OCR',
    )
  })

  it('shows the reason of a failure', () => {
    const failed = makeDocument({ status: 'failed', error: 'No text found on any page.' })
    expect(describeDocument(failed, t)).toBe('No text found on any page.')
    expect(describeDocument(makeDocument({ status: 'failed' }), t)).toBe(
      'This file could not be read.',
    )
  })

  it('shows a document that is still being processed', () => {
    expect(describeDocument(makeDocument({ status: 'processing' }), t)).toBe('Processing…')
  })
})

describe('isUsable', () => {
  it('accepts only the documents that are ready', () => {
    expect(isUsable(makeDocument({}))).toBe(true)
    expect(isUsable(makeDocument({ status: 'failed' }))).toBe(false)
    expect(isUsable(makeDocument({ status: 'processing' }))).toBe(false)
  })
})