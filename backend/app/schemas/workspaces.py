from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkspaceRole(str, Enum):
    BRAND_OWNER = "brand_owner"
    CREATOR = "creator"


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(
        min_length=2,
        max_length=63,
        pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 2:
            raise ValueError("Workspace name is too short.")

        return value

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        value = value.strip().lower()

        if len(value) < 2:
            raise ValueError("Workspace slug is too short.")

        return value


class WorkspaceRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    name: str
    slug: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class WorkspaceListItem(BaseModel):
    workspace: WorkspaceRecord
    role: WorkspaceRole
    joined_at: datetime


class WorkspaceMemberRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    invited_by: UUID | None = None
    joined_at: datetime


class WorkspaceMemberCreate(BaseModel):
    user_id: UUID
    role: WorkspaceRole = WorkspaceRole.CREATOR


class WorkspaceMemberRoleUpdate(BaseModel):
    role: WorkspaceRole
