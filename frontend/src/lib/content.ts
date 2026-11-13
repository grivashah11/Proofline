import { apiRequest } from './api'

export type ContentType = 'social_post' | 'advertisement' | 'email' | 'document' | 'other'
export type ContentStatus = 'draft' | 'in_review' | 'approved' | 'changes_requested' | 'rejected' | 'archived'
export type ReviewDecision = 'approved' | 'changes_requested' | 'rejected'
export type FindingOutcome = 'supported' | 'conflict' | 'review_due' | 'needs_verification' | 'needs_review'
export type FindingSeverity = 'error' | 'warning' | 'info'
export type FindingSource = 'terminology' | 'brand_rule' | 'claim_passport' | 'ai_claim'

export type ContentRecord = {
  id: string
  workspace_id: string
  title: string
  content_type: ContentType
  product_context: string | null
  channel: string | null
  market: string | null
  status: ContentStatus
  current_revision_id: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export type ContentRevision = {
  id: string
  workspace_id: string
  content_id: string
  revision_number: number
  content_text: string
  created_by: string
  created_at: string
}

export type ContentDetail = {
  content: ContentRecord
  revisions: ContentRevision[]
}

export type ExtractedClaim = {
  exact_text: string
  subject: string
  attribute: string
  claim_kind: 'factual' | 'promotional'
  value_text: string | null
  numeric_value: string | null
  unit: string | null
  qualifier: string | null
  conditions: string | null
  product_scope: string | null
  channel_scope: string | null
  market_scope: string | null
  extraction_note: string
}

export type AnalysisFinding = {
  id: string
  workspace_id: string
  analysis_run_id: string
  revision_id: string
  finding_number: number
  source: FindingSource
  source_id: string | null
  category: string
  outcome: FindingOutcome
  severity: FindingSeverity
  title: string
  message: string
  recommended_action: string
  start_index: number | null
  end_index: number | null
  matched_text: string | null
  source_span_verified: boolean
  candidate_claim: ExtractedClaim | Record<string, unknown> | null
  passport_id: string | null
  passport_version_id: string | null
  passport_version_number: number | null
  approved_wording: string | null
  evidence_source_title: string | null
  evidence_source_url: string | null
  evidence_reference: string | null
  evidence_excerpt: string | null
  created_at: string
}

export type AnalysisRun = {
  id: string
  workspace_id: string
  content_id: string
  revision_id: string
  run_number: number
  model: string
  status: 'completed' | 'partial'
  ai_extraction_status: 'completed' | 'unavailable'
  content_length: number
  channel: string | null
  rule_checks_run: number
  rule_passed_checks: number
  rule_conflict_count: number
  rule_needs_review_count: number
  claim_supported_count: number
  claim_conflict_count: number
  claim_review_due_count: number
  claim_needs_verification_count: number
  human_approval_required: boolean
  created_by: string
  created_at: string
}

export type AnalysisDetail = {
  analysis: AnalysisRun
  findings: AnalysisFinding[]
}

export type ReviewDecisionRecord = {
  id: string
  workspace_id: string
  content_id: string
  revision_id: string
  analysis_run_id: string
  decision: ReviewDecision
  reviewer_comment: string | null
  reviewer_id: string
  created_at: string
}

export type ContentComment = {
  id: string
  workspace_id: string
  content_id: string
  revision_id: string
  body: string
  created_by: string
  created_at: string
}

export type AuditEvent = {
  id: string
  workspace_id: string
  content_id: string
  revision_id: string | null
  event_type: string
  actor_id: string
  details: Record<string, unknown>
  created_at: string
}

export type WorkspaceMember = {
  workspace_id: string
  user_id: string
  role: 'brand_owner' | 'creator'
  invited_by: string | null
  joined_at: string
}

export type ContentWithRevision = {
  content: ContentRecord
  revision: ContentRevision
}

export type ReviewSubmissionResult = {
  content: ContentRecord
  analysis_run_id: string
  analysis_status: 'completed' | 'partial'
}

export type ReviewDecisionResult = {
  content: ContentRecord
  decision: ReviewDecisionRecord
}

const workspacePath = (workspaceId: string) => `/api/v1/workspaces/${workspaceId}`
const contentPath = (workspaceId: string, contentId: string) =>
  `${workspacePath(workspaceId)}/contents/${contentId}`

export function listContents(workspaceId: string) {
  return apiRequest<ContentRecord[]>(`${workspacePath(workspaceId)}/contents`)
}

export function createContent(
  workspaceId: string,
  payload: {
    title: string
    content_type: ContentType
    product_context: string | null
    channel: string | null
    market: string | null
    content_text: string
  },
) {
  return apiRequest<ContentWithRevision>(`${workspacePath(workspaceId)}/contents`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getContent(workspaceId: string, contentId: string) {
  return apiRequest<ContentDetail>(contentPath(workspaceId, contentId))
}

export function createRevision(workspaceId: string, contentId: string, contentText: string) {
  return apiRequest<ContentWithRevision>(`${contentPath(workspaceId, contentId)}/revisions`, {
    method: 'POST',
    body: JSON.stringify({ content_text: contentText }),
  })
}

export function listAnalyses(workspaceId: string, contentId: string) {
  return apiRequest<AnalysisRun[]>(`${contentPath(workspaceId, contentId)}/analyses`)
}

export function getAnalysis(workspaceId: string, contentId: string, analysisId: string) {
  return apiRequest<AnalysisDetail>(`${contentPath(workspaceId, contentId)}/analyses/${analysisId}`)
}

export function runAnalysis(workspaceId: string, contentId: string) {
  return apiRequest<AnalysisDetail>(`${contentPath(workspaceId, contentId)}/analyses`, {
    method: 'POST',
  })
}

export function submitForReview(workspaceId: string, contentId: string) {
  return apiRequest<ReviewSubmissionResult>(`${contentPath(workspaceId, contentId)}/submit-for-review`, {
    method: 'POST',
  })
}

export function getReviewQueue(workspaceId: string) {
  return apiRequest<ContentRecord[]>(`${workspacePath(workspaceId)}/review-queue`)
}

export function listReviewDecisions(workspaceId: string, contentId: string) {
  return apiRequest<ReviewDecisionRecord[]>(`${contentPath(workspaceId, contentId)}/reviews`)
}

export function recordReviewDecision(
  workspaceId: string,
  contentId: string,
  payload: { decision: ReviewDecision; reviewer_comment: string | null },
) {
  return apiRequest<ReviewDecisionResult>(`${contentPath(workspaceId, contentId)}/reviews`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listComments(workspaceId: string, contentId: string, revisionId: string) {
  return apiRequest<ContentComment[]>(
    `${contentPath(workspaceId, contentId)}/revisions/${revisionId}/comments`,
  )
}

export function addComment(
  workspaceId: string,
  contentId: string,
  revisionId: string,
  body: string,
) {
  return apiRequest<ContentComment>(
    `${contentPath(workspaceId, contentId)}/revisions/${revisionId}/comments`,
    { method: 'POST', body: JSON.stringify({ body }) },
  )
}

export function listAuditEvents(workspaceId: string, contentId: string) {
  return apiRequest<AuditEvent[]>(`${contentPath(workspaceId, contentId)}/audit-events`)
}

export function listWorkspaceMembers(workspaceId: string) {
  return apiRequest<WorkspaceMember[]>(`${workspacePath(workspaceId)}/members`)
}

export function addWorkspaceMember(
  workspaceId: string,
  payload: { user_id: string; role: 'brand_owner' | 'creator' },
) {
  return apiRequest<WorkspaceMember>(`${workspacePath(workspaceId)}/members`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateWorkspaceMember(
  workspaceId: string,
  userId: string,
  role: 'brand_owner' | 'creator',
) {
  return apiRequest<WorkspaceMember>(`${workspacePath(workspaceId)}/members/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify({ role }),
  })
}

export function removeWorkspaceMember(workspaceId: string, userId: string) {
  return apiRequest<void>(`${workspacePath(workspaceId)}/members/${userId}`, {
    method: 'DELETE',
  })
}

export function statusLabel(status: ContentStatus) {
  const labels: Record<ContentStatus, string> = {
    draft: 'Draft',
    in_review: 'In review',
    approved: 'Approved',
    changes_requested: 'Changes requested',
    rejected: 'Rejected',
    archived: 'Archived',
  }
  return labels[status]
}

export function outcomeLabel(outcome: FindingOutcome) {
  const labels: Record<FindingOutcome, string> = {
    supported: 'Supported',
    conflict: 'Conflict',
    review_due: 'Review due',
    needs_verification: 'Needs verification',
    needs_review: 'Needs review',
  }
  return labels[outcome]
}

export function decisionLabel(decision: ReviewDecision) {
  const labels: Record<ReviewDecision, string> = {
    approved: 'Approved',
    changes_requested: 'Changes requested',
    rejected: 'Rejected',
  }
  return labels[decision]
}
