import type { Issue, Review } from '../api/types'
import type { Messages } from '../lib/i18n'
import { issueText, splitIssues } from '../lib/review'

interface CriticReviewProps {
  review: Review | null
  // For an extraction, each problem is shown next to its field: only the count is shown here.
  issuesInTable?: boolean
  t: Messages
}

/** The Critic's verdict. Problems found by the code are certain; those found by the model are to check. */
export function CriticReview({ review, issuesInTable = false, t }: CriticReviewProps) {
  if (review === null) {
    return null // refusals and answers saved before step 9 have no verdict
  }
  if (review.verdict === 'ok') {
    return (
      <p className="critic critic-ok">
        <span className="critic-mark" aria-hidden="true">
          ✓
        </span>
        {review.model_checked ? t.criticOk : t.criticOkCodeOnly}
      </p>
    )
  }

  const { certain, toCheck } = splitIssues(review)
  return (
    <div className="critic critic-issues">
      <p className="critic-title">
        <span className="critic-mark" aria-hidden="true">
          !
        </span>
        {t.criticIssues(review.issues.length)}
        {issuesInTable && <> {t.criticInTable}</>}
      </p>
      {!issuesInTable && certain.length > 0 && (
        <IssueGroup title={t.criticCertain} issues={certain} kind="certain" t={t} />
      )}
      {!issuesInTable && toCheck.length > 0 && (
        <IssueGroup
          title={t.criticToCheck}
          note={t.criticToCheckNote}
          issues={toCheck}
          kind="to-check"
          t={t}
        />
      )}
    </div>
  )
}

interface IssueGroupProps {
  title: string
  note?: string
  issues: Issue[]
  kind: 'certain' | 'to-check'
  t: Messages
}

function IssueGroup({ title, note, issues, kind, t }: IssueGroupProps) {
  return (
    <div className={`issue-group issue-group-${kind}`}>
      <p className="issue-group-title">
        {title}
        {note !== undefined && <span className="issue-group-note"> {note}</span>}
      </p>
      <ul className="issue-list">
        {issues.map((issue, index) => (
          <li key={index} className="issue">
            {issueText(issue, t)}
            {issue.sentence !== null && <q className="issue-sentence">{issue.sentence}</q>}
          </li>
        ))}
      </ul>
    </div>
  )
}
