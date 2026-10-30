import { describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import type { DocumentInfo } from '../api/types'
import { describeDocument } from './documents'
import { apiErrorText, type Operation } from './errors'
import { dictionaries } from './i18n'

const en = dictionaries.en
const fr = dictionaries.fr

describe('apiErrorText', () => {
  it('writes the cause from the operation and the HTTP status', () => {
    const cases: [number, Operation, string][] = [
      [0, 'ask', en.errorUnreachable],
      [413, 'upload', en.errorFileTooLarge],
      [400, 'upload', en.errorUnsupportedFile],
      [403, 'upload', en.errorUploadsDisabled],
      [403, 'ask', en.errorServer(403)],
      [400, 'ask', en.errorInvalidRequest],
      [404, 'openSession', en.errorNotFound],
      [409, 'extract', en.errorDocumentNotReady],
      [409, 'ask', en.errorServer(409)],
      [422, 'ask', en.errorInvalidRequest],
      [429, 'ask', en.errorRateLimited],
      [429, 'extract', en.errorRateLimited],
      [503, 'ask', en.errorServiceDown],
      [503, 'extract', en.errorServiceDown],
      [500, 'listDocuments', en.errorServer(500)],
    ]
    for (const [status, operation, expected] of cases) {
      expect(apiErrorText(new ApiError(status, 'detail from the backend'), operation, en)).toBe(
        expected,
      )
    }
  })

  it('never shows the English detail of the backend', () => {
    const error = new ApiError(503, 'Embedding request failed: connection refused')

    expect(apiErrorText(error, 'ask', fr)).toBe(
      'Le modèle de langue ou le service de recherche ne répond pas. Ollama est-il lancé\u00a0?',
    )
  })

  it('mentions Ollama for a service that is down only with the local provider', () => {
    const down = new ApiError(503, 'Answer generation failed')

    expect(apiErrorText(down, 'ask', en)).toBe(en.errorServiceDown)
    expect(apiErrorText(down, 'ask', en, 'ollama')).toBe(en.errorServiceDown)
    expect(apiErrorText(down, 'ask', en, 'openai_compatible')).toBe(en.errorServiceDownOnline)
    expect(apiErrorText(down, 'extract', fr, 'openai_compatible')).toBe(
      'Le modèle de langue ou le service de recherche en ligne ne répond pas. Réessayez plus tard.',
    )
    expect(en.errorServiceDownOnline).not.toContain('Ollama')
    expect(fr.errorServiceDownOnline).not.toContain('Ollama')
  })

  it('explains a usage limit the same way with every provider', () => {
    const limited = new ApiError(429, 'The usage limit of the online provider was reached.')

    expect(apiErrorText(limited, 'ask', fr, 'openai_compatible')).toBe(
      'Limite gratuite atteinte, réessayez dans une minute.',
    )
    expect(apiErrorText(limited, 'ask', en, 'ollama')).toBe(
      'Free usage limit reached. Please try again in a minute.',
    )
  })

  it('uses a general message for anything that is not an API error', () => {
    expect(apiErrorText(new TypeError('x is undefined'), 'ask', fr)).toBe(fr.unexpectedError)
    expect(apiErrorText('oops', 'upload', en)).toBe(en.unexpectedError)
  })
})

describe('describeDocument in French', () => {
  const failed: DocumentInfo = {
    id: 'doc-1',
    filename: 'scan.pdf',
    mime_type: 'application/pdf',
    page_count: 0,
    ocr_used: false,
    status: 'failed',
    error: 'The PDF has 60 pages; the limit is 50.',
    created_at: '2026-10-25T10:00:00Z',
  }

  it('frames the reason of a failure, which comes from the backend in English', () => {
    expect(describeDocument(failed, fr)).toBe(
      'Lecture impossible\u00a0: The PDF has 60 pages; the limit is 50.',
    )
    expect(describeDocument(failed, en)).toBe('The PDF has 60 pages; the limit is 50.')
    expect(describeDocument({ ...failed, error: null }, fr)).toBe(fr.unreadableFile)
  })
})