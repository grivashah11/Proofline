from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.analysis import AnalysisRunState
from app.schemas.contents import ContentRecord


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class ContentCommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Comment cannot be empty.")

        return value


class ReviewDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecision
    reviewer_comment: str | None = Field(default=None, max_length=5000)

    @field_validator("reviewer_comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return value.strip() or None


class ContentCommentRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    content_id: UUID
    revision_id: UUID
    body: str
    created_by: UUID
    created_at: datetime


class ReviewDecisionRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    content_id: UUID
    revision_id: UUID
    analysis_run_id: UUID
    decision: ReviewDecision
    reviewer_comment: str | None = None
    reviewer_id: UUID
    created_at: datetime


class ReviewSubmissionResult(BaseModel):
    content: ContentRecord
    analysis_run_id: UUID
    analysis_status: AnalysisRunState


class ReviewDecisionResult(BaseModel):
    content: ContentRecord
    decision: ReviewDecisionRecord


class AuditEventRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    content_id: UUID
    revision_id: UUID | None = None
    event_type: str
    actor_id: UUID
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
