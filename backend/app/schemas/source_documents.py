from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceDocumentFormat(str, Enum):
    PDF = "PDF"
    DOCX = "DOCX"


class SourceLocationType(str, Enum):
    PAGE = "page"
    SECTION = "section"
    TABLE_ROW = "table_row"


class SourceDocumentRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    title: str = Field(min_length=1, max_length=300)
    original_filename: str = Field(min_length=1, max_length=255)
    mime_type: str
    document_format: SourceDocumentFormat
    file_size_bytes: int = Field(ge=1)
    sha256_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int | None = Field(default=None, ge=1)
    segment_count: int = Field(ge=1)
    extraction_warnings: list[str] = Field(default_factory=list)
    uploaded_by: UUID
    created_at: datetime


class SourceDocumentSegmentRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    source_document_id: UUID
    segment_index: int = Field(ge=1)
    location_type: SourceLocationType
    location_label: str = Field(min_length=1, max_length=500)
    page_number: int | None = Field(default=None, ge=1)
    section_path: str | None = Field(default=None, max_length=1000)
    paragraph_number: int | None = Field(default=None, ge=1)
    text_content: str = Field(min_length=1, max_length=20_000)
    sha256_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @field_validator("text_content")
    @classmethod
    def normalize_text_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Source segment text cannot be empty.")
        return value


class ClaimPassportVersionSourceRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    claim_passport_id: UUID
    passport_version_id: UUID
    source_document_id: UUID
    source_document_segment_id: UUID
    excerpt: str = Field(min_length=1, max_length=10_000)
    location_label_snapshot: str = Field(min_length=1, max_length=500)
    source_document_title_snapshot: str = Field(min_length=1, max_length=300)
    source_document_sha256_snapshot: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: UUID
    created_at: datetime


class ReverificationStatus(str, Enum):
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    EXPIRED = "expired"


class PassportReverificationReminder(BaseModel):
    passport_id: UUID
    passport_code: str
    subject: str
    version_id: UUID
    version_number: int
    review_by: date | None = None
    valid_until: date | None = None
    status: ReverificationStatus
    days_until_action: int
