from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ClaimKind(str, Enum):
    FACTUAL = "factual"
    PROMOTIONAL = "promotional"


class ClaimPassportState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    REVIEW_DUE = "review_due"
    RETIRED = "retired"


class PassportVersionState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class ClaimPassportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passport_code: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Z0-9][A-Z0-9._-]{0,63}$",
    )

    subject: str = Field(min_length=1, max_length=300)
    claim_type: ClaimKind
    summary: str | None = Field(default=None, max_length=2000)

    @field_validator("passport_code", "subject")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty.")

        return value

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return value.strip() or None


class ClaimPassportRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    passport_code: str
    subject: str
    claim_type: ClaimKind
    summary: str | None = None
    status: ClaimPassportState
    current_version_id: UUID | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class PassportVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_wording: str = Field(min_length=1, max_length=3000)

    subject: str = Field(min_length=1, max_length=300)
    attribute: str = Field(min_length=1, max_length=300)

    permitted_value: str | None = Field(default=None, max_length=500)

    numeric_value: Decimal | None = Field(
        default=None,
        max_digits=20,
        decimal_places=6,
    )

    unit: str | None = Field(default=None, max_length=80)
    qualifier: str | None = Field(default=None, max_length=500)

    required_conditions: str | None = Field(
        default=None,
        max_length=3000,
    )

    product_scope: str | None = Field(default=None, max_length=300)
    channel_scope: str | None = Field(default=None, max_length=300)
    market_scope: str | None = Field(default=None, max_length=300)

    valid_from: date | None = None
    valid_until: date | None = None

    evidence_source_title: str | None = Field(
        default=None,
        max_length=500,
    )

    evidence_source_url: AnyHttpUrl | None = None

    evidence_reference: str | None = Field(
        default=None,
        max_length=1000,
    )

    evidence_excerpt: str | None = Field(
        default=None,
        max_length=10000,
    )

    evidence_source_version: str | None = Field(
        default=None,
        max_length=200,
    )

    review_by: date | None = None

    @field_validator(
        "approved_wording",
        "subject",
        "attribute",
    )
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty.")

        return value

    @field_validator(
        "permitted_value",
        "unit",
        "qualifier",
        "required_conditions",
        "product_scope",
        "channel_scope",
        "market_scope",
        "evidence_source_title",
        "evidence_reference",
        "evidence_excerpt",
        "evidence_source_version",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None):
        if value is None:
            return None

        return value.strip() or None

    @model_validator(mode="after")
    def validate_version_data(self):
        if self.numeric_value is not None and not self.unit:
            raise ValueError("A unit is required when a numeric value is provided.")

        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until < self.valid_from
        ):
            raise ValueError("valid_until cannot be earlier than valid_from.")

        return self


class PassportVersionRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    claim_passport_id: UUID

    version_number: int
    approved_wording: str

    subject: str
    attribute: str

    permitted_value: str | None = None
    numeric_value: Decimal | None = None
    unit: str | None = None
    qualifier: str | None = None

    required_conditions: str | None = None

    product_scope: str | None = None
    channel_scope: str | None = None
    market_scope: str | None = None

    valid_from: date | None = None
    valid_until: date | None = None

    evidence_source_title: str | None = None
    evidence_source_url: str | None = None
    evidence_reference: str | None = None
    evidence_excerpt: str | None = None
    evidence_source_version: str | None = None

    owner_id: UUID
    verified_by: UUID | None = None
    verified_at: datetime | None = None
    review_by: date | None = None

    status: PassportVersionState

    created_by: UUID
    created_at: datetime
    updated_at: datetime
