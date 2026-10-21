// State of the document list: loading, upload, and which documents questions use.

import { useEffect, useState } from 'react'

import { listDocuments, uploadDocument } from '../api/client'
import type { DocumentInfo } from '../api/types'
import { isUsable, toggleId, usableIds } from '../lib/documents'
import { errorText } from '../lib/errors'
import { useMessages } from '../lib/i18n'

export type ListState = 'loading' | 'loaded' | 'error'

export function useDocuments() {
  const t = useMessages()
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [listState, setListState] = useState<ListState>('loading')
  const [listError, setListError] = useState<string | null>(null)
  // Ids of the documents used to answer questions. Every usable document is
  // selected when the list loads, and each new upload is selected too.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  useEffect(() => {
    // Cancels the request if the component disappears before it finishes.
    const controller = new AbortController()
    listDocuments(controller.signal)
      .then((items) => {
        setDocuments(items)
        setSelectedIds(new Set(usableIds(items)))
        setListState('loaded')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setListError(errorText(error, t.unexpectedError))
        setListState('error')
      })
    return () => controller.abort()
  }, [t])

  async function upload(file: File): Promise<void> {
    setIsUploading(true)
    setUploadError(null)
    try {
      const document = await uploadDocument(file)
      // Newest first, like the list returned by the backend.
      setDocuments((current) => [document, ...current.filter((item) => item.id !== document.id)])
      if (isUsable(document)) {
        setSelectedIds((current) => new Set(current).add(document.id))
      }
    } catch (error) {
      setUploadError(errorText(error, t.unexpectedError))
    } finally {
      setIsUploading(false)
    }
  }

  function toggle(id: string): void {
    setSelectedIds((current) => toggleId(current, id))
  }

  return { documents, listState, listError, selectedIds, isUploading, uploadError, upload, toggle }
}