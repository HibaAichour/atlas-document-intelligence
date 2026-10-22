// The Critic's verdict, as the chat shows it. Problems found by a rule of the
// code are certain; those found by the model are only "to check" (measured at
// step 9.2: the 3B model raises false alarms on short, elliptic sentences).

import type { Issue, Review } from '../api/types'
import type { Messages } from './i18n'

export interface SplitIssues {
  certain: Issue[] // found by the code
  toCheck: Issue[] // found by the model
}

export function splitIssues(review: Review): SplitIssues {
  return {
    certain: review.issues.filter((issue) => issue.origin === 'code'),
    toCheck: review.issues.filter((issue) => issue.origin === 'model'),
  }
}

/** The text shown for one problem, written from its code (never the backend message). */
export function issueText(issue: Issue, t: Messages): string {
  return t.issueTexts[issue.code]
}

/** The problems that concern one extracted field. */
export function fieldIssues(review: Review | null, fieldName: string): Issue[] {
  if (review === null) {
    return []
  }
  return review.issues.filter((issue) => issue.field === fieldName)
}