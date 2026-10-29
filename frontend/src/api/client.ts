// Every call to the backend goes through this file.
// URLs are relative (/api/...): the Vite proxy (development) or Nginx (Docker)
// forwards them to FastAPI, so the same code works in every environment.

import type {
  AppConfig,
  AskRequest,
  AskResponse,
  DocumentInfo,
  ExtractRequest,
  HealthInfo,
  SessionAskResponse,
  SessionDetail,
  SessionSummary,
} from './types'

/** An API call that failed. The message is safe to show to the user. */
export class ApiError extends Error {
  readonly status: number // HTTP status, or 0 when the server could not be reached

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Turn an error response into a readable message.
 *
 * FastAPI sends {"detail": "..."} for the errors raised by our routes, and
 * {"detail": [{"msg": "..."}]} when a request is invalid (status 422).
 * Nginx sends an HTML page when an upload is too large (status 413).
 */
export function errorMessage(status: number, body: unknown): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const { detail } = body as { detail: unknown }
    if (typeof detail === 'string' && detail.trim() !== '') {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown }
      if (typeof first.msg === 'string') {
        return `Invalid request: ${first.msg}`
      }
    }
  }
  if (status === 413) {
    return 'The file is too large.'
  }
  return `The server returned an error (HTTP ${status}).`
}

/** Read the body as JSON; return the raw text if it is not JSON, null if empty. */
async function readBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (text === '') {
    return null
  }
  try {
    return JSON.parse(text) as unknown
  } catch {
    return text
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch (error) {
    // A cancelled request is not an error to show: let the caller ignore it.
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    throw new ApiError(0, 'The server cannot be reached. Is the backend running?')
  }

  const body = await readBody(response)
  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(response.status, body))
  }
  return body as T
}

/** Options for a request that sends a JSON body. */
function postJson(payload: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }
}

export function getHealth(signal?: AbortSignal): Promise<HealthInfo> {
  return request<HealthInfo>('/api/health', { signal })
}

export function getConfig(signal?: AbortSignal): Promise<AppConfig> {
  return request<AppConfig>('/api/config', { signal })
}

export function listDocuments(signal?: AbortSignal): Promise<DocumentInfo[]> {
  return request<DocumentInfo[]>('/api/documents', { signal })
}

/** Upload one file. Processing is synchronous: this can take a while (OCR). */
export function uploadDocument(file: File): Promise<DocumentInfo> {
  const form = new FormData()
  form.append('file', file)
  // No Content-Type header: the browser sets it, with the multipart boundary.
  return request<DocumentInfo>('/api/documents', { method: 'POST', body: form })
}

/** Ask without saving anything (the chat uses askInSession instead). */
export function askQuestion(payload: AskRequest): Promise<AskResponse> {
  return request<AskResponse>('/api/ask', postJson(payload))
}

/** Every session, most recently used first. */
export function listSessions(signal?: AbortSignal): Promise<SessionSummary[]> {
  return request<SessionSummary[]>('/api/sessions', { signal })
}

/** Create an empty session (its title comes from its first question). */
export function createSession(): Promise<SessionSummary> {
  return request<SessionSummary>('/api/sessions', { method: 'POST' })
}

/** A session with its messages and documents. An unknown id gives an ApiError 404. */
export function getSession(sessionId: string, signal?: AbortSignal): Promise<SessionDetail> {
  return request<SessionDetail>(`/api/sessions/${encodeURIComponent(sessionId)}`, { signal })
}

/** Ask inside a session: the question and its answer are saved by the backend. */
export function askInSession(
  sessionId: string,
  payload: AskRequest,
): Promise<SessionAskResponse> {
  return request<SessionAskResponse>(
    `/api/sessions/${encodeURIComponent(sessionId)}/ask`,
    postJson(payload),
  )
}
/** Extract the key fields of one document inside a session; the backend saves the result. */
export function extractInSession(
  sessionId: string,
  payload: ExtractRequest,
): Promise<SessionAskResponse> {
  return request<SessionAskResponse>(
    `/api/sessions/${encodeURIComponent(sessionId)}/extract`,
    postJson(payload),
  )
}