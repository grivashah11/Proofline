from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RevisionDiffOperation(BaseModel):
    operation: Literal["equal", "insert", "delete", "replace"]
    from_start_line: int
    from_end_line: int
    to_start_line: int
    to_end_line: int
    from_lines: list[str] = Field(default_factory=list)
    to_lines: list[str] = Field(default_factory=list)


class RevisionDiffSummary(BaseModel):
    inserted_lines: int = 0
    deleted_lines: int = 0
    unchanged_lines: int = 0
    changed_blocks: int = 0


class RevisionDiffResponse(BaseModel):
    content_id: UUID
    from_revision_id: UUID
    from_revision_number: int
    to_revision_id: UUID
    to_revision_number: int
    summary: RevisionDiffSummary
    operations: list[RevisionDiffOperation] = Field(default_factory=list)


class FindingLifecycleEventRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    content_id: UUID
    lifecycle_id: UUID
    finding_id: UUID | None = None
    analysis_run_id: UUID | None = None
    revision_id: UUID | None = None
    event_type: Literal["opened", "persisted", "resolved", "reappeared"]
    actor_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime


class FindingLifecycleRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    content_id: UUID
    fingerprint: str
    source: str
    category: str
    source_id: UUID | None = None
    issue_title: str
    last_outcome: str
    last_severity: str
    status: Literal["open", "resolved"]
    occurrence_count: int
    reappeared_count: int
    first_finding_id: UUID | None = None
    latest_finding_id: UUID | None = None
    first_revision_id: UUID | None = None
    latest_revision_id: UUID | None = None
    resolved_revision_id: UUID | None = None
    first_analysis_run_id: UUID | None = None
    latest_analysis_run_id: UUID | None = None
    resolved_analysis_run_id: UUID | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None
    last_event: Literal["opened", "persisted", "resolved", "reappeared"]
    events: list[FindingLifecycleEventRecord] = Field(default_factory=list)


class RecurringIssuePattern(BaseModel):
    fingerprint: str
    source: str
    category: str
    source_id: UUID | None = None
    title: str
    distinct_submissions: int
    total_occurrences: int
    open_submissions: int
    resolved_submissions: int
    reappeared_submissions: int
    last_seen_at: datetime


class GuidelineGapCandidate(BaseModel):
    fingerprint: str
    rule_id: UUID | None = None
    category: Literal["messaging", "brand_voice", "channel_guidance"]
    current_guideline_title: str
    distinct_submissions: int
    total_occurrences: int
    suggested_clarification: str
    requires_owner_confirmation: bool = True


class EvidenceGapCandidate(BaseModel):
    fingerprint: str
    subject: str | None = None
    attribute: str | None = None
    distinct_submissions: int
    total_occurrences: int
    suggested_action: str
    requires_owner_confirmation: bool = True


class FindingResolutionSummary(BaseModel):
    open_threads: int = 0
    resolved_threads: int = 0
    reappeared_threads: int = 0


class GovernanceInsightsResponse(BaseModel):
    workspace_id: UUID
    window_days: int
    generated_at: datetime
    min_distinct_submissions: int
    resolution_summary: FindingResolutionSummary
    recurring_issues: list[RecurringIssuePattern] = Field(default_factory=list)
    candidate_guideline_gaps: list[GuidelineGapCandidate] = Field(default_factory=list)
    evidence_gaps: list[EvidenceGapCandidate] = Field(default_factory=list)
