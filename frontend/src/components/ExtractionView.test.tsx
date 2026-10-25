// @vitest-environment jsdom
// Component test: an extraction shown as a table (React Testing Library).
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Citation, ExtractedField } from '../api/types'
import type { ExtractResponse } from '../lib/chat'
import { dictionaries } from '../lib/i18n'
import { ExtractionView } from './ExtractionView'

const en = dictionaries.en
const fr = dictionaries.fr

// Vitest globals are off, so the rendered components are removed by hand.
afterEach(cleanup)

const SOURCE: Citation = {
  label: 'total_amount',
  display: '[invoice.pdf, p. 1]',
  chunk_id: 'c1',
  document_id: 'd1',
  filename: 'invoice.pdf',
  page_number: 1,
  position: 0,
  text: 'Total due USD 15,950.00',
  score: 1,
}

function field(
  name: string,
  label: string,
  value: string | null,
  page: number | null,
  source: Citation | null = null,
): ExtractedField {
  return { name, label, value, page, source }
}

const RESPONSE: ExtractResponse = {
  request: 'Extract the key fields of invoice.pdf',
  status: 'answered',
  message: 'Extracted 3 fields.',
  refusal_reason: null,
  extraction: {
    document_id: 'd1',
    filename: 'invoice.pdf',
    document_type: 'invoice',
    fields: [
      field('total_amount', 'Total due', 'USD 15,950.00', 1, SOURCE),
      field('due_date', 'Due date', '1 June 2026', 1), // a page but no passage holding it
      field('currency', 'Currency', null, null),
    ],
  },
  review: {
    verdict: 'issues',
    model_checked: false,
    issues: [
      {
        code: 'value_not_found',
        origin: 'code',
        message: 'technical note',
        sentence: null,
        field: 'due_date',
      },
    ],
  },
  agent_trace: [],
}

function show(response = RESPONSE, t = en, onOpenSource = vi.fn()) {
  const view = render(
    <ExtractionView
      answerId={7}
      response={response}
      seconds={null}
      saved={{ sessionId: 's1', messageId: 'm1' }}
      openSource={null}
      onOpenSource={onOpenSource}
      t={t}
    />,
  )
  return { ...view, onOpenSource }
}

function row(container: HTMLElement, label: string): HTMLTableRowElement {
  // Array.from rather than [...list]: some editors check with a TypeScript
  // version that cannot spread a NodeList under this project's settings.
  const header = Array.from(container.querySelectorAll('th[scope="row"]')).find(
    (cell) => cell.textContent === label,
  )
  expect(header).toBeDefined()
  return header!.closest('tr')!
}

describe('ExtractionView', () => {
  it('shows one row per field with its value, and the number found', () => {
    const { container } = show()
    expect(screen.getByText(en.extractionTitle('invoice.pdf', 'invoice'))).toBeTruthy()
    expect(container.querySelectorAll('tbody tr')).toHaveLength(3)
    expect(screen.getByText('USD 15,950.00')).toBeTruthy()
    expect(screen.getByText(en.extractionCount(2, 3))).toBeTruthy()
  })

  it('opens the passage a value was read from when its page is clicked', () => {
    const { onOpenSource } = show()
    fireEvent.click(screen.getByRole('button', { name: en.openFieldSource('Total due', 1) }))
    expect(onOpenSource).toHaveBeenCalledWith({
      kind: 'field',
      answerId: 7,
      field: 'total_amount',
      label: 'Total due',
      value: 'USD 15,950.00',
      citations: [SOURCE],
    })
  })

  it('shows a page without a button when no passage holds the value', () => {
    const { container } = show()
    const due = row(container, 'Due date')
    expect(due.querySelector('button')).toBeNull()
    expect(due.textContent).toContain(en.pageShort(1))
  })

  it('marks a field that was not found', () => {
    const { container } = show()
    const currency = row(container, 'Currency')
    expect(currency.textContent).toContain(en.notFound)
    expect(currency.querySelector('button')).toBeNull()
  })

  it('puts each problem of the Critic under the value concerned', () => {
    const { container } = show()
    const due = row(container, 'Due date')
    expect(due.className).toBe('field-flagged')
    expect(due.textContent).toContain(en.issueTexts.value_not_found)
    expect(row(container, 'Total due').textContent).not.toContain(en.issueTexts.value_not_found)
    // The verdict above the table only gives the count.
    expect(container.textContent).toContain(en.criticInTable)
  })

  it('translates the field labels in French', () => {
    show(RESPONSE, fr)
    expect(screen.getByText('Total dû')).toBeTruthy()
    expect(screen.getByRole('button', { name: fr.openFieldSource('Total dû', 1) })).toBeTruthy()
    expect(screen.queryByText('Total due')).toBeNull()
  })

  it('explains a refused extraction instead of showing a table', () => {
    const refused: ExtractResponse = {
      ...RESPONSE,
      status: 'refused',
      refusal_reason: 'unsupported_document',
      extraction: null,
      review: null,
    }
    const { container } = show(refused)
    expect(screen.getByText(en.unsupportedTitle)).toBeTruthy()
    expect(container.querySelector('table')).toBeNull()
  })
})
