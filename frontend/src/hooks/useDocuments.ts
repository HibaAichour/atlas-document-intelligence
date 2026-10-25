// State of the document list: loading, upload, and which documents questions use.

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'

import { listDocuments, uploadDocument } from '../api/client'
import type { DocumentInfo } from '../api/types'
import { apiErrorText } from '../lib/errors'
import { useMessages } from '../lib/i18n'
import { selectedIdsOf, selectUploaded, toggleDocument, type Selection } from '../lib/selection'

export type ListState = 'loading' | 'loaded' | 'error'

export function useDocuments() {
  const t = useMessages()
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [listState, setListState] = useState<ListState>('loading')
  const [listError, setListError] = useState<string | null>(null)
  // Which documents questions use: "all" for a new session (every usable
  // document, uploads included), or the documents chosen or restored.
  const [selection, setSelection] = useState<Selection>('all')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  // The texts of the current language, read by the request started at load
  // time: changing the language must not load the list again.
  const tRef = useRef(t)
  useLayoutEffect(() => {
    tRef.current = t
  })

  // Computed from the selection and the list, so a selection restored before
  // the list has loaded is applied as soon as the documents arrive.
  const selectedIds = useMemo(() => selectedIdsOf(selection, documents), [selection, documents])

  useEffect(() => {
    // Cancels the request if the component disappears before it finishes.
    const controller = new AbortController()
    listDocuments(controller.signal)
      .then((items) => {
        setDocuments(items)
        setListState('loaded')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setListError(apiErrorText(error, 'listDocuments', tRef.current))
        setListState('error')
      })
    return () => controller.abort()
  }, [])

  async function upload(file: File): Promise<void> {
    setIsUploading(true)
    setUploadError(null)
    try {
      const document = await uploadDocument(file)
      // Newest first, like the list returned by the backend.
      setDocuments((current) => [document, ...current.filter((item) => item.id !== document.id)])
      setSelection((current) => selectUploaded(current, document))
    } catch (error) {
      setUploadError(apiErrorText(error, 'upload', t))
    } finally {
      setIsUploading(false)
    }
  }

  function toggle(id: string): void {
    setSelection((current) => toggleDocument(current, documents, id))
  }

  /** Replace the selection, when a session is opened or a new one is started. */
  function select(next: Selection): void {
    setSelection(next)
  }

  return {
    documents,
    listState,
    listError,
    selectedIds,
    isUploading,
    uploadError,
    upload,
    toggle,
    select,
  }
}