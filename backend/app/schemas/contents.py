from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContentType(str, Enum):
    SOCIAL_POST = "social_post"
    ADVERTISEMENT = "advertisement"
    EMAIL = "email"
    DOCUMENT = "document"
    OTHER = "other"


class ContentStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ContentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    content_type: ContentType
    product_context: str | None = Field(default=None, max_length=300)
    channel: str | None = Field(default=None, max_length=80)
    market: str | None = Field(default=None, max_length=100)
    content_text: str = Field(min_length=1, max_length=50000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Content title cannot be empty.")
        return value

    @field_validator("content_text")
    @classmethod
    def validate_content_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Content cannot be empty.")
        return value

    @field_validator("product_context", "channel", "market")
    @classmethod
    def normalize_optional_context(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ContentRevisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_text: str = Field(min_length=1, max_length=50000)

    @field_validator("content_text")
    @classmethod
    def validate_content_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Content cannot be empty.")
        return value


class ContentRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    title: str
    content_type: ContentType
    product_context: str | None = None
    channel: str | None = None
    market: str | None = None
    status: ContentStatus
    current_revision_id: UUID | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class ContentRevisionRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    content_id: UUID
    revision_number: int
    content_text: str
    created_by: UUID
    created_at: datetime


class ContentWithRevision(BaseModel):
    content: ContentRecord
    revision: ContentRevisionRecord


class ContentDetail(BaseModel):
    content: ContentRecord
    revisions: list[ContentRevisionRecord]
