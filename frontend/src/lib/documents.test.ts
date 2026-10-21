import { describe, expect, it } from 'vitest'

import type { DocumentInfo } from '../api/types'
import { describeDocument, isUsable, toggleId, usableIds } from './documents'
import { errorText } from './errors'
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

describe('usable documents', () => {
  it('keeps only the documents that are ready', () => {
    const documents = [
      makeDocument({ id: 'a' }),
      makeDocument({ id: 'b', status: 'failed' }),
      makeDocument({ id: 'c', status: 'processing' }),
      makeDocument({ id: 'd' }),
    ]
    expect(usableIds(documents)).toEqual(['a', 'd'])
    expect(isUsable(documents[1])).toBe(false)
  })
})

describe('toggleId', () => {
  it('adds a missing id and removes a present one, without changing the original', () => {
    const original = new Set(['a'])

    expect([...toggleId(original, 'b')]).toEqual(['a', 'b'])
    expect([...toggleId(original, 'a')]).toEqual([])
    expect([...original]).toEqual(['a'])
  })
})

describe('errorText', () => {
  it('uses the message of an error, or the fallback', () => {
    expect(errorText(new Error('Disk full'), 'Fallback')).toBe('Disk full')
    expect(errorText('not an error', 'Fallback')).toBe('Fallback')
    expect(errorText(new Error(''), 'Fallback')).toBe('Fallback')
  })
})