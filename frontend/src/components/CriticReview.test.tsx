// @vitest-environment jsdom
// Component test: the Critic's verdict as the chat shows it (React Testing Library).
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { Issue, Review } from '../api/types'
import { dictionaries } from '../lib/i18n'
import { CriticReview } from './CriticReview'

const en = dictionaries.en
const fr = dictionaries.fr

// Vitest globals are off, so the rendered components are removed by hand.
afterEach(cleanup)

function issue(code: Issue['code'], origin: Issue['origin'], sentence: string | null): Issue {
  return { code, origin, message: 'technical note', sentence, field: null }
}

const OK: Review = { verdict: 'ok', issues: [], model_checked: true }
const ISSUES: Review = {
  verdict: 'issues',
  model_checked: true,
  issues: [
    issue('unsupported_number', 'code', 'For a material breach it is 30 days.'),
    issue('unsupported_claim', 'model', 'The notice period is 60 days.'),
  ],
}

describe('CriticReview', () => {
  it('shows nothing for a refusal, which has no verdict', () => {
    const { container } = render(<CriticReview review={null} t={en} />)
    expect(container.innerHTML).toBe('')
  })

  it('shows one green line when no problem was found', () => {
    const { container } = render(<CriticReview review={OK} t={en} />)
    expect(screen.getByText(en.criticOk)).toBeTruthy()
    expect(container.querySelector('.critic-ok')).not.toBeNull()
    expect(container.querySelector('.critic-issues')).toBeNull()
  })

  it('says when only the rules of the code checked the answer', () => {
    render(<CriticReview review={{ ...OK, model_checked: false }} t={en} />)
    expect(screen.getByText(en.criticOkCodeOnly)).toBeTruthy()
  })

  it('splits the problems into certain (code) and to check (model)', () => {
    const { container } = render(<CriticReview review={ISSUES} t={en} />)
    expect(screen.getByText(en.criticIssues(2))).toBeTruthy()

    const certain = container.querySelector<HTMLElement>('.issue-group-certain')
    const toCheck = container.querySelector<HTMLElement>('.issue-group-to-check')
    expect(certain).not.toBeNull()
    expect(toCheck).not.toBeNull()
    // Each problem is written from its code, with the sentence concerned.
    expect(within(certain!).getByText(en.issueTexts.unsupported_number)).toBeTruthy()
    expect(within(certain!).getByText('For a material breach it is 30 days.')).toBeTruthy()
    expect(within(toCheck!).getByText(en.issueTexts.unsupported_claim)).toBeTruthy()
    expect(within(toCheck!).getByText(en.criticToCheckNote)).toBeTruthy()
  })

  it('never shows the technical message of the backend', () => {
    render(<CriticReview review={ISSUES} t={en} />)
    expect(screen.queryByText('technical note')).toBeNull()
  })

  it('shows only the groups that have problems', () => {
    const codeOnly: Review = { ...ISSUES, issues: [ISSUES.issues[0]] }
    const { container } = render(<CriticReview review={codeOnly} t={en} />)
    expect(screen.getByText(en.criticIssues(1))).toBeTruthy()
    expect(container.querySelector('.issue-group-certain')).not.toBeNull()
    expect(container.querySelector('.issue-group-to-check')).toBeNull()
  })

  it('for an extraction, gives the count and leaves the problems to the table', () => {
    const { container } = render(<CriticReview review={ISSUES} issuesInTable t={en} />)
    expect(container.textContent).toContain(en.criticInTable)
    expect(container.querySelector('.issue-group')).toBeNull()
  })

  it('is written in French with the French texts', () => {
    render(<CriticReview review={ISSUES} t={fr} />)
    expect(screen.getByText('À vérifier')).toBeTruthy()
    expect(screen.getByText(fr.issueTexts.unsupported_number)).toBeTruthy()
    expect(screen.queryByText(en.criticToCheck)).toBeNull()
  })
})
