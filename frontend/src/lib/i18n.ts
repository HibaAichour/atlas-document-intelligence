// Every text shown by the interface, in one place.
// Only English for now. French will be added at the bilingual step as a second
// dictionary of the same type: TypeScript will then report any missing text.

const en = {
  brandTagline: 'Answers from your documents, with the page they come from',

  healthChecking: 'Connecting to the backend…',
  healthOnline: (version: string) => `Backend online, version ${version}`,
  healthOffline: 'Backend unreachable',

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

  questionLabel: 'Your question',
  questionPlaceholder: 'Ask about the checked documents',
  selectDocumentFirst: 'Check at least one document to ask a question',
  askButton: 'Ask',
  answerPending: 'Searching the documents and writing the answer. The local model can take up to a minute.',
  answerFailed: 'The answer could not be generated.',
  refusalTitle: 'The documents do not contain this information.',
  refusalNoPassages: 'No passage was close enough to the question, so no answer was generated.',
  refusalNotFound: 'The passages found do not answer the question.',
  warningInvalidCitations: 'Some citations invented by the model were removed.',
  warningNoCitation: 'This answer cites no source: check it against the documents.',
  sourceCount: (count: number) =>
    count === 0 ? 'No source.' : count === 1 ? '1 source.' : `${count} sources.`,
  answeredIn: (seconds: number) => `Answered in ${seconds.toFixed(1)} s.`,

  openSource: (label: string) => `Show the source: ${label}`,
  sourceTitle: 'Source',
  closeSource: 'Close',
  pageLabel: (page: number) => `Page ${page}`,
  sourceExplanation: 'The passage the answer relies on, exactly as extracted from the document.',
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