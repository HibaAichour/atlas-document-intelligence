// Shapes of the JSON exchanged with the backend.
// They mirror the Pydantic schemas in backend/app/api/schemas.py: field names
// stay in snake_case, exactly as the API sends them, so nothing is converted.

export type DocumentStatus = 'uploaded' | 'processing' | 'ready' | 'failed'

export interface DocumentInfo {
  id: string
  filename: string
  mime_type: string
  page_count: number
  ocr_used: boolean
  status: DocumentStatus
  error: string | null
  created_at: string // ISO 8601 date, e.g. "2026-10-21T10:41:22.557757Z"
}

export interface HealthInfo {
  status: string
  version: string
}

export interface AskRequest {
  question: string
  top_k?: number
  // Omitted: every document is used. A list limits the answer to those documents.
  document_ids?: string[]
}

export interface Citation {
  label: string // identifier used by the model, e.g. "S1"
  display: string // text shown in the answer, e.g. "[contract.pdf, p. 3]"
  chunk_id: string
  document_id: string
  filename: string
  page_number: number
  position: number
  text: string
  score: number
}

export type AnswerStatus = 'answered' | 'refused'
export type RefusalReason = 'no_relevant_passages' | 'not_found_by_model'
export type AnswerWarning = 'invalid_citations_removed' | 'no_valid_citation'

export interface AskResponse {
  question: string
  status: AnswerStatus
  answer: string // the refusal message when status is "refused"
  refusal_reason: RefusalReason | null
  citations: Citation[]
  invalid_citations: string[]
  warnings: AnswerWarning[]
  best_score: number | null
}