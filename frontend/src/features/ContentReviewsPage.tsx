import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  AlertCircle,
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  FilePlus2,
  FileText,
  ExternalLink,
  Info,
  LoaderCircle,
  MessageSquareText,
  RefreshCw,
  Save,
  Send,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../lib/auth-context'
import {
  addComment,
  addManualClaim,
  createContent,
  createRevision,
  getAnalysis,
  getContent,
  listAnalyses,
  listComments,
  listContents,
  listReviewDecisions,
  runAnalysis,
  statusLabel,
  outcomeLabel,
  submitForReview,
  type AnalysisDetail,
  type AnalysisFinding,
  type ExtractedClaim,
  type ManualClaimInput,
  type ContentComment,
  type ContentDetail,
  type ContentRecord,
  type ContentType,
  type ReviewDecisionRecord,
} from '../lib/content'
import type { WorkspaceRole } from '../lib/workspaces'
import './WorkflowPages.css'

type Props = { workspaceId: string; role: WorkspaceRole }
type DraftForm = {
  title: string
  content_type: ContentType
  product_context: string
  channel: string
  market: string
  content_text: string
}

const blankDraft: DraftForm = {
  title: '',
  content_type: 'social_post',
  product_context: '',
  channel: 'Instagram',
  market: 'India',
  content_text: '',
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

function contentTypeLabel(value: ContentType) {
  const labels: Record<ContentType, string> = {
    social_post: 'Social post', advertisement: 'Advertisement', email: 'Email', document: 'Document', other: 'Other',
  }
  return labels[value]
}

function findingSourceLabel(source: AnalysisFinding['source']) {
  if (source === 'claim_passport') return 'Claim Passport comparison'
  if (source === 'ai_claim') return 'AI-extracted claim'
  if (source === 'terminology') return 'Terminology rule'
  return 'Brand guideline'
}

function FindingCard({ finding }: { finding: AnalysisFinding }) {
  const candidate = finding.candidate_claim && typeof finding.candidate_claim === 'object'
    ? finding.candidate_claim as Partial<ExtractedClaim>
    : null
  const isClaimFinding = finding.source === 'claim_passport' || finding.source === 'ai_claim'
  const hasEvidence = Boolean(finding.evidence_source_title || finding.evidence_excerpt || finding.evidence_source_url || finding.evidence_reference)
  const excerpt = finding.matched_text || candidate?.exact_text || null

  return (
    <article className={`finding-card finding-${finding.outcome}`}>
      <div className="finding-card-top">
        <div className="finding-title-wrap">
          <span className={`finding-severity severity-${finding.severity}`}>{finding.severity}</span>
          <strong>{finding.title}</strong>
        </div>
        <span className={`outcome-pill outcome-${finding.outcome}`}>{outcomeLabel(finding.outcome)}</span>
      </div>

      <div className="finding-source-label"><Info size={12} /> Checked against: {findingSourceLabel(finding.source)}</div>

      <div className="finding-explanation-block">
        <span>What Proofline found</span>
        <p>{finding.message}</p>
        {excerpt && <blockquote className="finding-excerpt">“{excerpt}”</blockquote>}
      </div>

      {candidate && (candidate.subject || candidate.attribute) && (
        <div className="candidate-claim">
          <span>Extracted claim details</span>
          <strong>{[candidate.subject, candidate.attribute].filter(Boolean).join(' · ')}</strong>
          {(candidate.numeric_value || candidate.value_text || candidate.unit || candidate.qualifier) && (
            <small>
              {[candidate.qualifier, candidate.numeric_value || candidate.value_text, candidate.unit].filter(Boolean).join(' ')}
            </small>
          )}
        </div>
      )}

      {finding.approved_wording && (
        <div className="approved-wording">
          <span>Approved wording in the Passport</span>
          <p>{finding.approved_wording}</p>
        </div>
      )}

      {finding.passport_version_number && (
        <div className="finding-passport-reference">
          <BadgeCheck size={14} />
          Matched evidence record · Passport version {finding.passport_version_number}
        </div>
      )}

      <div className="finding-evidence-explainer">
        <span>What evidence was used?</span>
        {hasEvidence ? (
          <div className="evidence-box">
            <div className="evidence-box-heading">
              <BadgeCheck size={15} />
              <strong>{finding.evidence_source_title || 'Claim Passport evidence'}</strong>
            </div>
            {finding.evidence_excerpt && <p>“{finding.evidence_excerpt}”</p>}
            {finding.evidence_reference && <small>Reference: {finding.evidence_reference}</small>}
            {finding.evidence_source_url && (
              <a href={finding.evidence_source_url} target="_blank" rel="noreferrer">
                Open evidence source <ExternalLink size={13} />
              </a>
            )}
          </div>
        ) : isClaimFinding ? (
          <div className="finding-no-evidence">
            No active Claim Passport evidence was matched to this claim. This means the claim needs human verification; it does not by itself mean the claim is false.
            {finding.passport_id && <small>Passport record: {finding.passport_id.slice(0, 8)}</small>}
          </div>
        ) : (
          <div className="finding-rule-source">
            This finding comes from the configured {findingSourceLabel(finding.source).toLowerCase()} in this workspace. No external evidence source was attached to this rule finding.
          </div>
        )}
      </div>

      <div className="finding-action">
        <span>What should happen next?</span>
        <p>{finding.recommended_action}</p>
      </div>
    </article>
  )
}

export default function ContentReviewsPage({ workspaceId, role }: Props) {
  const { user } = useAuth()
  const [items, setItems] = useState<ContentRecord[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [detail, setDetail] = useState<ContentDetail | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null)
  const [comments, setComments] = useState<ContentComment[]>([])
  const [decisions, setDecisions] = useState<ReviewDecisionRecord[]>([])
  const [editorText, setEditorText] = useState('')
  const [commentText, setCommentText] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [newDraft, setNewDraft] = useState<DraftForm>(blankDraft)
  const [loadedWorkspaceId, setLoadedWorkspaceId] = useState('')
  const loading = loadedWorkspaceId !== workspaceId
  const [detailReloadKey, setDetailReloadKey] = useState(0)
  const [loadedDetailKey, setLoadedDetailKey] = useState('')
  const detailKey = `${workspaceId}:${selectedId}:${detailReloadKey}`
  const detailLoading = Boolean(selectedId) && loadedDetailKey !== detailKey
  const [busy, setBusy] = useState<'create' | 'save' | 'analyse' | 'submit' | 'comment' | ''>('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [filter, setFilter] = useState('all')

  const currentRevision = useMemo(() => {
    if (!detail) return null
    return detail.revisions.find((revision) => revision.id === detail.content.current_revision_id)
      ?? detail.revisions[0]
      ?? null
  }, [detail])

  const isDirty = Boolean(currentRevision && editorText !== currentRevision.content_text)
  const canEdit = detail?.content.status === 'draft' || detail?.content.status === 'changes_requested'
  const analysisMatchesCurrent = Boolean(
    analysis && currentRevision && analysis.analysis.revision_id === currentRevision.id,
  )
  const canSubmit = Boolean(
    detail && currentRevision && analysisMatchesCurrent && !isDirty
      && ['draft', 'changes_requested'].includes(detail.content.status),
  )

  const refreshList = useCallback(async (preferredId?: string) => {
    const records = await listContents(workspaceId)
    setItems(records)
    const nextId = preferredId && records.some((item) => item.id === preferredId)
      ? preferredId
      : selectedId && records.some((item) => item.id === selectedId)
        ? selectedId
        : records[0]?.id ?? ''
    setSelectedId(nextId)
    return records
  }, [workspaceId, selectedId])

  useEffect(() => {
    let active = true
    listContents(workspaceId)
      .then((records) => {
        if (!active) return
        setItems(records)
        const nextId = records[0]?.id ?? ''
        setSelectedId(nextId)
        if (!nextId) {
          setDetail(null)
          setAnalysis(null)
          setComments([])
          setDecisions([])
          setEditorText('')
        }
        setError('')
      })
      .catch((err: unknown) => {
        if (active) {
          setItems([])
          setSelectedId('')
          setDetail(null)
          setAnalysis(null)
          setComments([])
          setDecisions([])
          setEditorText('')
          setError(getErrorMessage(err))
        }
      })
      .finally(() => {
        if (active) setLoadedWorkspaceId(workspaceId)
      })
    return () => { active = false }
  }, [workspaceId])

  useEffect(() => {
    if (loading || !selectedId) return
    let active = true

    async function loadSelected() {
      try {
        const [loadedDetail, runs, reviewRecords] = await Promise.all([
          getContent(workspaceId, selectedId),
          listAnalyses(workspaceId, selectedId),
          listReviewDecisions(workspaceId, selectedId),
        ])
        if (!active) return

        setDetail(loadedDetail)
        setDecisions(reviewRecords)
        const revision = loadedDetail.revisions.find((item) => item.id === loadedDetail.content.current_revision_id)
          ?? loadedDetail.revisions[0]
          ?? null
        setEditorText(revision?.content_text ?? '')

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

  const filteredItems = useMemo(
    () => filter === 'all' ? items : items.filter((item) => item.status === filter),
    [filter, items],
  )

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSuccess('')
    if (!newDraft.title.trim() || !newDraft.content_text.trim()) {
      setError('Add a title and draft content before saving.')
      return
    }
    setBusy('create')
    try {
      const created = await createContent(workspaceId, {
        title: newDraft.title.trim(),
        content_type: newDraft.content_type,
        product_context: newDraft.product_context.trim() || null,
        channel: newDraft.channel.trim() || null,
        market: newDraft.market.trim() || null,
        content_text: newDraft.content_text,
      })
      setNewDraft(blankDraft)
      setShowCreate(false)
      await refreshList(created.content.id)
      setSuccess('Your draft was saved. Run the checks when you are ready.')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setBusy('')
    }
  }

  async function handleSaveRevision() {
    if (!detail || !editorText.trim()) return
    setError('')
    setSuccess('')
    setBusy('save')
    try {
      const saved = await createRevision(workspaceId, detail.content.id, editorText)
      setSuccess(`Revision ${saved.revision.revision_number} saved. Run the checks again for this revision.`)
      await refreshList(detail.content.id)
      setDetailReloadKey((current) => current + 1)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setBusy('')
    }
  }

  async function handleAnalyse() {
    if (!detail || !currentRevision || isDirty) return
    setError('')
    setSuccess('')
    setBusy('analyse')
    try {
      const result = await runAnalysis(workspaceId, detail.content.id)
      setAnalysis(result)
      setSuccess(`Checks completed for revision ${currentRevision.revision_number}. Review the findings below.`)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setBusy('')
    }
  }

  async function handleSubmit() {
    if (!detail || !canSubmit) return
    setError('')
    setSuccess('')
    setBusy('submit')
    try {
      await submitForReview(workspaceId, detail.content.id)
      await refreshList(detail.content.id)
      setDetailReloadKey((current) => current + 1)
      setSuccess('Submitted successfully. Your Brand Owner can now review this revision.')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setBusy('')
    }
  }

  async function handleComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!detail || !currentRevision || !commentText.trim()) return
    setError('')
    setBusy('comment')
    try {
      const added = await addComment(workspaceId, detail.content.id, currentRevision.id, commentText.trim())
      setComments((current) => [...current, added])
      setCommentText('')
      setSuccess('Comment added to this revision.')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setBusy('')
    }
  }

  const isOwner = role === 'brand_owner'

  return (
    <div className="workflow-page">
      <header className="workflow-header">
        <div>
          <p className="eyebrow">CREATOR WORKSPACE</p>
          <h1>Content reviews</h1>
          <p className="workflow-subtitle">Save a draft, check it against approved brand knowledge, and send the exact revision for human review.</p>
        </div>
        <button className="button button-primary" type="button" onClick={() => { setShowCreate((value) => !value); setError(''); setSuccess('') }}>
          <FilePlus2 size={16} /> {showCreate ? 'Close form' : 'New submission'}
        </button>
      </header>

      {isOwner && (
        <div className="workflow-notice workflow-notice--info">
          <ShieldCheck size={17} /> You are viewing the creator workflow as a Brand Owner. Use this to prepare a submission, then review it from the Review Queue.
          <Link to="/reviews">Open review queue <ArrowRight size={14} /></Link>
        </div>
      )}

      {error && <div className="workflow-alert workflow-alert--error" role="alert"><AlertCircle size={17} />{error}</div>}
      {success && <div className="workflow-alert workflow-alert--success" role="status"><CheckCircle2 size={17} />{success}</div>}

      {showCreate && (
        <form className="workflow-panel create-submission-panel" onSubmit={handleCreate}>
          <div className="workflow-panel-heading">
            <div><p className="eyebrow">NEW CONTENT</p><h2>Create a submission</h2></div>
            <span className="workflow-step-pill">STEP 01 · DRAFT</span>
          </div>
          <div className="content-create-guide">
            <div><span>1</span><p><strong>Save a draft</strong><small>Paste the content and choose its channel and market.</small></p></div>
            <div><span>2</span><p><strong>Run checks</strong><small>Proofline compares claims and language with approved brand knowledge.</small></p></div>
            <div><span>3</span><p><strong>Send for review</strong><small>An authorised reviewer makes the final decision on this revision.</small></p></div>
          </div>
          <div className="workflow-form-grid">
            <label className="workflow-field"><span>Submission title</span><input value={newDraft.title} onChange={(event: { target: { value: string } }) => setNewDraft((current) => ({ ...current, title: event.target.value }))} placeholder="e.g. Hydro Flask summer campaign" maxLength={200} required /></label>
            <label className="workflow-field"><span>Content type</span><select value={newDraft.content_type} onChange={(event: { target: { value: string } }) => setNewDraft((current) => ({ ...current, content_type: event.target.value as ContentType }))}><option value="social_post">Social post</option><option value="advertisement">Advertisement</option><option value="email">Email</option><option value="document">Document</option><option value="other">Other</option></select></label>
            <label className="workflow-field"><span>Product / subject context</span><input value={newDraft.product_context} onChange={(event: { target: { value: string } }) => setNewDraft((current) => ({ ...current, product_context: event.target.value }))} placeholder="e.g. Hydro Flask 24 oz Standard Mouth" maxLength={300} /></label>
            <label className="workflow-field"><span>Channel</span><input value={newDraft.channel} onChange={(event: { target: { value: string } }) => setNewDraft((current) => ({ ...current, channel: event.target.value }))} placeholder="e.g. Instagram" maxLength={80} /></label>
            <label className="workflow-field"><span>Market</span><input value={newDraft.market} onChange={(event: { target: { value: string } }) => setNewDraft((current) => ({ ...current, market: event.target.value }))} placeholder="e.g. India" maxLength={100} /></label>
          </div>
          <label className="workflow-field workflow-field--full"><span>Draft content</span><textarea value={newDraft.content_text} onChange={(event: { target: { value: string } }) => setNewDraft((current) => ({ ...current, content_text: event.target.value }))} placeholder="Paste the content you want Proofline to review..." rows={6} maxLength={50000} required /></label>
          <div className="workflow-form-footer"><span>{newDraft.content_text.length.toLocaleString('en-IN')} / 50,000 characters</span><button className="button button-primary" type="submit" disabled={busy === 'create'}>{busy === 'create' ? <LoaderCircle className="spin-icon" size={16} /> : <Save size={16} />} Save draft</button></div>
        </form>
      )}

      <div className="workflow-layout">
        <aside className="workflow-list-panel">
          <div className="workflow-list-heading"><div><p className="eyebrow">YOUR SUBMISSIONS</p><h2>Drafts & reviews</h2></div><button className="icon-button" type="button" aria-label="Refresh submissions" onClick={() => void refreshList()}><RefreshCw size={16} /></button></div>
          <div className="workflow-filter-row"><label htmlFor="content-filter">Status</label><select id="content-filter" value={filter} onChange={(event: { target: { value: string } }) => setFilter(event.target.value)}><option value="all">All submissions</option><option value="draft">Draft</option><option value="in_review">In review</option><option value="changes_requested">Changes requested</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select></div>
          {loading ? <div className="workflow-loading"><LoaderCircle className="spin-icon" size={21} />Loading submissions...</div> : filteredItems.length === 0 ? <div className="workflow-empty-small"><FileText size={23} /><strong>No submissions found</strong><span>Create your first content draft to begin.</span></div> : (
            <div className="workflow-submission-list">
              {filteredItems.map((item) => (
                <button key={item.id} type="button" className={`workflow-submission-item ${selectedId === item.id ? 'is-selected' : ''}`} onClick={() => { setSelectedId(item.id); setError(''); setSuccess('') }}>
                  <span className="submission-item-top"><span>{contentTypeLabel(item.content_type)}</span><span className={`status-pill status-${item.status}`}>{statusLabel(item.status)}</span></span>
                  <strong>{item.title}</strong>
                  <span className="submission-item-context">{item.product_context || 'No product context'}</span>
                  <span className="submission-item-bottom"><span>{item.channel || 'Channel not set'}</span><ChevronRight size={14} /></span>
                </button>
              ))}
            </div>
          )}
        </aside>

        <section className="workflow-detail-panel">
          {detailLoading ? <div className="workflow-loading workflow-loading--large"><LoaderCircle className="spin-icon" size={24} />Loading submission details...</div> : !detail ? (
            <div className="workflow-detail-empty"><div className="workflow-empty-icon"><FileCheck2Icon /></div><h2>Select a submission</h2><p>Choose a draft from the left or create a new submission to start checking content.</p></div>
          ) : (
            <>
              <div className="workflow-detail-heading">
                <div><p className="eyebrow">SUBMISSION DETAILS</p><h2>{detail.content.title}</h2><div className="workflow-meta-line"><span>{contentTypeLabel(detail.content.content_type)}</span><span>·</span><span>{detail.content.channel || 'No channel'}</span><span>·</span><span>{detail.content.market || 'No market'}</span></div></div>
                <span className={`status-pill status-${detail.content.status}`}>{statusLabel(detail.content.status)}</span>
              </div>

              <div className="workflow-stepper">
                <div className="workflow-step is-complete"><span><CheckCircle2 size={15} /></span><div><strong>Draft saved</strong><small>Revision {currentRevision?.revision_number ?? '—'}</small></div></div>
                <div className={`workflow-step ${analysisMatchesCurrent ? 'is-complete' : ''}`}><span>{analysisMatchesCurrent ? <CheckCircle2 size={15} /> : '2'}</span><div><strong>Run checks</strong><small>{analysisMatchesCurrent ? 'Analysis ready' : 'Awaiting analysis'}</small></div></div>
                <div className={`workflow-step ${detail.content.status === 'in_review' || detail.content.status === 'approved' ? 'is-complete' : ''}`}><span>{detail.content.status === 'in_review' || detail.content.status === 'approved' ? <CheckCircle2 size={15} /> : '3'}</span><div><strong>Human review</strong><small>{detail.content.status === 'in_review' ? 'With Brand Owner' : detail.content.status === 'approved' ? 'Approved' : 'Not submitted'}</small></div></div>
              </div>

              <section className="workflow-section-block">
                <div className="workflow-section-heading"><div><p className="eyebrow">CURRENT REVISION</p><h3>Review your content</h3></div><span className="revision-tag">{currentRevision ? `REVISION ${currentRevision.revision_number}` : 'NO REVISION'}</span></div>
                <label className="workflow-field"><textarea className="review-editor" value={editorText} onChange={(event: { target: { value: string } }) => setEditorText(event.target.value)} rows={8} disabled={!canEdit} aria-label="Current content revision" /></label>
                <div className="workflow-editor-footer"><span>{editorText.length.toLocaleString('en-IN')} characters{isDirty ? ' · Unsaved changes' : ' · Saved revision'}</span><div className="workflow-actions">{canEdit && <button className="button button-secondary" type="button" disabled={!isDirty || busy !== ''} onClick={() => void handleSaveRevision()}>{busy === 'save' ? <LoaderCircle className="spin-icon" size={15} /> : <Save size={15} />} Save new revision</button>}<button className="button button-primary" type="button" disabled={!currentRevision || isDirty || busy !== '' || !canEdit} onClick={() => void handleAnalyse()}>{busy === 'analyse' ? <LoaderCircle className="spin-icon" size={15} /> : <Sparkles size={15} />} Run checks</button></div></div>
                {!canEdit && <p className="workflow-helper">This submission is {statusLabel(detail.content.status).toLowerCase()}. Editing is available for drafts and submissions returned for changes.</p>}
              </section>

              <section className="workflow-section-block">
                <div className="workflow-section-heading"><div><p className="eyebrow">ANALYSIS RESULTS</p><h3>Findings and evidence</h3></div>{analysis && analysisMatchesCurrent && <span className={`analysis-state ${analysis.analysis.status === 'completed' ? 'analysis-state--good' : 'analysis-state--partial'}`}>{analysis.analysis.status === 'completed' ? 'Analysis complete' : 'Partial analysis'}</span>}</div>
                {!analysis || !analysisMatchesCurrent ? <div className="workflow-inline-empty"><Sparkles size={18} /><div><strong>No current analysis yet</strong><p>Save the latest revision, then run checks to see terminology, brand-rule and Claim Passport findings.</p></div></div> : (
                  <>
                    <div className="analysis-summary-grid">
                      <div><strong>{analysis.findings.length}</strong><span>Total findings</span></div>
                      <div><strong>{analysis.analysis.rule_conflict_count + analysis.analysis.claim_conflict_count}</strong><span>Conflicts</span></div>
                      <div><strong>{analysis.analysis.claim_supported_count}</strong><span>Supported claims</span></div>
                      <div><strong>{analysis.analysis.claim_needs_verification_count + analysis.analysis.claim_review_due_count}</strong><span>Need verification</span></div>
                    </div>
                    {analysis.analysis.ai_extraction_status === 'unavailable' && <div className="workflow-notice workflow-notice--warning"><CircleAlert size={16} />AI claim extraction was unavailable for this run. Deterministic brand checks are still shown; do not treat the absence of extracted claims as proof that all claims are supported.</div>}
                    {canEdit && <ManualClaimPanel workspaceId={workspaceId} contentId={detail.content.id} analysisId={analysis.analysis.id} onAdded={(updated) => { setAnalysis(updated); setSuccess('The missed claim was added and marked for verification.'); }} />}
                    <div className="finding-reading-guide">
                      <strong>How to read these results</strong>
                      <p><b>Supported</b> means the extracted fields match an active Passport. <b>Conflict</b> means a compared value or rule differs. <b>Needs verification</b> means evidence or a required detail could not be matched. <b>Needs review</b> means a person should assess the guidance. None of these findings replaces human approval.</p>
                    </div>
                    {analysis.findings.length === 0 ? <div className="workflow-inline-empty"><CheckCircle2 size={18} /><div><strong>No findings were returned</strong><p>This run did not identify any configured issues. This is not proof that every claim is true or approved. An authorised reviewer must still inspect the draft.</p></div></div> : (
                      <div className="finding-list">
                        {analysis.findings.map((finding) => (
                          <FindingCard finding={finding} key={finding.id} />
                        ))}
                      </div>
                    )}
                  </>
                )}
              </section>

              {detail.content.status === 'draft' || detail.content.status === 'changes_requested' ? (
                <section className="submit-review-bar"><div><ShieldCheck size={20} /><div><strong>Ready for a human decision?</strong><p>Submit this exact analysed revision to the Brand Owner. Findings are advisory; the reviewer decides.</p></div></div><button className="button button-primary" type="button" disabled={!canSubmit || busy !== ''} onClick={() => void handleSubmit()}>{busy === 'submit' ? <LoaderCircle className="spin-icon" size={16} /> : <Send size={16} />} Submit for review</button></section>
              ) : detail.content.status === 'in_review' ? <div className="workflow-notice workflow-notice--info"><Clock3 size={17} /> This revision is waiting for the Brand Owner. New edits can be made after the reviewer returns it for changes.</div> : null}

              <section className="workflow-section-block">
                <div className="workflow-section-heading"><div><p className="eyebrow">DISCUSSION</p><h3>Revision comments</h3></div><span className="revision-tag">{comments.length} COMMENTS</span></div>
                {comments.length === 0 ? <p className="workflow-muted-copy">No comments on the current revision yet.</p> : <div className="comment-list">{comments.map((comment) => <article className="comment-item" key={comment.id}><div className="comment-avatar"><MessageSquareText size={14} /></div><div><p>{comment.body}</p><small>{comment.created_by === user?.id ? 'You' : `Member ${comment.created_by.slice(0, 8)}`} · {formatDate(comment.created_at)}</small></div></article>)}</div>}
                {currentRevision && <form className="comment-form" onSubmit={handleComment}><input value={commentText} onChange={(event: { target: { value: string } }) => setCommentText(event.target.value)} placeholder="Add a note to this revision..." maxLength={5000} aria-label="Add a comment" /><button className="button button-secondary" type="submit" disabled={!commentText.trim() || busy !== ''}>{busy === 'comment' ? <LoaderCircle className="spin-icon" size={15} /> : <Send size={15} />} Comment</button></form>}
              </section>

              <section className="workflow-section-block revision-history-block">
                <div className="workflow-section-heading"><div><p className="eyebrow">VERSION HISTORY</p><h3>Saved revisions</h3></div><span className="revision-tag">{detail.revisions.length} VERSIONS</span></div>
                <div className="revision-history-list">{detail.revisions.map((revision) => <div className="revision-history-item" key={revision.id}><span className="revision-history-number">R{revision.revision_number}</span><div><strong>{revision.id === detail.content.current_revision_id ? 'Current revision' : 'Previous revision'}</strong><small>{formatDate(revision.created_at)} · {revision.content_text.length.toLocaleString('en-IN')} characters</small></div>{revision.id === detail.content.current_revision_id && <span className="current-version-dot" />}</div>)}</div>
                {decisions.length > 0 && <div className="decision-history"><strong>Latest reviewer decision</strong><span className={`outcome-pill outcome-${decisions[0].decision === 'approved' ? 'supported' : decisions[0].decision === 'rejected' ? 'conflict' : 'needs_review'}`}>{decisions[0].decision.replace('_', ' ')}</span>{decisions[0].reviewer_comment && <p>{decisions[0].reviewer_comment}</p>}</div>}
              </section>
            </>
          )}
        </section>
      </div>
    </div>
  )
}

type ManualClaimPanelProps = {
  workspaceId: string
  contentId: string
  analysisId: string
  onAdded: (analysis: AnalysisDetail) => void
}

function ManualClaimPanel({ workspaceId, contentId, analysisId, onAdded }: ManualClaimPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    exact_text: '',
    subject: '',
    attribute: '',
    claim_kind: 'factual' as ManualClaimInput['claim_kind'],
    value_text: '',
    numeric_value: '',
    unit: '',
    qualifier: '',
    conditions: '',
  })

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSaving(true)

    const payload: ManualClaimInput = {
      exact_text: form.exact_text.trim(),
      subject: form.subject.trim(),
      attribute: form.attribute.trim(),
      claim_kind: form.claim_kind,
      value_text: form.value_text.trim() || null,
      numeric_value: form.numeric_value.trim() || null,
      unit: form.unit.trim() || null,
      qualifier: form.qualifier.trim() || null,
      conditions: form.conditions.trim() || null,
    }

    try {
      const updated = await addManualClaim(workspaceId, contentId, analysisId, payload)
      onAdded(updated)
      setForm({
        exact_text: '', subject: '', attribute: '', claim_kind: 'factual',
        value_text: '', numeric_value: '', unit: '', qualifier: '', conditions: '',
      })
      setExpanded(false)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="manual-claim-panel">
      <button className="button button-secondary" type="button" onClick={() => setExpanded((value) => !value)}>
        <FilePlus2 size={16} /> {expanded ? 'Close manual claim form' : 'Add a missed claim manually'}
      </button>
      {expanded && (
        <form className="manual-claim-form" onSubmit={handleSubmit}>
          <div>
            <strong>Add a candidate claim</strong>
            <p>Copy the exact wording from the current draft. Proofline will save it as <b>Needs verification</b>; adding it manually does not approve the claim.</p>
          </div>
          <label className="workflow-field">
            Exact claim excerpt *
            <textarea rows={3} maxLength={3000} required value={form.exact_text} onChange={(event) => setForm({ ...form, exact_text: event.target.value })} placeholder="Paste the exact sentence or phrase from the draft..." />
          </label>
          <div className="manual-claim-grid">
            <label className="workflow-field">Subject *<input required maxLength={300} value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} placeholder="e.g. Hydro Flask bottle" /></label>
            <label className="workflow-field">Attribute *<input required maxLength={300} value={form.attribute} onChange={(event) => setForm({ ...form, attribute: event.target.value })} placeholder="e.g. cold retention" /></label>
            <label className="workflow-field">Claim type<select value={form.claim_kind} onChange={(event) => setForm({ ...form, claim_kind: event.target.value as ManualClaimInput['claim_kind'] })}><option value="factual">Factual</option><option value="promotional">Promotional</option></select></label>
            <label className="workflow-field">Claimed value<input maxLength={500} value={form.value_text} onChange={(event) => setForm({ ...form, value_text: event.target.value })} placeholder="e.g. 24" /></label>
            <label className="workflow-field">Numeric value<input maxLength={50} value={form.numeric_value} onChange={(event) => setForm({ ...form, numeric_value: event.target.value })} placeholder="e.g. 24" /></label>
            <label className="workflow-field">Unit<input maxLength={80} value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value })} placeholder="e.g. hours" /></label>
          </div>
          <label className="workflow-field">Qualifier (optional)<input maxLength={500} value={form.qualifier} onChange={(event) => setForm({ ...form, qualifier: event.target.value })} placeholder="e.g. up to" /></label>
          <label className="workflow-field">Conditions (optional)<textarea rows={2} maxLength={1000} value={form.conditions} onChange={(event) => setForm({ ...form, conditions: event.target.value })} placeholder="Any stated conditions or limitations..." /></label>
          {error && <div className="workflow-notice workflow-notice--warning" role="alert">{error}</div>}
          <div className="workflow-actions"><button className="button button-secondary" type="button" onClick={() => setExpanded(false)}>Cancel</button><button className="button button-primary" type="submit" disabled={saving}>{saving ? <LoaderCircle className="spin-icon" size={15} /> : <CheckCircle2 size={15} />} Add claim for verification</button></div>
        </form>
      )}
    </div>
  )
}

function FileCheck2Icon() {
  return <FileText size={26} />
}
