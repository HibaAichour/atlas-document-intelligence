// Turn a failed call to the backend into a text in the language of the interface.
//
// The backend's error messages are in English. The interface knows which
// operation failed and the HTTP status, which tell the cause almost every time,
// so it writes the message itself, as it does for refusals and for the Critic.

import { ApiError } from '../api/client'
import type { LlmProvider } from './config'
import type { Messages } from './i18n'

/** What the interface was doing when the call failed. */
export type Operation =
  | 'listDocuments'
  | 'upload'
  | 'listSessions'
  | 'openSession'
  | 'ask'
  | 'extract'

/** The message for an error of the API, from the operation and the HTTP status.
 *
 * provider tells which language model the deployment uses: a service that is
 * down (503) is explained with Ollama locally, without it in the online demo.
 */
export function apiErrorText(
  error: unknown,
  operation: Operation,
  t: Messages,
  provider: LlmProvider = 'ollama',
): string {
  if (!(error instanceof ApiError)) {
    return t.unexpectedError
  }
  switch (error.status) {
    case 0:
      return t.errorUnreachable
    case 413:
      return t.errorFileTooLarge
    case 403:
      // The online demo refuses uploads (its button is hidden, so this is a safety net).
      return operation === 'upload' ? t.errorUploadsDisabled : t.errorServer(error.status)
    case 400:
      return operation === 'upload' ? t.errorUnsupportedFile : t.errorInvalidRequest
    case 404:
      return t.errorNotFound
    case 409:
      return operation === 'extract' ? t.errorDocumentNotReady : t.errorServer(error.status)
    case 422:
      return t.errorInvalidRequest
    case 429:
      // An online provider's free usage limit was reached (Groq or Gemini).
      return t.errorRateLimited
    case 503:
      return provider === 'ollama' ? t.errorServiceDown : t.errorServiceDownOnline
    default:
      return t.errorServer(error.status)
  }
}