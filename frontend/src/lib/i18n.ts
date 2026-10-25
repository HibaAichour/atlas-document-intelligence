// Every text shown by the interface, in one place: an English and a French
// dictionary of the same type, so TypeScript reports any missing text.

import { createContext, useContext } from 'react'

import type { DocumentType, IssueCode } from '../api/types'
import type { ExportFormat } from './export'
import type { Language } from './language'

/** No-break space, written before : ? ! in French. */
const NB = '\u00a0'

const en = {
  // Language used to write dates and times ("19 Oct", "18:12").
  dateLocale: 'en-GB',

  brandTagline: 'Answers from your documents, with the page they come from',

  healthChecking: 'Connecting to the backend…',
  healthOnline: (version: string) => `Backend online, version ${version}`,
  healthOffline: 'Backend unreachable',

  // Language selector, in the header. Each language is named in its own language.
  languageLabel: 'Language of the interface',
  languageShort: { en: 'EN', fr: 'FR' } satisfies Record<Language, string>,
  languageNames: { en: 'English', fr: 'Français' } satisfies Record<Language, string>,

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
  // The reason a document failed comes from the backend, in English.
  documentFailed: (reason: string) => reason,

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
  // The request of an extraction, written by the interface (live and restored).
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

  // Export of a result, next to the agents.
  exportLabel: 'Export',
  exportNames: { docx: 'Word', pptx: 'PowerPoint' } satisfies Record<ExportFormat, string>,
  exportAria: {
    docx: 'Download this result as a Word document, sources included',
    pptx: 'Download this result as a PowerPoint presentation, sources included',
  } satisfies Record<ExportFormat, string>,

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
  // Labels of the extracted fields by field name; a missing name keeps the
  // label sent by the backend (English).
  fieldLabels: {} as Record<string, string | undefined>,
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

  // Errors of the API, written from the operation and the HTTP status.
  errorUnreachable: 'The server cannot be reached. Is the backend running?',
  errorFileTooLarge: 'The file is too large.',
  errorUnsupportedFile:
    'This file cannot be read: accepted files are PDF, Word (.docx), PowerPoint (.pptx), PNG and JPG.',
  errorServiceDown: 'The language model or the search service is not responding. Is Ollama running?',
  errorDocumentNotReady: 'This document cannot be analysed: it is not ready or contains no text.',
  errorNotFound: 'This item no longer exists. Reload the page.',
  errorInvalidRequest: 'The request was refused as invalid.',
  errorServer: (status: number) => `The server returned an error (HTTP ${status}).`,
  unexpectedError: 'Something unexpected happened.',
}

/** "5.2" in English, "5,2" in French. */
function frenchDecimal(value: number, digits: number): string {
  return value.toFixed(digits).replace('.', ',')
}

