// Small pure helpers about documents, kept out of the components so they can be tested.

import type { DocumentInfo } from '../api/types'
import type { Messages } from './i18n'

/** Only documents that were read and indexed can be used to answer questions. */
export function isUsable(document: DocumentInfo): boolean {
  return document.status === 'ready'
}

export function usableIds(documents: readonly DocumentInfo[]): string[] {
  return documents.filter(isUsable).map((document) => document.id)
}

/** The short line shown under a file name in the document list. */
export function describeDocument(document: DocumentInfo, t: Messages): string {
  if (document.status === 'failed') {
    return document.error ?? t.unreadableFile
  }
  if (document.status !== 'ready') {
    return t.processing
  }
  const pages = t.pageCount(document.page_count)
  return document.ocr_used ? t.readWithOcr(pages) : pages
}

/** Return a new set with the id added if it was missing, removed if it was there. */
export function toggleId(selected: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(selected)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  return next
}