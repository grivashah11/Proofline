from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ImageFormat(str, Enum):
    JPEG = "JPEG"
    PNG = "PNG"
    WEBP = "WEBP"


class AssetMatchStatus(str, Enum):
    EXACT_MATCH = "exact_match"
    NO_EXACT_MATCH = "no_exact_match"


class AltTextStatus(str, Enum):
    PROVIDED = "provided"
    MISSING = "missing"


class ImageFindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"


class PaletteColor(BaseModel):
    hex: str = Field(pattern=r"^#[0-9A-F]{6}$")
    percentage: float = Field(ge=0, le=100)


class ImageFinding(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    severity: ImageFindingSeverity
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    recommended_action: str = Field(min_length=1, max_length=1000)


class BrandAssetMatch(BaseModel):
    id: UUID
    asset_name: str
    description: str | None = None


class ImageCheckAnalysis(BaseModel):
    asset_match_status: AssetMatchStatus
    matched_asset: BrandAssetMatch | None = None
    dominant_colors: list[PaletteColor]
    alt_text_status: AltTextStatus
    findings: list[ImageFinding]
    limitations: list[str]


class BrandAssetRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    asset_name: str
    description: str | None = None
    original_filename: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    image_format: ImageFormat
    width: int
    height: int
    dominant_colors: list[PaletteColor]
    is_active: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class BrandAssetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @field_validator("asset_name")
    @classmethod
    def normalize_asset_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Asset name must contain at least two non-space characters.")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ImageCheckRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    workspace_id: UUID
    original_filename: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    image_format: ImageFormat
    width: int
    height: int
    alt_text: str | None = None
    analysis: ImageCheckAnalysis
    created_by: UUID
    created_at: datetime
