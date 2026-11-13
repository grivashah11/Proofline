import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.claim_passports import ClaimKind


class ManualClaimCreate(BaseModel):
    """A creator-supplied candidate claim copied from the current draft."""

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

    @field_validator("exact_text", "subject", "attribute")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator(
        "value_text", "numeric_value", "unit", "qualifier", "conditions",
        "product_scope", "channel_scope", "market_scope",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("numeric_value")
    @classmethod
    def validate_numeric_value(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?", value):
            raise ValueError("Numeric value must be a plain decimal number.")
        return value

    def to_candidate_claim(self) -> dict:
        return {
            **self.model_dump(mode="json"),
            "extraction_note": "Manually added by a workspace member; human verification is required.",
        }
