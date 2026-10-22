import type { ExtractResponse } from '../lib/chat'
import { isOpenFieldSource, type OpenSource } from '../lib/citations'
import type { Messages } from '../lib/i18n'
import { fieldIssues, issueText } from '../lib/review'
import { AgentTrace } from './AgentTrace'
import { CriticReview } from './CriticReview'

interface ExtractionViewProps {
  answerId: number
  response: ExtractResponse
  seconds: number | null // null for a result restored from a saved session
  openSource: OpenSource | null
  onOpenSource: (source: OpenSource) => void
  t: Messages
}

/** The fields extracted from one document: value, page (opens the source) and problems. */
export function ExtractionView({
  answerId,
  response,
  seconds,
  openSource,
  onOpenSource,
  t,
}: ExtractionViewProps) {
  const timing = seconds === null ? null : <> {t.extractedIn(seconds)}</>
  const { extraction } = response

  if (response.status === 'refused' || extraction === null) {
    return (
      <div className="answer answer-refused">
        <p className="answer-title">{t.unsupportedTitle}</p>
        <p className="answer-note">
          {t.unsupportedText}
          {timing}
        </p>
        <AgentTrace trace={response.agent_trace} t={t} />
      </div>
    )
  }

  const found = extraction.fields.filter((field) => field.value !== null).length
  return (
    <div className="answer extraction">
      <p className="answer-title">{t.extractionTitle(extraction.filename, extraction.document_type)}</p>
      <div className="fields-scroll">
        <table className="fields">
          <thead>
            <tr>
              <th scope="col">{t.fieldColumn}</th>
              <th scope="col">{t.valueColumn}</th>
              <th scope="col" className="fields-page">
                {t.pageColumn}
              </th>
            </tr>
          </thead>
          <tbody>
            {extraction.fields.map((field) => {
              const issues = fieldIssues(response.review, field.name)
              const isOpen = isOpenFieldSource(openSource, answerId, field.name)
              return (
                <tr key={field.name} className={issues.length > 0 ? 'field-flagged' : undefined}>
                  <th scope="row" className="field-label">
                    {field.label}
                  </th>
                  <td className="field-value">
                    {field.value === null ? (
                      <span className="field-missing">{t.notFound}</span>
                    ) : (
                      <span className="field-text">{field.value}</span>
                    )}
                    {issues.map((issue, index) => (
                      <span key={index} className="field-issue">
                        {issueText(issue, t)}
                      </span>
                    ))}
                  </td>
                  <td className="fields-page">
                    {field.page !== null && field.source !== null && field.value !== null ? (
                      <button
                        type="button"
                        className={isOpen ? 'citation citation-open' : 'citation'}
                        aria-pressed={isOpen}
                        aria-label={t.openFieldSource(field.label, field.page)}
                        onClick={() =>
                          onOpenSource({
                            kind: 'field',
                            answerId,
                            field: field.name,
                            label: field.label,
                            value: field.value ?? '',
                            citations: field.source === null ? [] : [field.source],
                          })
                        }
                      >
                        {t.pageShort(field.page)}
                      </button>
                    ) : field.page !== null ? (
                      <span className="field-page-plain">{t.pageShort(field.page)}</span>
                    ) : (
                      <span className="field-missing">–</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="answer-note">
        {t.extractionCount(found, extraction.fields.length)}
        {timing}
      </p>
      <CriticReview review={response.review} issuesInTable t={t} />
      <AgentTrace trace={response.agent_trace} t={t} />
    </div>
  )
}
