import { useEffect, useRef } from 'react'

import type { OpenSource } from '../lib/citations'
import { useMessages } from '../lib/i18n'
import { readableText } from '../lib/text'

interface SourcePanelProps {
  source: OpenSource
  onClose: () => void
}

/** Side panel showing the passage behind a citation, so the answer can be checked. */
export function SourcePanel({ source, onClose }: SourcePanelProps) {
  const t = useMessages()
  const closeRef = useRef<HTMLButtonElement>(null)
  const first = source.citations[0]
  const count = source.citations.length

  // Move the keyboard focus to the panel when a citation is opened.
  useEffect(() => {
    closeRef.current?.focus()
  }, [source])

  // Escape closes the panel.
  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  if (first === undefined) {
    return null
  }

  return (
    <aside className="source glass" aria-label={t.sourceTitle}>
      <div className="source-header">
        <div className="source-heading">
          <p className="note">{t.sourceTitle}</p>
          <h2 className="source-file" title={first.filename}>
            {first.filename}
          </h2>
          <p className="source-page">{t.pageLabel(first.page_number)}</p>
        </div>
        <button ref={closeRef} type="button" className="button button-quiet" onClick={onClose}>
          {t.closeSource}
        </button>
      </div>

      <p className="note">
        {source.kind === 'field'
          ? t.fieldSourceExplanation(source.label, source.value)
          : t.sourceExplanation}
      </p>

      {source.citations.map((citation, index) => (
        <figure key={citation.chunk_id} className="passage">
          {count > 1 && <figcaption className="note">{t.passageOf(index + 1, count)}</figcaption>}
          <blockquote className="passage-text">{readableText(citation.text)}</blockquote>
          {/* A similarity score only means something for a question. */}
          {source.kind === 'answer' && <p className="note">{t.similarity(citation.score)}</p>}
        </figure>
      ))}
    </aside>
  )
}