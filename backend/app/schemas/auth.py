from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuthenticatedUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    email: str | None = None


class SupabaseAuthUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    email: str | None = None
