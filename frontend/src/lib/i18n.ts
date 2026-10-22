// Every text shown by the interface, in one place.
// Only English for now. French will be added at the bilingual step as a second
// dictionary of the same type: TypeScript will then report any missing text.

import type { DocumentType, IssueCode } from '../api/types'

const en = {
  // Language used to write dates and times ("19 Oct", "18:12").
  dateLocale: 'en-GB',

  brandTagline: 'Answers from your documents, with the page they come from',

  healthChecking: 'Connecting to the backend…',
  healthOnline: (version: string) => `Backend online, version ${version}`,
  healthOffline: 'Backend unreachable',

  sessionsTitle: 'Sessions',
  newSessionButton: 'New session',
  newSessionTitle: 'New session',
  newSessionNote: 'Saved with its first question',
  untitledSession: 'Untitled session',
  loadingSessions: 'Loading sessions…',
  sessionsErrorHint: 'Past sessions cannot be shown for now.',
  sessionOpenFailed: 'This session could not be opened.',
  waitBeforeSwitching: 'Wait for the answer before changing session.',
  messageCount: (count: number) => (count === 1 ? '1 message' : `${count} messages`),
  today: (time: string) => `Today, ${time}`,
  yesterday: 'Yesterday',

  documentsTitle: 'Documents',
  uploadButton: 'Upload a file',
  uploadingButton: 'Uploading…',
  uploadingNote: 'Reading and indexing the file. A scanned document can take up to a minute.',
  loadingDocuments: 'Loading documents…',
  listErrorHint: 'Start the backend, then reload the page.',
  noDocuments: 'No documents yet. Upload a PDF, Word, PowerPoint or image file to start.',
  selectionSummary: (selected: number, total: number) =>
    `Questions use ${selected} of ${total} documents.`,
  pageCount: (count: number) => (count === 1 ? '1 page' : `${count} pages`),
  readWithOcr: (pages: string) => `${pages}, read with OCR`,
  processing: 'Processing…',
  unreadableFile: 'This file could not be read.',

  introTitle: 'Ask a question about your documents',
  introText:
    'Each answer cites the document and the page it comes from. When the documents do not contain the answer, ATLAS says so instead of guessing.',

  modeLabel: 'What to do',
  modeAsk: 'Ask',
  modeExtract: 'Extract',
  extractDocumentLabel: 'Document to extract from',
  extractHint: 'Reads the key fields of an invoice or a contract, with the page of each value.',
  noDocumentToExtract: 'Upload a document to extract its fields',
  extractButton: 'Extract',
  // The same text the backend saves for the request (written again for the live message).
  extractRequest: (filename: string) => `Extract the key fields of ${filename}`,

  questionLabel: 'Your question',
  questionPlaceholder: 'Ask about the checked documents',
  selectDocumentFirst: 'Check at least one document to ask a question',
  askButton: 'Ask',
  answerPending: 'Searching the documents and writing the answer. The local model can take up to a minute.',
  extractPending:
    'Reading the document and extracting its fields. The local model can take up to a minute.',
  answerFailed: 'The answer could not be generated.',
  refusalTitle: 'The documents do not contain this information.',
  refusalNoPassages: 'No passage was close enough to the question, so no answer was generated.',
  refusalNotFound: 'The passages found do not answer the question.',
  warningInvalidCitations: 'Some citations invented by the model were removed.',
  warningNoCitation: 'This answer cites no source: check it against the documents.',
  sourceCount: (count: number) =>
    count === 0 ? 'No source.' : count === 1 ? '1 source.' : `${count} sources.`,
  answeredIn: (seconds: number) => `Answered in ${seconds.toFixed(1)} s.`,

  // Agents that ran, shown under each answer.
  traceLabel: 'Agents',
  agentNames: {
    retrieval: 'Retrieval',
    writer: 'Writer',
    critic: 'Critic',
    analyst: 'Document Analyst',
    extractor: 'Extractor',
  } as Record<string, string | undefined>,
  stepRefused: 'stopped',
  stepSkipped: 'not run',
  stepFailed: 'failed',

  // The Critic's verdict.
  criticOk: 'Checked by the Critic: no problem found.',
  criticOkCodeOnly: 'Checked by the Critic (rules only): no problem found.',
  criticIssues: (count: number) =>
    count === 1 ? 'The Critic found 1 problem.' : `The Critic found ${count} problems.`,
  criticCertain: 'Certain',
  criticToCheck: 'To check',
  criticToCheckNote: 'Flagged by the model, which can be wrong: compare with the source.',
  criticInTable: 'They are shown next to the fields concerned.',
  issueTexts: {
    invented_citations: 'Citations invented by the model were removed.',
    no_citation: 'The answer cites no source.',
    uncited_sentence: 'A sentence cites no source.',
    unsupported_number: 'A number appears in none of the cited passages.',
    unsupported_claim: 'No passage seems to state this sentence.',
    missing_required_field: 'Required field not found.',
    value_not_found: 'This value does not appear in the pages read.',
    wrong_page: 'This value is not on the page given.',
    unreadable_date: 'This is not a readable date.',
    unreadable_amount: 'This is not a readable amount.',
  } satisfies Record<IssueCode, string>,

  // An extraction.
  extractionTitle: (filename: string, type: DocumentType) =>
    `Key fields of ${filename} (${type === 'invoice' ? 'invoice' : 'contract'})`,
  extractionCount: (found: number, total: number) => `${found} of ${total} fields found.`,
  fieldColumn: 'Field',
  valueColumn: 'Value',
  pageColumn: 'Page',
  notFound: 'Not found',
  pageShort: (page: number) => `p. ${page}`,
  openFieldSource: (label: string, page: number) => `Show the source of ${label}, page ${page}`,
  extractedIn: (seconds: number) => `Extracted in ${seconds.toFixed(1)} s.`,
  unsupportedTitle: 'No fields were extracted.',
  unsupportedText:
    'This document is neither an invoice nor a contract: ATLAS extracts fields from these two kinds of documents only.',

  openSource: (label: string) => `Show the source: ${label}`,
  sourceTitle: 'Source',
  closeSource: 'Close',
  pageLabel: (page: number) => `Page ${page}`,
  sourceExplanation: 'The passage the answer relies on, exactly as extracted from the document.',
  fieldSourceExplanation: (label: string, value: string) =>
    `The passage the value of ${label} (${value}) was read from, exactly as extracted from the document.`,
  passageOf: (index: number, total: number) => `Passage ${index} of ${total}`,
  similarity: (score: number) => `Similarity to the question: ${score.toFixed(2)}`,

  unexpectedError: 'Something unexpected happened.',
}

/** The shape every dictionary must have: same keys, same parameters. */
export type Messages = typeof en

export const dictionaries = { en } satisfies Record<string, Messages>

/** Return the texts of the current language (always English for now).
 * Components call this instead of writing text directly, so adding a
 * language selector later will not change them. */
export function useMessages(): Messages {
  return dictionaries.en
}