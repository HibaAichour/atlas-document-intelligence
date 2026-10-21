// Which documents the questions use. Pure functions, tested without React.

import type { DocumentInfo } from '../api/types'
import { isUsable } from './documents'

/** "all": every usable document, including the ones uploaded later (a new session).
 * A set: only these documents (chosen by hand, or restored from a saved session). */
export type Selection = 'all' | ReadonlySet<string>

/** The ids of the documents a question will use: only usable ones are ever kept,
 * so a document deleted or failed since the session was saved is simply left out. */
export function selectedIdsOf(
  selection: Selection,
  documents: readonly DocumentInfo[],
): ReadonlySet<string> {
  return new Set(
    documents
      .filter((document) => isUsable(document))
      .filter((document) => selection === 'all' || selection.has(document.id))
      .map((document) => document.id),
  )
}

/** Check or uncheck one document. From "all", the selection becomes an explicit set. */
export function toggleDocument(
  selection: Selection,
  documents: readonly DocumentInfo[],
  id: string,
): ReadonlySet<string> {
  const next = new Set(selectedIdsOf(selection, documents))
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  return next
}

/** A newly uploaded document is checked (with "all", it is already included). */
export function selectUploaded(selection: Selection, document: DocumentInfo): Selection {
  if (selection === 'all' || !isUsable(document)) {
    return selection
  }
  return new Set(selection).add(document.id)
}

/** The selection of a saved session. A session with no saved document (never
 * used for a question) starts like a new one, with every document. */
export function restoredSelection(documentIds: readonly string[]): Selection {
  return documentIds.length === 0 ? 'all' : new Set(documentIds)
}