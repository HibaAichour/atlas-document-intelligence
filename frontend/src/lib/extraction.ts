// Which document an extraction uses. Any ready document can be chosen: the
// checkboxes only decide which documents questions use.

import type { DocumentInfo } from '../api/types'
import { isUsable } from './documents'

export function extractableDocuments(documents: readonly DocumentInfo[]): DocumentInfo[] {
  return documents.filter(isUsable)
}

/** The document to show as chosen: the one the user picked if it can still be
 * used, else the first checked one, else the first ready one (null if none). */
export function chosenDocumentId(
  documents: readonly DocumentInfo[],
  selectedIds: ReadonlySet<string>,
  picked: string | null,
): string | null {
  const usable = extractableDocuments(documents)
  if (picked !== null && usable.some((document) => document.id === picked)) {
    return picked
  }
  const firstChecked = usable.find((document) => selectedIds.has(document.id))
  return (firstChecked ?? usable[0])?.id ?? null
}