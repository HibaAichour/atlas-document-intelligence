// Export of a saved answer or extraction as a Word or PowerPoint file.
// The file is built by the backend from the saved message, so the interface
// only needs to know where that message is saved: its session and its id.

import type { AskResponse } from '../api/types'
import type { ExtractResponse } from './chat'
import type { Language } from './language'

export type ExportFormat = 'docx' | 'pptx'

export const EXPORT_FORMATS: readonly ExportFormat[] = ['docx', 'pptx']

/** Where a result is saved: the session and the id of the assistant message. */
export interface SavedRef {
  sessionId: string
  messageId: string
}

/** The download address of GET /api/sessions/{id}/messages/{id}/export. The
 * language sets the fixed texts of the file (headings, verdict, field labels). */
export function exportUrl(saved: SavedRef, format: ExportFormat, language: Language = 'en'): string {
  const session = encodeURIComponent(saved.sessionId)
  const message = encodeURIComponent(saved.messageId)
  return `/api/sessions/${session}/messages/${message}/export?format=${format}&lang=${language}`
}

/** A refusal has nothing to export (the backend answers 409). */
export function canExportAnswer(response: AskResponse): boolean {
  return response.status === 'answered'
}

export function canExportExtraction(response: ExtractResponse): boolean {
  return response.status === 'answered' && response.extraction !== null
}