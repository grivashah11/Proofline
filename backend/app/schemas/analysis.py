
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalysisRunState(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"


class AIExtractionState(str, Enum):
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"


class AnalysisFindingSource(str, Enum):
    TERMINOLOGY = "terminology"
    BRAND_RULE = "brand_rule"
    CLAIM_PASSPORT = "claim_passport"
    AI_CLAIM = "ai_claim"


class AnalysisFindingOutcome(str, Enum):
    SUPPORTED = "supported"
    CONFLICT = "conflict"
    REVIEW_DUE = "review_due"
    NEEDS_VERIFICATION = "needs_verification"
    NEEDS_REVIEW = "needs_review"


class AnalysisFindingSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AnalysisFindingRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    analysis_run_id: UUID
    revision_id: UUID
    finding_number: int

    source: AnalysisFindingSource
    source_id: UUID | None = None

    category: str
    outcome: AnalysisFindingOutcome
    severity: AnalysisFindingSeverity

    title: str
    message: str
    recommended_action: str

    start_index: int | None = None
    end_index: int | None = None
    matched_text: str | None = None
    source_span_verified: bool

    candidate_claim: dict | None = None

    passport_id: UUID | None = None
    passport_version_id: UUID | None = None
    passport_version_number: int | None = None

    approved_wording: str | None = None
    evidence_source_title: str | None = None
    evidence_source_url: str | None = None
    evidence_reference: str | None = None
    evidence_excerpt: str | None = None

    created_at: datetime


class AnalysisRunRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    content_id: UUID
    revision_id: UUID
    run_number: int

    model: str
    status: AnalysisRunState
    ai_extraction_status: AIExtractionState

    content_length: int
    channel: str | None = None

    rule_checks_run: int
    rule_passed_checks: int
    rule_conflict_count: int
    rule_needs_review_count: int

    claim_supported_count: int
    claim_conflict_count: int
    claim_review_due_count: int
    claim_needs_verification_count: int

    human_approval_required: bool = True

    created_by: UUID
    created_at: datetime


class AnalysisDetail(BaseModel):
    analysis: AnalysisRunRecord
    findings: list[AnalysisFindingRecord] = Field(default_factory=list)
