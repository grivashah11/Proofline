from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FindingSource(str, Enum):
    TERMINOLOGY = "terminology"
    BRAND_RULE = "brand_rule"


class FindingCategory(str, Enum):
    TERMINOLOGY = "terminology"
    MESSAGING = "messaging"
    BRAND_VOICE = "brand_voice"
    CHANNEL_GUIDANCE = "channel_guidance"


class FindingOutcome(str, Enum):
    CONFLICT = "conflict"
    NEEDS_REVIEW = "needs_review"


class FindingSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class RuleCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=50000)
    channel: str | None = Field(default=None, max_length=80)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Content cannot be empty.")
        return value

    @field_validator("channel")
    @classmethod
    def normalize_channel(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class RuleFinding(BaseModel):
    finding_id: UUID = Field(default_factory=uuid4)
    source: FindingSource
    source_id: UUID
    category: FindingCategory
    outcome: FindingOutcome
    severity: FindingSeverity

    title: str
    message: str
    recommended_action: str

    start_index: int | None = None
    end_index: int | None = None
    matched_text: str | None = None


class RuleCheckResponse(BaseModel):
    workspace_id: UUID
    content_length: int
    channel: str | None

    checks_run: int
    passed_checks: int
    conflict_count: int
    needs_review_count: int

    recognized_preferred_terms: list[str] = Field(default_factory=list)
    findings: list[RuleFinding] = Field(default_factory=list)
