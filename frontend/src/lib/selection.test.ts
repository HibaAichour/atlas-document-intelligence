import { describe, expect, it } from 'vitest'

import type { DocumentInfo, DocumentStatus } from '../api/types'
import {
  restoredSelection,
  selectedIdsOf,
  selectUploaded,
  toggleDocument,
} from './selection'

function doc(id: string, status: DocumentStatus = 'ready'): DocumentInfo {
  return {
    id,
    filename: `${id}.pdf`,
    mime_type: 'application/pdf',
    page_count: 1,
    ocr_used: false,
    status,
    error: status === 'failed' ? 'This file could not be read.' : null,
    created_at: '2026-10-21T10:00:00Z',
  }
}

const DOCUMENTS = [doc('contract'), doc('invoice'), doc('broken', 'failed')]

describe('selectedIdsOf', () => {
  it('uses every usable document for "all"', () => {
    expect(selectedIdsOf('all', DOCUMENTS)).toEqual(new Set(['contract', 'invoice']))
  })

  it('keeps only the chosen documents that are still usable', () => {
    const selection = new Set(['invoice', 'broken', 'deleted-since'])

    expect(selectedIdsOf(selection, DOCUMENTS)).toEqual(new Set(['invoice']))
  })

  it('gives nothing before the documents are loaded', () => {
    expect(selectedIdsOf('all', [])).toEqual(new Set())
  })
})

describe('toggleDocument', () => {
  it('unchecks a document from "all" and keeps the others checked', () => {
    expect(toggleDocument('all', DOCUMENTS, 'contract')).toEqual(new Set(['invoice']))
  })

  it('checks a document that was not checked', () => {
    expect(toggleDocument(new Set(['invoice']), DOCUMENTS, 'contract')).toEqual(
      new Set(['invoice', 'contract']),
    )
  })

  it('does not change the previous selection', () => {
    const before = new Set(['invoice'])

    toggleDocument(before, DOCUMENTS, 'contract')

    expect(before).toEqual(new Set(['invoice']))
  })
})

describe('selectUploaded', () => {
  it('checks a new usable document', () => {
    expect(selectUploaded(new Set(['invoice']), doc('report'))).toEqual(
      new Set(['invoice', 'report']),
    )
  })

  it('leaves "all" as it is: the new document is already included', () => {
    expect(selectUploaded('all', doc('report'))).toBe('all')
  })

  it('does not check a document that failed', () => {
    const selection = new Set(['invoice'])

    expect(selectUploaded(selection, doc('broken', 'failed'))).toBe(selection)
  })
})

describe('restoredSelection', () => {
  it('restores the documents saved with the session', () => {
    expect(restoredSelection(['contract'])).toEqual(new Set(['contract']))
  })

  it('starts a session without saved documents with every document', () => {
    expect(restoredSelection([])).toBe('all')
  })
})