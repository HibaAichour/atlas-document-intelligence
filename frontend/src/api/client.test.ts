import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, askQuestion, errorMessage, listDocuments, uploadDocument } from './client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** Replace fetch with a fake that returns the given response and records calls. */
function mockFetch(response: Response | Error) {
  const fake = vi.fn(async () => {
    if (response instanceof Error) {
      throw response
    }
    return response
  })
  vi.stubGlobal('fetch', fake)
  return fake
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('errorMessage', () => {
  it('uses the detail sent by our routes', () => {
    expect(errorMessage(503, { detail: 'Search failed: connection refused' })).toBe(
      'Search failed: connection refused',
    )
  })

  it('uses the first validation error of a 422 response', () => {
    const body = { detail: [{ msg: 'String should have at least 1 character' }] }
    expect(errorMessage(422, body)).toBe(
      'Invalid request: String should have at least 1 character',
    )
  })

  it('explains the HTML page Nginx sends for a file that is too large', () => {
    expect(errorMessage(413, '<html>413 Request Entity Too Large</html>')).toBe(
      'The file is too large.',
    )
  })

  it('falls back to the status code', () => {
    expect(errorMessage(500, null)).toBe('The server returned an error (HTTP 500).')
    expect(errorMessage(502, { detail: '' })).toBe('The server returned an error (HTTP 502).')
  })
})

describe('API calls', () => {
  it('lists the documents', async () => {
    const fake = mockFetch(jsonResponse(200, [{ id: 'doc-1', filename: 'a.pdf' }]))

    const documents = await listDocuments()

    expect(documents).toEqual([{ id: 'doc-1', filename: 'a.pdf' }])
    expect(fake).toHaveBeenCalledWith('/api/documents', { signal: undefined })
  })

  it('uploads the file as multipart form data in the "file" field', async () => {
    const fake = mockFetch(jsonResponse(201, { id: 'doc-1', status: 'ready' }))
    const file = new File(['hello'], 'contract.pdf', { type: 'application/pdf' })

    await uploadDocument(file)

    const [path, init] = fake.mock.calls[0] as unknown as [string, RequestInit]
    expect(path).toBe('/api/documents')
    expect(init.method).toBe('POST')
    expect(init.headers).toBeUndefined()
    expect((init.body as FormData).get('file')).toBeInstanceOf(File)
  })

  it('sends the question as JSON', async () => {
    const fake = mockFetch(jsonResponse(200, { status: 'refused' }))

    await askQuestion({ question: 'Notice period?', document_ids: ['doc-1'] })

    const [path, init] = fake.mock.calls[0] as unknown as [string, RequestInit]
    expect(path).toBe('/api/ask')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({
      question: 'Notice period?',
      document_ids: ['doc-1'],
    })
  })

  it('turns an error response into an ApiError with the backend message', async () => {
    mockFetch(jsonResponse(503, { detail: 'Answer generation failed: timeout' }))

    const error = await askQuestion({ question: 'x' }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(503)
    expect((error as ApiError).message).toBe('Answer generation failed: timeout')
  })

  it('reports a server that cannot be reached', async () => {
    mockFetch(new TypeError('Failed to fetch'))

    const error = await listDocuments().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(0)
    expect((error as ApiError).message).toContain('cannot be reached')
  })

  it('lets a cancelled request through, so the caller can ignore it', async () => {
    mockFetch(new DOMException('The operation was aborted.', 'AbortError'))

    const error = await listDocuments().catch((caught: unknown) => caught)

    expect(error).not.toBeInstanceOf(ApiError)
    expect((error as DOMException).name).toBe('AbortError')
  })
})