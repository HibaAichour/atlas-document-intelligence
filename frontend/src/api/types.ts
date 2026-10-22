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
// "unsupported_document": an extraction on a document that is neither an
// invoice nor a contract.
export type RefusalReason = 'no_relevant_passages' | 'not_found_by_model' | 'unsupported_document'
export type AnswerWarning = 'invalid_citations_removed' | 'no_valid_citation'

/** One step of the Orchestrator's plan: which agent or tool ran, and how (AgentRunOut). */
export interface AgentRun {
  name: string // "retrieval", "writer", "critic", "analyst", "extractor"
  kind: 'agent' | 'tool' // an agent calls the LLM, a tool does not
  status: 'ok' | 'refused' | 'skipped' | 'failed'
  duration_ms: number
  summary: string // short technical note in English, not shown as such
}

export type IssueCode =
  | 'invented_citations'
  | 'no_citation'
  | 'uncited_sentence'
  | 'unsupported_number'
  | 'unsupported_claim'
  | 'missing_required_field'
  | 'value_not_found'
  | 'wrong_page'
  | 'unreadable_date'
  | 'unreadable_amount'

/** One problem the Critic found (IssueOut). */
export interface Issue {
  code: IssueCode
  origin: 'code' | 'model' // a rule of the code (certain) or the model's judgement (to check)
  message: string // short technical note in English, not shown as such
  sentence: string | null // the sentence concerned, for an answer
  field: string | null // the field concerned, for an extraction
}

/** The Critic's verdict (ReviewOut). It reports problems, it never changes the answer. */
export interface Review {
  verdict: 'ok' | 'issues'
  issues: Issue[]
  model_checked: boolean // false when only the code checks ran
}

export interface AskResponse {
  question: string
  status: AnswerStatus
  answer: string // the refusal message when status is "refused"
  refusal_reason: RefusalReason | null
  citations: Citation[]
  invalid_citations: string[]
  warnings: AnswerWarning[]
  best_score: number | null
  review: Review | null // null for a refusal
  agent_trace: AgentRun[] // the steps run, in order (skipped ones included)
}

export interface ExtractRequest {
  document_id: string
}

export type DocumentType = 'invoice' | 'contract' | 'other'

/** One extracted field (ExtractedFieldOut). */
export interface ExtractedField {
  name: string // e.g. "invoice_number"
  label: string // e.g. "Invoice number"
  value: string | null // null when the field was not found
  page: number | null
  source: Citation | null // the passage of that page holding the value
}

/** The fields extracted from one document (ExtractionOut). */
export interface Extraction {
  document_id: string
  filename: string
  document_type: DocumentType
  fields: ExtractedField[]
}

export type MessageRole = 'user' | 'assistant'
export type MessageMode = 'ask' | 'extract'

/** A session as shown in the session list (SessionSummaryOut). */
export interface SessionSummary {
  id: string
  title: string | null // null until the first question
  created_at: string
  updated_at: string
  message_count: number
}

/** A saved question or answer (MessageOut). The answer fields are empty for a question. */
export interface StoredMessage {
  id: string
  position: number // 0-based order within the session
  role: MessageRole
  mode: MessageMode
  content: string // the question, or the answer text (refusal message if refused)
  status: AnswerStatus | null
  refusal_reason: RefusalReason | null
  citations: Citation[]
  invalid_citations: string[]
  warnings: AnswerWarning[]
  best_score: number | null
  review: Review | null // null for questions, refusals and old answers
  agent_trace: AgentRun[] // empty for questions and old answers
  extraction: Extraction | null // the extracted fields (extract answers only)
  created_at: string
}

/** A full session: its messages and its selected documents (SessionOut). */
export interface SessionDetail {
  id: string
  title: string | null
  created_at: string
  updated_at: string
  document_ids: string[]
  messages: StoredMessage[]
}

/** What POST /api/sessions/{id}/ask and /extract return (SessionAskResponse).
 * For an extraction, "question" is the request written by the backend. */
export interface SessionAskResponse {
  session: SessionSummary
  question: StoredMessage
  answer: StoredMessage
}