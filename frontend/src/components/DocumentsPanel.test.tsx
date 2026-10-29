// @vitest-environment jsdom
// Component test: the document panel, with and without uploads (React Testing Library).
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { DocumentInfo } from '../api/types'
import { dictionaries, LanguageContext } from '../lib/i18n'
import type { Language } from '../lib/language'
import { DocumentsPanel } from './DocumentsPanel'

const en = dictionaries.en
const fr = dictionaries.fr

// Vitest globals are off, so the rendered components are removed by hand.
afterEach(cleanup)

const CONTRACT: DocumentInfo = {
  id: 'doc-1',
  filename: 'service_agreement.pdf',
  mime_type: 'application/pdf',
  page_count: 6,
  ocr_used: false,
  status: 'ready',
  error: null,
  created_at: '2026-10-29T10:00:00Z',
}

function renderPanel(uploadsAllowed: boolean, language: Language = 'en') {
  return render(
    <LanguageContext.Provider value={{ language, setLanguage: () => {} }}>
      <DocumentsPanel
        documents={[CONTRACT]}
        listState="loaded"
        listError={null}
        selectedIds={new Set(['doc-1'])}
        uploadsAllowed={uploadsAllowed}
        isUploading={false}
        uploadError={null}
        onUpload={() => {}}
        onToggle={() => {}}
      />
    </LanguageContext.Provider>,
  )
}

describe('DocumentsPanel', () => {
  it('offers the upload button when uploads are allowed', () => {
    const { container } = renderPanel(true)

    expect(screen.getByRole('button', { name: en.uploadButton })).toBeTruthy()
    expect(container.querySelector('input[type="file"]')).not.toBeNull()
    expect(screen.queryByText(en.demoUploadsNote)).toBeNull()
  })

  it('replaces it with a note in the online demo', () => {
    const { container } = renderPanel(false)

    expect(screen.queryByRole('button', { name: en.uploadButton })).toBeNull()
    expect(container.querySelector('input[type="file"]')).toBeNull()
    expect(screen.getByText(en.demoUploadsNote)).toBeTruthy()
    // The documents are still listed and can still be checked.
    expect(screen.getByRole('checkbox', { name: /service_agreement\.pdf/ })).toBeTruthy()
  })

  it('writes the note in French', () => {
    const { container } = renderPanel(false, 'fr')

    // Compared as written: the text has a no-break space before the colon,
    // which the text queries of Testing Library turn into a normal space.
    const notes = [...container.querySelectorAll('.note')].map((note) => note.textContent)
    expect(notes).toContain(fr.demoUploadsNote)
  })
})