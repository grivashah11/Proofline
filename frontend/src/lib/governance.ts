import { apiRequest } from './api'

export type RevisionDiffOperationType = 'equal' | 'insert' | 'delete' | 'replace'

export type RevisionDiffOperation = {
  operation: RevisionDiffOperationType
  from_start_line: number
  from_end_line: number
  to_start_line: number
  to_end_line: number
  from_lines: string[]
  to_lines: string[]
}

export type RevisionDiffResponse = {
  content_id: string
  from_revision_id: string
  from_revision_number: number
  to_revision_id: string
  to_revision_number: number
  summary: {
    inserted_lines: number
    deleted_lines: number
    unchanged_lines: number
    changed_blocks: number
  }
  operations: RevisionDiffOperation[]
}

export type FindingLifecycleEvent = {
  id: string
  workspace_id: string
  content_id: string
  lifecycle_id: string
  finding_id: string | null
  analysis_run_id: string | null
  revision_id: string | null
  event_type: 'opened' | 'persisted' | 'resolved' | 'reappeared'
  actor_id: string | null
  details: Record<string, unknown>
  created_at: string
}

export type FindingLifecycleRecord = {
  id: string
  workspace_id: string
  content_id: string
  fingerprint: string
  source: string
  category: string
  source_id: string | null
  issue_title: string
  last_outcome: string
  last_severity: string
  status: 'open' | 'resolved'
  occurrence_count: number
  reappeared_count: number
  first_finding_id: string | null
  latest_finding_id: string | null
  first_revision_id: string | null
  latest_revision_id: string | null
  resolved_revision_id: string | null
  first_analysis_run_id: string | null
  latest_analysis_run_id: string | null
  resolved_analysis_run_id: string | null
  first_seen_at: string
  last_seen_at: string
  resolved_at: string | null
  last_event: 'opened' | 'persisted' | 'resolved' | 'reappeared'
  events: FindingLifecycleEvent[]
}

export type RecurringIssuePattern = {
  fingerprint: string
  source: string
  category: string
  source_id: string | null
  title: string
  distinct_submissions: number
  total_occurrences: number
  open_submissions: number
  resolved_submissions: number
  reappeared_submissions: number
  last_seen_at: string
}

export type GuidelineGapCandidate = {
  fingerprint: string
  rule_id: string | null
  category: 'messaging' | 'brand_voice' | 'channel_guidance'
  current_guideline_title: string
  distinct_submissions: number
  total_occurrences: number
  suggested_clarification: string
  requires_owner_confirmation: boolean
}

export type EvidenceGapCandidate = {
  fingerprint: string
  subject: string | null
  attribute: string | null
  distinct_submissions: number
  total_occurrences: number
  suggested_action: string
  requires_owner_confirmation: boolean
}

export type GovernanceInsightsResponse = {
  workspace_id: string
  window_days: number
  generated_at: string
  min_distinct_submissions: number
  resolution_summary: {
    open_threads: number
    resolved_threads: number
    reappeared_threads: number
  }
  recurring_issues: RecurringIssuePattern[]
  candidate_guideline_gaps: GuidelineGapCandidate[]
  evidence_gaps: EvidenceGapCandidate[]
}

const workspacePath = (workspaceId: string) => `/api/v1/workspaces/${workspaceId}`
const contentPath = (workspaceId: string, contentId: string) =>
  `${workspacePath(workspaceId)}/contents/${contentId}`

export function getRevisionDiff(
  workspaceId: string,
  contentId: string,
  fromRevisionId: string,
  toRevisionId: string,
) {
  const query = new URLSearchParams({
    from_revision_id: fromRevisionId,
    to_revision_id: toRevisionId,
  })

  return apiRequest<RevisionDiffResponse>(
    `${contentPath(workspaceId, contentId)}/revision-diff?${query.toString()}`,
  )
}

export function getFindingLifecycle(workspaceId: string, contentId: string) {
  return apiRequest<FindingLifecycleRecord[]>(
    `${contentPath(workspaceId, contentId)}/finding-lifecycle?limit=200`,
  )
}

export function getGovernanceInsights(
  workspaceId: string,
  options: { windowDays: number; minDistinctSubmissions: number; limit?: number },
) {
  const query = new URLSearchParams({
    window_days: String(options.windowDays),
    min_distinct_submissions: String(options.minDistinctSubmissions),
    limit: String(options.limit ?? 50),
  })

  return apiRequest<GovernanceInsightsResponse>(
    `${workspacePath(workspaceId)}/governance/insights?${query.toString()}`,
  )
}
