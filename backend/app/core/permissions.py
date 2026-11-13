from uuid import UUID

from fastapi import HTTPException, status

from app.core.auth import AuthContext
from app.core.supabase_gateway import SupabaseGateway
from app.schemas.workspaces import WorkspaceRole


async def get_workspace_role(
    workspace_id: UUID,
    auth: AuthContext,
    gateway: SupabaseGateway,
) -> WorkspaceRole:

    records = await gateway.request(
        "GET",
        "workspace_members",
        params={
            "select": "role",
            "workspace_id": f"eq.{workspace_id}",
            "user_id": f"eq.{auth.user.id}",
            "limit": "1",
        },
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or membership unavailable.",
        )

    return WorkspaceRole(records[0]["role"])


async def require_workspace_member(
    workspace_id: UUID,
    auth: AuthContext,
    gateway: SupabaseGateway,
) -> WorkspaceRole:
    return await get_workspace_role(
        workspace_id,
        auth,
        gateway,
    )


async def require_workspace_owner(
    workspace_id: UUID,
    auth: AuthContext,
    gateway: SupabaseGateway,
) -> None:

    role = await get_workspace_role(
        workspace_id,
        auth,
        gateway,
    )

    if role != WorkspaceRole.BRAND_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Brand Owner permission required.",
        )