const fr: Messages = {
  dateLocale: 'fr-FR',

  brandTagline: 'Des réponses tirées de vos documents, avec la page d’où elles viennent',

  healthChecking: 'Connexion au backend…',
  healthOnline: (version: string) => `Backend en ligne, version ${version}`,
  healthOffline: 'Backend injoignable',

  languageLabel: 'Langue de l’interface',
  languageShort: { en: 'EN', fr: 'FR' },
  languageNames: { en: 'English', fr: 'Français' },

  sessionsTitle: 'Sessions',
  newSessionButton: 'Nouvelle session',
  newSessionTitle: 'Nouvelle session',
  newSessionNote: 'Enregistrée avec sa première question',
  untitledSession: 'Session sans titre',
  loadingSessions: 'Chargement des sessions…',
  sessionsErrorHint: 'Les sessions précédentes ne peuvent pas être affichées pour le moment.',
  sessionOpenFailed: 'Cette session n’a pas pu être ouverte.',
  waitBeforeSwitching: 'Attendez la réponse avant de changer de session.',
  messageCount: (count: number) => (count <= 1 ? `${count} message` : `${count} messages`),
  today: (time: string) => `Aujourd’hui, ${time}`,
  yesterday: 'Hier',

  documentsTitle: 'Documents',
  uploadButton: 'Téléverser',
  uploadingButton: 'Envoi…',
  uploadingNote:
    'Lecture et indexation du fichier. Un document scanné peut demander jusqu’à une minute.',
  loadingDocuments: 'Chargement des documents…',
  listErrorHint: 'Lancez le backend, puis rechargez la page.',
  noDocuments:
    'Aucun document pour l’instant. Téléversez un fichier PDF, Word, PowerPoint ou une image pour commencer.',
  selectionSummary: (selected: number, total: number) =>
    `Questions${NB}: ${selected} document${selected > 1 ? 's' : ''} sur ${total}.`,
  pageCount: (count: number) => (count <= 1 ? `${count} page` : `${count} pages`),
  readWithOcr: (pages: string) => `${pages}, lu par OCR`,
  processing: 'Traitement…',
  unreadableFile: 'Ce fichier n’a pas pu être lu.',
  documentFailed: (reason: string) => `Lecture impossible${NB}: ${reason}`,

  introTitle: 'Posez une question sur vos documents',
  introText:
    'Chaque réponse cite le document et la page d’où elle vient. Quand les documents ne contiennent pas la réponse, ATLAS le dit au lieu de deviner.',

  modeLabel: 'Que faire',
  modeAsk: 'Question',
  modeExtract: 'Extraction',
  extractDocumentLabel: 'Document à analyser',
  extractHint:
    'Lit les champs clés d’une facture ou d’un contrat, avec la page de chaque valeur.',
  noDocumentToExtract: 'Téléversez un document pour en extraire les champs',
  extractButton: 'Extraire',
  extractRequest: (filename: string) => `Extraire les champs clés de ${filename}`,

  questionLabel: 'Votre question',
  questionPlaceholder: 'Posez une question sur les documents cochés',
  selectDocumentFirst: 'Cochez au moins un document pour poser une question',
  askButton: 'Demander',
  answerPending:
    'Recherche dans les documents et rédaction de la réponse. Le modèle local peut demander jusqu’à une minute.',
  extractPending:
    'Lecture du document et extraction des champs. Le modèle local peut demander jusqu’à une minute.',
  answerFailed: 'La réponse n’a pas pu être produite.',
  refusalTitle: 'Les documents ne contiennent pas cette information.',
  refusalNoPassages:
    'Aucun passage n’était assez proche de la question, donc aucune réponse n’a été rédigée.',
  refusalNotFound: 'Les passages trouvés ne répondent pas à la question.',
  warningInvalidCitations: 'Des citations inventées par le modèle ont été retirées.',
  warningNoCitation: 'Cette réponse ne cite aucune source\u00a0: vérifiez-la dans les documents.',
  sourceCount: (count: number) =>
    count === 0 ? 'Aucune source.' : count === 1 ? '1 source.' : `${count} sources.`,
  answeredIn: (seconds: number) => `Répondu en ${frenchDecimal(seconds, 1)}${NB}s.`,

  traceLabel: 'Agents',
  agentNames: {
    retrieval: 'Retrieval',
    writer: 'Writer',
    critic: 'Critic',
    analyst: 'Document Analyst',
    extractor: 'Extractor',
  },
  stepRefused: 'arrêté',
  stepSkipped: 'non exécuté',
  stepFailed: 'en échec',

  exportLabel: 'Exporter',
  exportNames: { docx: 'Word', pptx: 'PowerPoint' },
  exportAria: {
    docx: 'Télécharger ce résultat en document Word, sources comprises',
    pptx: 'Télécharger ce résultat en présentation PowerPoint, sources comprises',
  },

  criticOk: 'Vérifié par le Critic\u00a0: aucun problème trouvé.',
  criticOkCodeOnly: 'Vérifié par le Critic (règles seulement)\u00a0: aucun problème trouvé.',
  criticIssues: (count: number) =>
    count === 1 ? 'Le Critic a trouvé 1 problème.' : `Le Critic a trouvé ${count} problèmes.`,
  criticCertain: 'Certain',
  criticToCheck: 'À vérifier',
  criticToCheckNote: 'Signalé par le modèle, qui peut se tromper\u00a0: comparez avec la source.',
  criticInTable: 'Ils sont indiqués à côté des champs concernés.',
  issueTexts: {
    invented_citations: 'Des citations inventées par le modèle ont été retirées.',
    no_citation: 'La réponse ne cite aucune source.',
    uncited_sentence: 'Une phrase ne cite aucune source.',
    unsupported_number: 'Un nombre n’apparaît dans aucun des passages cités.',
    unsupported_claim: 'Aucun passage ne semble affirmer cette phrase.',
    missing_required_field: 'Champ obligatoire non trouvé.',
    value_not_found: 'Cette valeur n’apparaît pas dans les pages lues.',
    wrong_page: 'Cette valeur n’est pas sur la page indiquée.',
    unreadable_date: 'Ce n’est pas une date lisible.',
    unreadable_amount: 'Ce n’est pas un montant lisible.',
  },

  extractionTitle: (filename: string, type: DocumentType) =>
    `Champs clés de ${filename} (${type === 'invoice' ? 'facture' : 'contrat'})`,
  extractionCount: (found: number, total: number) =>
    `${found} champ${found > 1 ? 's' : ''} trouvé${found > 1 ? 's' : ''} sur ${total}.`,
  fieldColumn: 'Champ',
  valueColumn: 'Valeur',
  pageColumn: 'Page',
  notFound: 'Non trouvé',
  fieldLabels: {
    invoice_number: 'Numéro de facture',
    invoice_date: 'Date de facture',
    due_date: 'Date d’échéance',
    total_amount: 'Total dû',
    currency: 'Devise',
    vendor: 'Fournisseur',
    customer: 'Client',
    agreement_number: 'Numéro du contrat',
    provider: 'Prestataire',
    client: 'Client',
    effective_date: 'Date d’effet',
    initial_term: 'Durée initiale',
    convenience_notice: 'Préavis de résiliation pour convenance',
    non_renewal_notice: 'Préavis de non-renouvellement',
    governing_law: 'Droit applicable',
  },
  pageShort: (page: number) => `p.${NB}${page}`,
  openFieldSource: (label: string, page: number) =>
    `Afficher la source de ${label}, page ${page}`,
  extractedIn: (seconds: number) => `Extrait en ${frenchDecimal(seconds, 1)}${NB}s.`,
  unsupportedTitle: 'Aucun champ n’a été extrait.',
  unsupportedText:
    'Ce document n’est ni une facture ni un contrat\u00a0: ATLAS extrait les champs de ces deux types de documents seulement.',

  openSource: (label: string) => `Afficher la source${NB}: ${label}`,
  sourceTitle: 'Source',
  closeSource: 'Fermer',
  pageLabel: (page: number) => `Page ${page}`,
  sourceExplanation:
    'Le passage sur lequel repose la réponse, tel qu’il a été extrait du document.',
  fieldSourceExplanation: (label: string, value: string) =>
    `Le passage d’où la valeur de ${label} (${value}) a été lue, tel qu’il a été extrait du document.`,
  passageOf: (index: number, total: number) => `Passage ${index} sur ${total}`,
  similarity: (score: number) => `Similarité avec la question${NB}: ${frenchDecimal(score, 2)}`,

  errorUnreachable: 'Le serveur est injoignable. Le backend est-il lancé\u00a0?',
  errorFileTooLarge: 'Le fichier est trop volumineux.',
  errorUnsupportedFile:
    'Ce fichier ne peut pas être lu\u00a0: les fichiers acceptés sont PDF, Word (.docx), PowerPoint (.pptx), PNG et JPG.',
  errorServiceDown:
    'Le modèle de langue ou le service de recherche ne répond pas. Ollama est-il lancé\u00a0?',
  errorDocumentNotReady:
    'Ce document ne peut pas être analysé\u00a0: il n’est pas prêt ou ne contient pas de texte.',
  errorNotFound: 'Cet élément n’existe plus. Rechargez la page.',
  errorInvalidRequest: 'La requête a été refusée car elle n’est pas valide.',
  errorServer: (status: number) => `Le serveur a renvoyé une erreur (HTTP ${status}).`,
  unexpectedError: 'Un problème inattendu est survenu.',
}

/** The shape every dictionary must have: same keys, same parameters. */
export type Messages = typeof en

export const dictionaries: Record<Language, Messages> = { en, fr }

/** The current language and the way to change it, shared by the whole app
 * (provided by components/LanguageProvider.tsx). */
export interface LanguageState {
  language: Language
  setLanguage: (language: Language) => void
}

export const LanguageContext = createContext<LanguageState>({
  language: 'en',
  setLanguage: () => {},
})

export function useLanguage(): LanguageState {
  return useContext(LanguageContext)
}

/** Return the texts of the current language. Components call this instead of
 * writing text directly, so the language can change without touching them. */
export function useMessages(): Messages {
  return dictionaries[useLanguage().language]
}