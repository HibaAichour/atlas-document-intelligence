// @vitest-environment jsdom
// Component test: the conversation, its citations, refusals and composer (React Testing Library).
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { AskResponse, Citation, DocumentInfo, RefusalReason } from '../api/types'
import type { ChatMessage } from '../lib/chat'
import { dictionaries, LanguageContext } from '../lib/i18n'
import type { Language } from '../lib/language'
import { ChatPanel } from './ChatPanel'

const en = dictionaries.en
const fr = dictionaries.fr

beforeAll(() => {
  // jsdom has no layout: the panel scrolls to the latest message on every render.
  Element.prototype.scrollIntoView = () => {}
})
// Vitest globals are off, so the rendered components are removed by hand.
afterEach(cleanup)

const CITATION: Citation = {
  label: 'S1',
  display: '[service_agreement.pdf, p. 4]',
  chunk_id: 'c1',
  document_id: 'd1',
  filename: 'service_agreement.pdf',
  page_number: 4,
  position: 0,
  text: "the Client may terminate this Agreement by giving the Provider 60 days' written notice.",
  score: 0.62,
}

const ANSWER: AskResponse = {
  question: 'What is the termination notice period?',
  status: 'answered',
  answer: 'The notice period is 60 days [service_agreement.pdf, p. 4].',
  refusal_reason: null,
  citations: [CITATION],
  invalid_citations: [],
  warnings: [],
  best_score: 0.62,
  review: { verdict: 'ok', issues: [], model_checked: true },
  agent_trace: [],
}

function refusal(reason: RefusalReason): AskResponse {
  return { ...ANSWER, status: 'refused', refusal_reason: reason, citations: [], review: null }
}

function answered(id: number, response: AskResponse): ChatMessage {
  return {
    id,
    role: 'assistant',
    status: 'done',
    response,
    seconds: null,
    saved: { sessionId: 's1', messageId: `m${id}` },
  }
}

const CONTRACT: DocumentInfo = {
  id: 'd1',
  filename: 'service_agreement.pdf',
  mime_type: 'application/pdf',
  page_count: 6,
  ocr_used: false,
  status: 'ready',
  error: null,
  created_at: '2026-10-21T10:41:22Z',
}

function show(messages: ChatMessage[], options: { language?: Language; canAsk?: boolean } = {}) {
  const handlers = { onAsk: vi.fn(), onExtract: vi.fn(), onOpenSource: vi.fn() }
  const view = render(
    <LanguageContext.Provider value={{ language: options.language ?? 'en', setLanguage: () => {} }}>
      <ChatPanel
        messages={messages}
        isWaiting={false}
        canAsk={options.canAsk ?? true}
        documents={[CONTRACT]}
        selectedIds={new Set(['d1'])}
        canExtract
        openSource={null}
        {...handlers}
      />
    </LanguageContext.Provider>,
  )
  return { ...view, ...handlers }
}

// The mode switch and the send button share their names ("Ask", "Extract").
function sendButton(container: HTMLElement): HTMLButtonElement {
  return container.querySelector<HTMLButtonElement>('button[type="submit"]')!
}

function modeButton(name: string): HTMLElement {
  return within(screen.getByRole('group', { name: en.modeLabel })).getByRole('button', { name })
}

describe('ChatPanel', () => {
  it('shows the introduction when the conversation is empty', () => {
    show([])
    expect(screen.getByText(en.introTitle)).toBeTruthy()
  })

  it('turns a citation into a button that opens its passage', () => {
    const { onOpenSource } = show([answered(2, ANSWER)])
    const marker = screen.getByRole('button', {
      name: en.openSource('service_agreement.pdf, p. 4'),
    })
    expect(marker.textContent).toBe('service_agreement.pdf, p. 4')
    // The marker replaces the raw citation text in the answer.
    expect(screen.queryByText(/\[service_agreement\.pdf, p\. 4\]/)).toBeNull()

    fireEvent.click(marker)
    expect(onOpenSource).toHaveBeenCalledWith({
      kind: 'answer',
      answerId: 2,
      display: '[service_agreement.pdf, p. 4]',
      citations: [CITATION],
    })
  })

  it('shows the Critic verdict and the export links under an answer', () => {
    show([answered(2, ANSWER)])
    expect(screen.getByText(en.criticOk)).toBeTruthy()
    expect(screen.getAllByRole('link')).toHaveLength(2) // Word and PowerPoint
  })

  it('explains each kind of refusal, with no citation and no export', () => {
    show([answered(2, refusal('no_relevant_passages')), answered(4, refusal('not_found_by_model'))])
    expect(screen.getAllByText(en.refusalTitle)).toHaveLength(2)
    expect(screen.getByText(en.refusalNoPassages)).toBeTruthy()
    expect(screen.getByText(en.refusalNotFound)).toBeTruthy()
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('sends the question with Enter, and keeps Shift+Enter for a new line', () => {
    const { onAsk } = show([])
    const input = screen.getByRole('textbox', { name: en.questionLabel })
    fireEvent.change(input, { target: { value: '  What is the notice period?  ' } })

    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })
    expect(onAsk).not.toHaveBeenCalled()

    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onAsk).toHaveBeenCalledWith('What is the notice period?')
  })

  it('cannot ask while no document is checked', () => {
    const { container, onAsk } = show([], { canAsk: false })
    const input = screen.getByRole('textbox', { name: en.questionLabel }) as HTMLTextAreaElement
    expect(input.disabled).toBe(true)
    expect(input.placeholder).toBe(en.selectDocumentFirst)
    expect(sendButton(container).disabled).toBe(true)
    expect(onAsk).not.toHaveBeenCalled()
  })

  it('extracts the chosen document in Extract mode', () => {
    const { container, onExtract } = show([])
    fireEvent.click(modeButton(en.modeExtract))
    const list = screen.getByRole('combobox', { name: en.extractDocumentLabel }) as HTMLSelectElement
    expect(list.value).toBe('d1')
    expect(sendButton(container).textContent).toBe(en.extractButton)

    fireEvent.click(sendButton(container))
    expect(onExtract).toHaveBeenCalledWith(CONTRACT)
  })

  it('is written in the language of the context', () => {
    const { container } = show([answered(2, refusal('no_relevant_passages'))], { language: 'fr' })
    expect(screen.getByText(fr.refusalTitle)).toBeTruthy()
    expect(sendButton(container).textContent).toBe(fr.askButton)
    expect(screen.queryByText(en.refusalTitle)).toBeNull()
  })
})
