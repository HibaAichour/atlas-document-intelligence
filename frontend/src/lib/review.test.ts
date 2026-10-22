import { describe, expect, it } from 'vitest'

import type { Issue, IssueCode, Review } from '../api/types'
import { dictionaries } from './i18n'
import { fieldIssues, issueText, splitIssues } from './review'

const t = dictionaries.en

function issue(code: IssueCode, origin: Issue['origin'], field: string | null = null): Issue {
  return { code, origin, message: 'technical note', sentence: null, field }
}

describe('splitIssues', () => {
  it('separates the certain problems (code) from those to check (model)', () => {
    const review: Review = {
      verdict: 'issues',
      model_checked: true,
      issues: [
        issue('uncited_sentence', 'code'),
        issue('unsupported_claim', 'model'),
        issue('unsupported_number', 'code'),
      ],
    }

    const { certain, toCheck } = splitIssues(review)

    expect(certain.map((item) => item.code)).toEqual(['uncited_sentence', 'unsupported_number'])
    expect(toCheck.map((item) => item.code)).toEqual(['unsupported_claim'])
  })
})

describe('issueText', () => {
  it('writes the text from the code, never from the backend message', () => {
    expect(issueText(issue('value_not_found', 'code'), t)).toBe(
      'This value does not appear in the pages read.',
    )
  })

  it('has a text for every code', () => {
    for (const text of Object.values(t.issueTexts)) {
      expect(text.trim()).not.toBe('')
    }
  })
})

describe('fieldIssues', () => {
  const review: Review = {
    verdict: 'issues',
    model_checked: false,
    issues: [issue('value_not_found', 'code', 'due_date'), issue('wrong_page', 'code', 'total')],
  }

  it('keeps only the problems of the field', () => {
    expect(fieldIssues(review, 'due_date').map((item) => item.code)).toEqual(['value_not_found'])
    expect(fieldIssues(review, 'vendor')).toEqual([])
  })

  it('gives nothing without a review', () => {
    expect(fieldIssues(null, 'due_date')).toEqual([])
  })
})