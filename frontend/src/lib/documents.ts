// Small pure helpers about documents, kept out of the components so they can be tested.

import type { DocumentInfo } from '../api/types'
import type { Messages } from './i18n'

/** Only documents that were read and indexed can be used to answer questions. */
export function isUsable(document: DocumentInfo): boolean {
  return document.status === 'ready'
}

/** The short line shown under a file name in the document list. */
export function describeDocument(document: DocumentInfo, t: Messages): string {
  if (document.status === 'failed') {
    return document.error !== null ? t.documentFailed(document.error) : t.unreadableFile
  }
  if (document.status !== 'ready') {
    return t.processing
  }
  const pages = t.pageCount(document.page_count)
  return document.ocr_used ? t.readWithOcr(pages) : pages
}