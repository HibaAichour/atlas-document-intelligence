import { useRef, type ChangeEvent } from 'react'

import type { DocumentInfo } from '../api/types'
import type { ListState } from '../hooks/useDocuments'
import { describeDocument, isUsable } from '../lib/documents'
import { useMessages, type Messages } from '../lib/i18n'

// Accepted in the file picker. The backend checks the real type and explains a refusal.
const ACCEPTED_FILES = '.pdf,.docx,.pptx,image/*'

interface DocumentsPanelProps {
  documents: DocumentInfo[]
  listState: ListState
  listError: string | null
  selectedIds: ReadonlySet<string>
  isUploading: boolean
  uploadError: string | null
  onUpload: (file: File) => void
  onToggle: (id: string) => void
}

export function DocumentsPanel({
  documents,
  listState,
  listError,
  selectedIds,
  isUploading,
  uploadError,
  onUpload,
  onToggle,
}: DocumentsPanelProps) {
  const t = useMessages()
  const inputRef = useRef<HTMLInputElement>(null)
  const usableCount = documents.filter(isUsable).length

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    // Reset the picker so that choosing the same file again still triggers a change.
    event.target.value = ''
    if (file) {
      onUpload(file)
    }
  }

  return (
    <aside className="documents glass" aria-label="Documents">
      <div className="documents-header">
        <h2 className="documents-title">{t.documentsTitle}</h2>
        <button
          type="button"
          className="button button-primary"
          onClick={() => inputRef.current?.click()}
          disabled={isUploading}
        >
          {isUploading ? t.uploadingButton : t.uploadButton}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_FILES}
          hidden
          onChange={handleFileChange}
        />
      </div>

      {isUploading && (
        <p className="note" aria-live="polite">
          {t.uploadingNote}
        </p>
      )}
      {uploadError && (
        <p className="message message-error" role="alert">
          {uploadError}
        </p>
      )}

      {listState === 'loading' && <p className="note">{t.loadingDocuments}</p>}
      {listState === 'error' && (
        <p className="message message-error" role="alert">
          {listError} {t.listErrorHint}
        </p>
      )}
      {listState === 'loaded' && documents.length === 0 && (
        <p className="note">{t.noDocuments}</p>
      )}

      {documents.length > 0 && (
        <>
          <p className="note">{t.selectionSummary(selectedIds.size, usableCount)}</p>
          <ul className="document-list">
            {documents.map((document) => (
              <DocumentRow
                key={document.id}
                document={document}
                isSelected={selectedIds.has(document.id)}
                onToggle={onToggle}
                t={t}
              />
            ))}
          </ul>
        </>
      )}
    </aside>
  )
}

interface DocumentRowProps {
  document: DocumentInfo
  isSelected: boolean
  onToggle: (id: string) => void
  t: Messages
}

function DocumentRow({ document, isSelected, onToggle, t }: DocumentRowProps) {
  const content = (
    <>
      <span className="document-name" title={document.filename}>
        {document.filename}
      </span>
      <span className="document-meta">{describeDocument(document, t)}</span>
    </>
  )

  if (!isUsable(document)) {
    return (
      <li className={`document document-${document.status}`}>
        <div className="document-row">
          <span aria-hidden="true" />
          <span className="document-text">{content}</span>
        </div>
      </li>
    )
  }

  return (
    <li className="document">
      <label className="document-row document-label">
        <input
          type="checkbox"
          className="document-check"
          checked={isSelected}
          onChange={() => onToggle(document.id)}
        />
        <span className="document-text">{content}</span>
      </label>
    </li>
  )
}