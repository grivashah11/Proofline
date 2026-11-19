import { Clock3, GitCompareArrows, History, ShieldCheck } from 'lucide-react'
import type { ContentRevision, ReviewDecisionRecord } from '../lib/content'
import type { FindingLifecycleRecord, RevisionDiffResponse } from '../lib/governance'
import './ReviewGovernancePanels.css'

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Date unavailable'
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(date)
}

function recordOf(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function numberOf(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function textOf(value: unknown) {
  return typeof value === 'string' && value.trim() ? value : null
}

type RevisionDiffPanelProps = {
  revisions: ContentRevision[]
  fromRevisionId: string
  toRevisionId: string
  onFromRevisionChange: (value: string) => void
  onToRevisionChange: (value: string) => void
  diff: RevisionDiffResponse | null
  loading: boolean
  error: string
}

function DiffLines({
  lines,
  startLine,
  variant,
}: {
  lines: string[]
  startLine: number
  variant: 'insert' | 'delete' | 'equal'
}) {
  if (!lines.length) return null

  return (
    <div className={`review-diff-lines review-diff-lines--${variant}`}>
      {lines.map((line, index) => (
        <div className="review-diff-line" key={`${startLine + index}:${index}`}>
          <span>{Math.max(1, startLine + index)}</span>
          <code>{line || ' '}</code>
        </div>
      ))}
    </div>
  )
}

export function RevisionDiffPanel({
  revisions,
  fromRevisionId,
  toRevisionId,
  onFromRevisionChange,
  onToRevisionChange,
  diff,
  loading,
  error,
}: RevisionDiffPanelProps) {
  const orderedRevisions = [...revisions].sort((a, b) => a.revision_number - b.revision_number)
  const changedOperations = diff?.operations.filter((item) => item.operation !== 'equal') ?? []

  return (
    <section className="workflow-section-block review-governance-panel">
      <div className="workflow-section-heading">
        <div><p className="eyebrow">IMPROVEMENT 3 · REVISION HISTORY</p><h3>Compare saved revisions</h3></div>
        <GitCompareArrows size={17} />
      </div>
      <p className="review-governance-intro">Compare immutable saved versions to see exactly which lines were added, removed or changed. This view never edits either revision.</p>

      {orderedRevisions.length < 2 ? (
        <div className="review-governance-empty">A second saved revision is needed before Proofline can show a revision difference.</div>
      ) : (
        <>
          <div className="review-diff-controls">
            <label className="workflow-field">
              <span>Previous revision</span>
              <select value={fromRevisionId} onChange={(event) => onFromRevisionChange(event.target.value)}>
                {orderedRevisions.map((revision) => (
                  <option value={revision.id} key={revision.id}>Revision {revision.revision_number} · {formatDate(revision.created_at)}</option>
                ))}
              </select>
            </label>
            <label className="workflow-field">
              <span>Compare with</span>
              <select value={toRevisionId} onChange={(event) => onToRevisionChange(event.target.value)}>
                {orderedRevisions.map((revision) => (
                  <option value={revision.id} key={revision.id}>Revision {revision.revision_number} · {formatDate(revision.created_at)}</option>
                ))}
              </select>
            </label>
          </div>

          {fromRevisionId === toRevisionId ? (
            <div className="workflow-notice workflow-notice--info">Choose two different saved revisions to see the changes between them.</div>
          ) : loading ? (
            <div className="review-governance-empty">Loading revision comparison...</div>
          ) : error ? (
            <div className="workflow-alert workflow-alert--error" role="alert">{error}</div>
          ) : diff ? (
            <>
              <div className="review-diff-summary">
                <span><strong>{diff.summary.inserted_lines}</strong> lines added</span>
                <span><strong>{diff.summary.deleted_lines}</strong> lines removed</span>
                <span><strong>{diff.summary.unchanged_lines}</strong> unchanged</span>
                <span><strong>{diff.summary.changed_blocks}</strong> changed blocks</span>
              </div>
              {changedOperations.length === 0 ? (
                <div className="review-governance-empty">No text differences were found between these two revisions.</div>
              ) : (
                <div className="review-diff-block-list">
                  {changedOperations.map((operation, index) => (
                    <article className={`review-diff-block review-diff-block--${operation.operation}`} key={`${operation.operation}:${index}`}>
                      <div className="review-diff-block-heading">
                        <strong>{operation.operation === 'insert' ? 'Added text' : operation.operation === 'delete' ? 'Removed text' : 'Changed text'}</strong>
                        <small>
                          {operation.operation !== 'insert' && `Old lines ${operation.from_start_line}–${operation.from_end_line}`}
                          {operation.operation === 'replace' && ' · '}
                          {operation.operation !== 'delete' && `New lines ${operation.to_start_line}–${operation.to_end_line}`}
                        </small>
                      </div>
                      {operation.operation === 'replace' ? (
                        <div className="review-diff-replacement-grid">
                          <DiffLines lines={operation.from_lines} startLine={operation.from_start_line} variant="delete" />
                          <DiffLines lines={operation.to_lines} startLine={operation.to_start_line} variant="insert" />
                        </div>
                      ) : operation.operation === 'delete' ? (
                        <DiffLines lines={operation.from_lines} startLine={operation.from_start_line} variant="delete" />
                      ) : (
                        <DiffLines lines={operation.to_lines} startLine={operation.to_start_line} variant="insert" />
                      )}
                    </article>
                  ))}
                </div>
              )}
            </>
          ) : null}
        </>
      )}
    </section>
  )
}

export function FindingLifecyclePanel({
  records,
  loading,
  error,
}: {
  records: FindingLifecycleRecord[]
  loading: boolean
  error: string
}) {
  return (
    <section className="workflow-section-block review-governance-panel">
      <div className="workflow-section-heading">
        <div><p className="eyebrow">IMPROVEMENT 3 · FINDING LIFECYCLE</p><h3>Issues across revisions</h3></div>
        <History size={17} />
      </div>
      <p className="review-governance-intro">Each thread follows the same issue fingerprint through later analyses, showing whether it persisted, was resolved or reappeared.</p>
      {loading ? (
        <div className="review-governance-empty">Loading finding history...</div>
      ) : error ? (
        <div className="workflow-alert workflow-alert--error" role="alert">{error}</div>
      ) : records.length === 0 ? (
        <div className="review-governance-empty">No finding lifecycle events are recorded for this submission yet. Tracking begins with analyses run after the governance migration.</div>
      ) : (
        <div className="review-lifecycle-list">
          {records.map((record) => (
            <article className={`review-lifecycle-card review-lifecycle-card--${record.status}`} key={record.id}>
              <div className="review-lifecycle-heading">
                <div><span className="governance-source-label">{record.source.replaceAll('_', ' ')} · {record.category.replaceAll('_', ' ')}</span><h4>{record.issue_title}</h4></div>
                <span className={`review-lifecycle-status review-lifecycle-status--${record.status}`}>{record.status === 'open' ? 'Open' : 'Resolved'}</span>
              </div>
              <div className="review-lifecycle-metrics">
                <span><strong>{record.occurrence_count}</strong> occurrences</span>
                <span><strong>{record.reappeared_count}</strong> reappearances</span>
                <span><strong>{record.last_outcome.replaceAll('_', ' ')}</strong> latest outcome</span>
              </div>
              <div className="review-lifecycle-events">
                {(record.events ?? []).map((event) => (
                  <div className="review-lifecycle-event" key={event.id}>
                    <span className={`review-lifecycle-event-dot review-lifecycle-event-dot--${event.event_type}`} />
                    <div><strong>{event.event_type.replaceAll('_', ' ')}</strong><small>{formatDate(event.created_at)}{event.revision_id ? ` · revision ${event.revision_id.slice(0, 8)}` : ''}</small></div>
                  </div>
                ))}
              </div>
              <small className="review-lifecycle-last-seen"><Clock3 size={12} /> First seen {formatDate(record.first_seen_at)} · Last seen {formatDate(record.last_seen_at)}{record.resolved_at ? ` · Resolved ${formatDate(record.resolved_at)}` : ''}</small>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

export function ReviewDecisionContext({ decision }: { decision: ReviewDecisionRecord }) {
  const context = decision.review_context ?? {}
  const revision = recordOf(context.revision)
  const analysis = recordOf(context.analysis)
  const findings = Array.isArray(context.findings) ? context.findings : []
  const hasContext = Boolean(revision || analysis || findings.length)
  const revisionNumber = numberOf(revision?.revision_number)
  const runNumber = numberOf(analysis?.run_number)
  const reviewCountItems: Array<{ label: string; value: unknown }> = [
    { label: 'Rule conflicts', value: analysis?.rule_conflict_count },
    { label: 'Rule needs review', value: analysis?.rule_needs_review_count },
    { label: 'Supported claims', value: analysis?.claim_supported_count },
    { label: 'Claim conflicts', value: analysis?.claim_conflict_count },
    { label: 'Claims needing verification', value: analysis?.claim_needs_verification_count },
    { label: 'Findings captured', value: findings.length },
  ]

  return (
    <details className="review-context-details">
      <summary><ShieldCheck size={13} /> Decision snapshot {revisionNumber !== null ? `· Revision ${revisionNumber}` : ''}</summary>
      {hasContext ? (
        <div className="review-context-body">
          <div className="review-context-meta">
            {revisionNumber !== null && <span>Revision {revisionNumber}</span>}
            {runNumber !== null && <span>Analysis run {runNumber}</span>}
            {textOf(analysis?.status) && <span>{textOf(analysis?.status)}</span>}
            {textOf(analysis?.ai_extraction_status) && <span>AI extraction {textOf(analysis?.ai_extraction_status)}</span>}
          </div>
          <div className="review-context-counts">
            {reviewCountItems.map(({ label, value }) => (
              <span key={label}><strong>{numberOf(value) ?? '—'}</strong>{label}</span>
            ))}
          </div>
          {textOf(context.captured_at) && <small>Context captured {formatDate(String(context.captured_at))}. This snapshot is tied to the exact revision and analysis used for the decision.</small>}
        </div>
      ) : (
        <p className="review-context-unavailable">No detailed review snapshot is available for this historical decision.</p>
      )}
    </details>
  )
}
