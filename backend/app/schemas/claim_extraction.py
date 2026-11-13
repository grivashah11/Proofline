from enum import Enum
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.schemas.claim_passports import ClaimKind


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exact_text: str = Field(min_length=1, max_length=3000)
    subject: str = Field(min_length=1, max_length=300)
    attribute: str = Field(min_length=1, max_length=300)

    claim_kind: ClaimKind

    value_text: str | None = Field(default=None, max_length=500)
    numeric_value: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, max_length=80)

    qualifier: str | None = Field(default=None, max_length=500)
    conditions: str | None = Field(default=None, max_length=1000)

    product_scope: str | None = Field(default=None, max_length=300)
    channel_scope: str | None = Field(default=None, max_length=300)
    market_scope: str | None = Field(default=None, max_length=300)

    extraction_note: str

    @field_validator("exact_text")
    @classmethod
    def validate_exact_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Exact claim text cannot be empty.")
        return value

    @field_validator("subject", "attribute")
    @classmethod
    def normalize_required_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator(
        "value_text",
        "numeric_value",
        "unit",
        "qualifier",
        "conditions",
        "product_scope",
        "channel_scope",
        "market_scope",
    )
    @classmethod
    def normalize_optional_fields(cls, value: str | None):
        if value is None:
            return None
        return value.strip() or None

    @field_validator("numeric_value")
    @classmethod
    def validate_numeric_value(cls, value: str | None):
        if value is None:
            return None

        import re

        if not re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?", value):
            raise ValueError("Numeric value must be a plain decimal number.")

        return value


class AIClaimExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ExtractedClaim] = Field(max_length=50)


class PassportMatchStatus(str, Enum):
    SUPPORTED = "supported"
    CONFLICT = "conflict"
    REVIEW_DUE = "review_due"
    NEEDS_VERIFICATION = "needs_verification"


class ClaimAssessment(BaseModel):
    candidate: ExtractedClaim

    status: PassportMatchStatus
    source_span_verified: bool

    start_index: int | None = None
    end_index: int | None = None

    passport_id: UUID | None = None
    passport_code: str | None = None
    passport_version_id: UUID | None = None
    passport_version_number: int | None = None

    approved_wording: str | None = None
    evidence_source_title: str | None = None
    evidence_source_url: str | None = None
    evidence_reference: str | None = None
    evidence_excerpt: str | None = None

    explanation: str
    recommended_action: str


class ClaimExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=50000)
    channel: str | None = Field(default=None, max_length=80)
    market: str | None = Field(default=None, max_length=100)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Draft content cannot be empty.")
        return value

    @field_validator("channel", "market")
    @classmethod
    def normalize_context(cls, value: str | None):
        if value is None:
            return None
        return value.strip() or None


class ClaimExtractionResponse(BaseModel):
    workspace_id: UUID
    model: str

    extracted_claim_count: int
    supported_count: int
    conflict_count: int
    review_due_count: int
    needs_verification_count: int

    human_approval_required: bool = True

    assessments: list[ClaimAssessment] = Field(default_factory=list)
