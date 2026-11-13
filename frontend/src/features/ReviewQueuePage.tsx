import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  AlertCircle,
  BadgeCheck,
  CheckCircle2,
  CircleAlert,
  Clock3,
  FileCheck2,
  History,
  LoaderCircle,
  MessageSquareText,
  RefreshCw,
  Send,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  Undo2,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  addComment,
  decisionLabel,
  getAnalysis,
  getContent,
  getReviewQueue,
  listAnalyses,
  listAuditEvents,
  listComments,
  listReviewDecisions,
  recordReviewDecision,
  statusLabel,
  type AnalysisDetail,
  type AuditEvent,
  type ContentComment,
  type ContentDetail,
  type ContentRecord,
  type ReviewDecision,
  type ReviewDecisionRecord,
} from '../lib/content'
import type { WorkspaceRole } from '../lib/workspaces'
import { useAuth } from '../lib/auth-context'
import './WorkflowPages.css'

type Props = { workspaceId: string; role: WorkspaceRole }

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

export default function ReviewQueuePage({ workspaceId, role }: Props) {
  const { user } = useAuth()
  const [queue, setQueue] = useState<ContentRecord[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [detail, setDetail] = useState<ContentDetail | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null)
  const [comments, setComments] = useState<ContentComment[]>([])
  const [decisions, setDecisions] = useState<ReviewDecisionRecord[]>([])
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [reviewComment, setReviewComment] = useState('')
  const [threadComment, setThreadComment] = useState('')
  const [loadedWorkspaceId, setLoadedWorkspaceId] = useState('')
  const loading = loadedWorkspaceId !== workspaceId
  const [detailReloadKey, setDetailReloadKey] = useState(0)
  const [loadedDetailKey, setLoadedDetailKey] = useState('')
  const detailKey = `${workspaceId}:${selectedId}:${detailReloadKey}`
  const detailLoading = Boolean(selectedId) && loadedDetailKey !== detailKey
  const [busy, setBusy] = useState<'comment' | ReviewDecision | ''>('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const currentRevision = useMemo(() => {
    if (!detail) return null
    return detail.revisions.find((revision) => revision.id === detail.content.current_revision_id)
      ?? detail.revisions[0]
      ?? null
  }, [detail])

  const refreshQueue = useCallback(async (preferredId?: string) => {
    const records = await getReviewQueue(workspaceId)
    setQueue(records)
    const nextId = preferredId && records.some((item) => item.id === preferredId)
      ? preferredId
      : selectedId && records.some((item) => item.id === selectedId)
        ? selectedId
        : records[0]?.id ?? ''
    setSelectedId(nextId)
  }, [workspaceId, selectedId])

  useEffect(() => {
    let active = true
    getReviewQueue(workspaceId)
      .then((records) => {
        if (!active) return
        setQueue(records)
        const nextId = records[0]?.id ?? ''
        setSelectedId(nextId)
        if (!nextId) {
          setDetail(null)
          setAnalysis(null)
          setComments([])
          setDecisions([])
          setEvents([])
        }
        setError('')
      })
      .catch((err: unknown) => {
        if (active) {
          setQueue([])
          setSelectedId('')
          setDetail(null)
          setAnalysis(null)
          setComments([])
          setDecisions([])
          setEvents([])
          setError(getErrorMessage(err))
        }
      })
      .finally(() => { if (active) setLoadedWorkspaceId(workspaceId) })
    return () => { active = false }
  }, [workspaceId])

  useEffect(() => {
    if (loading || !selectedId) return
    let active = true

    async function loadSelected() {
      try {
        const [loadedDetail, runs, reviewRecords, auditRecords] = await Promise.all([
          getContent(workspaceId, selectedId),
          listAnalyses(workspaceId, selectedId),
          listReviewDecisions(workspaceId, selectedId),
          listAuditEvents(workspaceId, selectedId),
        ])
        if (!active) return

        setDetail(loadedDetail)
        setDecisions(reviewRecords)
        setEvents(auditRecords)
        const revision = loadedDetail.revisions.find((item) => item.id === loadedDetail.content.current_revision_id)
          ?? loadedDetail.revisions[0]
          ?? null
        const latestRun = runs
          .filter((run) => run.revision_id === revision?.id)
          .sort((a, b) => b.run_number - a.run_number)[0]
        if (latestRun) {
          const fullAnalysis = await getAnalysis(workspaceId, selectedId, latestRun.id)
          if (!active) return
          setAnalysis(fullAnalysis)
        } else {
          setAnalysis(null)
        }
        if (revision) {
          const revisionComments = await listComments(workspaceId, selectedId, revision.id)
          if (!active) return
          setComments(revisionComments)
        } else {
          setComments([])
        }
        setError('')
      } catch (err) {
        if (active) {
          setError(getErrorMessage(err))
          setDetail(null)
          setAnalysis(null)
          setComments([])
        }
      } finally {
        if (active) setLoadedDetailKey(detailKey)
      }
    }

    void loadSelected()
    return () => { active = false }
  }, [workspaceId, selectedId, loading, detailReloadKey, detailKey])

  async function handleThreadComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!detail || !currentRevision || !threadComment.trim()) return
    setBusy('comment')
    setError('')
    try {
      const added = await addComment(workspaceId, detail.content.id, currentRevision.id, threadComment.trim())
      setComments((current) => [...current, added])
      setThreadComment('')
      setSuccess('Comment added to the submitted revision.')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setBusy('')
    }
  }

  async function handleDecision(decision: ReviewDecision) {
    if (!detail || !currentRevision || !analysis || analysis.analysis.revision_id !== currentRevision.id) return
    setBusy(decision)
    setError('')
    setSuccess('')
    try {
      const result = await recordReviewDecision(workspaceId, detail.content.id, {
        decision,
        reviewer_comment: reviewComment.trim() || null,
      })
      setSuccess(`Decision recorded: ${decisionLabel(result.decision.decision)}.`)
      setReviewComment('')
      const records = await getReviewQueue(workspaceId)
      setQueue(records)
      setSelectedId(records[0]?.id ?? '')
      setDetailReloadKey((current) => current + 1)
      if (records.length === 0) {
        setDetail(null)
        setAnalysis(null)
        setComments([])
        setDecisions([])
        setEvents([])
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setBusy('')
    }
  }

  if (role !== 'brand_owner') {
    return (
      <div className="workflow-page">
        <header className="workflow-header"><div><p className="eyebrow">BRAND OWNER WORKSPACE</p><h1>Review queue</h1><p className="workflow-subtitle">Only Brand Owners can make review decisions.</p></div></header>
        <div className="workflow-notice workflow-notice--warning"><ShieldCheck size={18} />Your current workspace role is Creator. Ask a Brand Owner to review submitted content. <Link to="/content">Return to your submissions</Link></div>
      </div>
    )
  }

  const hasCurrentAnalysis = Boolean(analysis && currentRevision && analysis.analysis.revision_id === currentRevision.id)
  const decisionDisabled = !detail || detail.content.status !== 'in_review' || !hasCurrentAnalysis || busy !== ''

  return (
    <div className="workflow-page">
      <header className="workflow-header">
        <div><p className="eyebrow">BRAND OWNER WORKSPACE</p><h1>Review queue</h1><p className="workflow-subtitle">Inspect the saved revision, read its evidence-linked findings and record an accountable human decision.</p></div>
        <button className="button button-secondary" type="button" onClick={() => void refreshQueue()}><RefreshCw size={15} /> Refresh queue</button>
      </header>

      {error && <div className="workflow-alert workflow-alert--error" role="alert"><AlertCircle size={17} />{error}</div>}
      {success && <div className="workflow-alert workflow-alert--success" role="status"><CheckCircle2 size={17} />{success}</div>}

      <div className="workflow-layout review-queue-layout">
        <aside className="workflow-list-panel">
          <div className="workflow-list-heading"><div><p className="eyebrow">AWAITING REVIEW</p><h2>Submissions <span className="queue-count">{queue.length}</span></h2></div></div>
          {loading ? <div className="workflow-loading"><LoaderCircle className="spin-icon" size={21} />Loading review queue...</div> : queue.length === 0 ? <div className="workflow-empty-small"><BadgeCheck size={24} /><strong>Queue is clear</strong><span>New submissions from Creators will appear here.</span><Link to="/content">Open content reviews</Link></div> : (
            <div className="workflow-submission-list">
              {queue.map((item) => (
                <button key={item.id} type="button" className={`workflow-submission-item ${selectedId === item.id ? 'is-selected' : ''}`} onClick={() => { setSelectedId(item.id); setError(''); setSuccess('') }}>
                  <span className="submission-item-top"><span>{item.content_type.replace('_', ' ')}</span><span className="status-pill status-in_review">In review</span></span>
                  <strong>{item.title}</strong>
                  <span className="submission-item-context">{item.product_context || 'No product context'}</span>
                  <span className="submission-item-bottom"><span>{item.channel || 'Channel not set'}</span><Clock3 size={13} /></span>
                </button>
              ))}
            </div>
          )}
        </aside>

        <section className="workflow-detail-panel">
          {detailLoading ? <div className="workflow-loading workflow-loading--large"><LoaderCircle className="spin-icon" size={24} />Loading submitted revision...</div> : !detail ? (
            <div className="workflow-detail-empty"><div className="workflow-empty-icon"><FileCheck2 size={26} /></div><h2>Select a submission</h2><p>Open an item from the queue to inspect its submitted revision and findings.</p></div>
          ) : (
            <>
              <div className="workflow-detail-heading"><div><p className="eyebrow">SUBMITTED FOR APPROVAL</p><h2>{detail.content.title}</h2><div className="workflow-meta-line"><span>{detail.content.content_type.replace('_', ' ')}</span><span>·</span><span>{detail.content.channel || 'No channel'}</span><span>·</span><span>{detail.content.market || 'No market'}</span></div></div><span className={`status-pill status-${detail.content.status}`}>{statusLabel(detail.content.status)}</span></div>

              <section className="workflow-section-block">
                <div className="workflow-section-heading"><div><p className="eyebrow">EXACT SUBMITTED VERSION</p><h3>{currentRevision ? `Revision ${currentRevision.revision_number}` : 'Revision unavailable'}</h3></div>{currentRevision && <span className="revision-tag">{formatDate(currentRevision.created_at)}</span>}</div>
                <div className="submitted-content-text">{currentRevision?.content_text || 'No revision content was returned.'}</div>
                {currentRevision && <div className="workflow-editor-footer"><span>Revision ID: {currentRevision.id}</span><span>Submitted by {detail.content.created_by === user?.id ? 'you' : detail.content.created_by.slice(0, 8)}</span></div>}
              </section>

              <section className="workflow-section-block">
                <div className="workflow-section-heading"><div><p className="eyebrow">EVIDENCE-LINKED ANALYSIS</p><h3>Findings to consider</h3></div>{analysis && <span className="analysis-state analysis-state--good">Run {analysis.analysis.run_number}</span>}</div>
                {!analysis || !hasCurrentAnalysis ? <div className="workflow-notice workflow-notice--warning"><CircleAlert size={17} />No analysis matching this exact revision was returned. Do not make a decision until the Creator re-runs the checks and resubmits.</div> : (
                  <>
                    <div className="analysis-summary-grid"><div><strong>{analysis.findings.length}</strong><span>Total findings</span></div><div><strong>{analysis.analysis.rule_conflict_count + analysis.analysis.claim_conflict_count}</strong><span>Conflicts</span></div><div><strong>{analysis.analysis.claim_supported_count}</strong><span>Supported claims</span></div><div><strong>{analysis.analysis.claim_needs_verification_count + analysis.analysis.claim_review_due_count}</strong><span>Need verification</span></div></div>
                    {analysis.analysis.ai_extraction_status === 'unavailable' && <div className="workflow-notice workflow-notice--warning"><CircleAlert size={16} />AI claim extraction was unavailable. Treat the analysis as partial and inspect claims manually.</div>}
                    {analysis.findings.length === 0 ? <div className="workflow-inline-empty"><CheckCircle2 size={18} /><div><strong>No findings returned</strong><p>This does not replace your own review of the submitted content.</p></div></div> : <div className="finding-list">{analysis.findings.map((finding) => <article className={`finding-card finding-${finding.outcome}`} key={finding.id}><div className="finding-card-top"><div className="finding-title-wrap"><span className={`finding-severity severity-${finding.severity}`}>{finding.severity}</span><strong>{finding.title}</strong></div><span className={`outcome-pill outcome-${finding.outcome}`}>{finding.outcome.replaceAll('_', ' ')}</span></div><p className="finding-message">{finding.message}</p>{finding.matched_text && <blockquote className="finding-excerpt">“{finding.matched_text}”</blockquote>}{finding.approved_wording && <div className="approved-wording"><span>Approved wording</span><p>{finding.approved_wording}</p></div>}{(finding.evidence_source_title || finding.evidence_excerpt) && <div className="evidence-box"><div className="evidence-box-heading"><BadgeCheck size={15} /><strong>{finding.evidence_source_title || 'Claim Passport evidence'}</strong></div>{finding.evidence_excerpt && <p>“{finding.evidence_excerpt}”</p>}{finding.evidence_reference && <small>Reference: {finding.evidence_reference}</small>}{finding.evidence_source_url && <a href={finding.evidence_source_url} target="_blank" rel="noreferrer">Open evidence source <Send size={12} /></a>}</div>}<div className="finding-action"><span>Suggested next step</span><p>{finding.recommended_action}</p></div></article>)}</div>}
                  </>
                )}
              </section>

              <section className="workflow-section-block"><div className="workflow-section-heading"><div><p className="eyebrow">REVISION DISCUSSION</p><h3>Comments</h3></div><span className="revision-tag">{comments.length}</span></div>{comments.length === 0 ? <p className="workflow-muted-copy">No comments have been added to this revision.</p> : <div className="comment-list">{comments.map((comment) => <article className="comment-item" key={comment.id}><div className="comment-avatar"><MessageSquareText size={14} /></div><div><p>{comment.body}</p><small>{comment.created_by === user?.id ? 'You' : `Member ${comment.created_by.slice(0, 8)}`} · {formatDate(comment.created_at)}</small></div></article>)}</div>}<form className="comment-form" onSubmit={handleThreadComment}><input value={threadComment} onChange={(event: { target: { value: string } }) => setThreadComment(event.target.value)} placeholder="Add a comment to this exact revision..." maxLength={5000} aria-label="Add revision comment" /><button className="button button-secondary" type="submit" disabled={!threadComment.trim() || busy !== ''}>{busy === 'comment' ? <LoaderCircle className="spin-icon" size={15} /> : <Send size={15} />} Comment</button></form></section>

              <section className="review-decision-panel"><div className="review-decision-header"><div className="review-decision-icon"><ShieldCheck size={21} /></div><div><p className="eyebrow">HUMAN DECISION</p><h3>What is your review outcome?</h3><p>The decision applies to revision {currentRevision?.revision_number ?? '—'} and its latest analysis.</p></div></div><label className="workflow-field"><span>Reviewer note <small>(optional for approval; recommended for changes or rejection)</small></span><textarea value={reviewComment} onChange={(event: { target: { value: string } }) => setReviewComment(event.target.value)} rows={3} maxLength={5000} placeholder="Explain your decision and what the Creator should do next..." /></label><div className="decision-buttons"><button className="button decision-button decision-button--approve" type="button" disabled={decisionDisabled} onClick={() => void handleDecision('approved')}>{busy === 'approved' ? <LoaderCircle className="spin-icon" size={16} /> : <ThumbsUp size={16} />} Approve</button><button className="button decision-button decision-button--changes" type="button" disabled={decisionDisabled} onClick={() => void handleDecision('changes_requested')}>{busy === 'changes_requested' ? <LoaderCircle className="spin-icon" size={16} /> : <Undo2 size={16} />} Request changes</button><button className="button decision-button decision-button--reject" type="button" disabled={decisionDisabled} onClick={() => void handleDecision('rejected')}>{busy === 'rejected' ? <LoaderCircle className="spin-icon" size={16} /> : <ThumbsDown size={16} />} Reject</button></div>{!hasCurrentAnalysis && <p className="workflow-helper">A review decision is disabled until an analysis for the current submitted revision is available.</p>}</section>

              <section className="workflow-section-block"><div className="workflow-section-heading"><div><p className="eyebrow">ACCOUNTABILITY</p><h3>Review & activity history</h3></div><History size={17} /></div>{decisions.length > 0 && <div className="revision-history-list review-history-list">{decisions.map((decision) => <div className="revision-history-item" key={decision.id}><span className="revision-history-number">{decision.decision === 'approved' ? '✓' : decision.decision === 'rejected' ? '×' : '↺'}</span><div><strong>{decisionLabel(decision.decision)}</strong><small>{formatDate(decision.created_at)} · reviewer {decision.reviewer_id.slice(0, 8)}</small>{decision.reviewer_comment && <p>{decision.reviewer_comment}</p>}</div></div>)}</div>}{events.length > 0 && <div className="audit-list">{events.slice(0, 8).map((event) => <div className="audit-item" key={event.id}><span className="audit-dot" /><div><strong>{event.event_type.replaceAll('_', ' ')}</strong><small>{formatDate(event.created_at)} · {event.actor_id === user?.id ? 'You' : event.actor_id.slice(0, 8)}</small></div></div>)}</div>}{decisions.length === 0 && events.length === 0 && <p className="workflow-muted-copy">No previous review events.</p>}</section>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
