from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class BrandRuleKind(str, Enum):
    BRAND_VOICE = "brand_voice"
    MESSAGING = "messaging"
    CHANNEL_GUIDANCE = "channel_guidance"
    OTHER = "other"


class BrandRuleState(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class BrandRuleCheckType(str, Enum):
    MANUAL_REVIEW = "manual_review"
    CONTAINS_PHRASE = "contains_phrase"
    DOES_NOT_CONTAIN_PHRASE = "does_not_contain_phrase"
    MIN_CHARACTERS = "min_characters"
    MAX_CHARACTERS = "max_characters"


class TermEntryKind(str, Enum):
    PREFERRED = "preferred"
    REQUIRED = "required"
    RESTRICTED = "restricted"


def validate_brand_rule_configuration(
    rule_kind: str | BrandRuleKind,
    check_type: str | BrandRuleCheckType,
    check_value: str | None,
) -> None:
    kind = rule_kind.value if isinstance(rule_kind, BrandRuleKind) else rule_kind

    check = (
        check_type.value if isinstance(check_type, BrandRuleCheckType) else check_type
    )

    if kind not in {"messaging", "channel_guidance"} and check != "manual_review":
        raise ValueError(
            "Only messaging and channel guidance rules support automatic checks."
        )

    if check == "manual_review":
        if check_value is not None:
            raise ValueError(
                "Manual review rules must not have an automatic check value."
            )
        return

    if check in {"contains_phrase", "does_not_contain_phrase"}:
        if not check_value or not check_value.strip():
            raise ValueError("A phrase is required for this check type.")
        if len(check_value) > 500:
            raise ValueError("The configured phrase is too long.")
        return

    if check in {"min_characters", "max_characters"}:
        if check_value is None or not check_value.isdigit() or len(check_value) > 5:
            raise ValueError("A valid character limit is required.")

        number = int(check_value)

        if number > 50000:
            raise ValueError("Character limit cannot exceed 50000.")

        if check == "max_characters" and number < 1:
            raise ValueError("Maximum character limit must be positive.")
        return

    raise ValueError("Unsupported brand rule check type.")


class BrandRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_kind: BrandRuleKind
    title: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    rule_text: str = Field(min_length=1, max_length=10000)
    tone_examples: str = Field(default="", max_length=5000)
    channel: str | None = Field(default=None, max_length=80)

    check_type: BrandRuleCheckType = BrandRuleCheckType.MANUAL_REVIEW
    check_value: str | None = Field(default=None, max_length=500)

    @field_validator("title", "rule_text")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator("tone_examples")
    @classmethod
    def normalize_tone_examples(cls, value: str) -> str:
        return value.strip()

    @field_validator("description", "channel", "check_value")
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_check_configuration(self):
        if self.rule_kind == BrandRuleKind.BRAND_VOICE and not self.tone_examples.strip():
            raise ValueError("Brand voice rules must include at least one tone example.")
        validate_brand_rule_configuration(
            self.rule_kind,
            self.check_type,
            self.check_value,
        )
        return self


class BrandRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_kind: BrandRuleKind | None = None
    title: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    rule_text: str | None = Field(default=None, min_length=1, max_length=10000)
    tone_examples: str | None = Field(default=None, max_length=5000)
    channel: str | None = Field(default=None, max_length=80)
    state: BrandRuleState | None = None

    check_type: BrandRuleCheckType | None = None
    check_value: str | None = Field(default=None, max_length=500)

    @field_validator("title", "rule_text")
    @classmethod
    def normalize_required_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator("description", "tone_examples", "channel", "check_value")
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        return value.strip() or None


class BrandRuleRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    rule_kind: BrandRuleKind
    title: str
    description: str | None = None
    rule_text: str
    tone_examples: str = ""
    channel: str | None = None
    state: BrandRuleState
    check_type: BrandRuleCheckType
    check_value: str | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class TermEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term_type: TermEntryKind
    term: str = Field(min_length=1, max_length=200)
    preferred_replacement: str | None = Field(
        default=None,
        max_length=200,
    )
    explanation: str | None = Field(default=None, max_length=2000)
    case_sensitive: bool = False
    match_whole_word: bool = True

    @field_validator("term")
    @classmethod
    def normalize_term(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Term cannot be empty.")
        return value

    @field_validator("preferred_replacement", "explanation")
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def require_restricted_replacement(self):
        if (
            self.term_type == TermEntryKind.RESTRICTED
            and not self.preferred_replacement
        ):
            raise ValueError(
                "Restricted terminology must include a suggested replacement."
            )
        return self


class TermEntryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term_type: TermEntryKind | None = None
    term: str | None = Field(default=None, min_length=1, max_length=200)
    preferred_replacement: str | None = Field(
        default=None,
        max_length=200,
    )
    explanation: str | None = Field(default=None, max_length=2000)
    case_sensitive: bool | None = None
    match_whole_word: bool | None = None
    is_active: bool | None = None

    @field_validator("term")
    @classmethod
    def normalize_term(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Term cannot be empty.")
        return value

    @field_validator("preferred_replacement", "explanation")
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        return value.strip() or None


class TermEntryRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    term_type: TermEntryKind
    term: str
    preferred_replacement: str | None = None
    explanation: str | None = None
    case_sensitive: bool
    match_whole_word: bool
    is_active: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime
