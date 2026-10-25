// Turn a failed call to the backend into a text in the language of the interface.
//
// The backend's error messages are in English. The interface knows which
// operation failed and the HTTP status, which tell the cause almost every time,
// so it writes the message itself, as it does for refusals and for the Critic.

import { ApiError } from '../api/client'
import type { Messages } from './i18n'

/** What the interface was doing when the call failed. */
export type Operation =
  | 'listDocuments'
  | 'upload'
  | 'listSessions'
  | 'openSession'
  | 'ask'
  | 'extract'

/** Return a message that can be shown to the user for any thrown value. */
export function errorText(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message !== '') {
    return error.message
  }
  return fallback
}

/** The message for an error of the API, from the operation and the HTTP status. */
export function apiErrorText(error: unknown, operation: Operation, t: Messages): string {
  if (!(error instanceof ApiError)) {
    return t.unexpectedError
  }
  switch (error.status) {
    case 0:
      return t.errorUnreachable
    case 413:
      return t.errorFileTooLarge
    case 400:
      return operation === 'upload' ? t.errorUnsupportedFile : t.errorInvalidRequest
    case 404:
      return t.errorNotFound
    case 409:
      return operation === 'extract' ? t.errorDocumentNotReady : t.errorServer(error.status)
    case 422:
      return t.errorInvalidRequest
    case 503:
      return t.errorServiceDown
    default:
      return t.errorServer(error.status)
  }
}