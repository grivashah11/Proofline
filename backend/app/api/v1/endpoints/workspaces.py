import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.core.supabase_gateway import SupabaseGateway
from app.schemas.workspaces import (
    WorkspaceCreate,
    WorkspaceListItem,
    WorkspaceMemberCreate,
    WorkspaceMemberRecord,
    WorkspaceMemberRoleUpdate,
    WorkspaceRecord,
    WorkspaceRole,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"],
)


AuthContextDependency = Annotated[
    AuthContext,
    Depends(get_auth_context),
]

SupabaseGatewayDependency = Annotated[
    SupabaseGateway,
    Depends(get_supabase_gateway),
]


async def require_workspace_owner(
    workspace_id: UUID,
    auth: AuthContext,
    gateway: SupabaseGateway,
) -> None:

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
            detail="Workspace membership not found.",
        )

    if records[0].get("role") != WorkspaceRole.BRAND_OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Brand Owner permission required.",
        )


@router.get(
    "",
    response_model=list[WorkspaceListItem],
    summary="List the current user's workspaces",
)
async def list_workspaces(
    auth: AuthContextDependency,
    gateway: SupabaseGatewayDependency,
) -> list[WorkspaceListItem]:

    records = await gateway.request(
        "GET",
        "workspace_members",
        params={
            "select": (
                "workspace_id,role,joined_at,"
                "workspace:workspaces!workspace_members_workspace_id_fkey("
                "id,name,slug,created_by,created_at,updated_at)"
            ),
            "user_id": f"eq.{auth.user.id}",
            "order": "joined_at.asc",
        },
    )

    result: list[WorkspaceListItem] = []

    for record in records:
        workspace_data = record.get("workspace")

        if not workspace_data:
            continue

        result.append(
            WorkspaceListItem(
                workspace=WorkspaceRecord.model_validate(workspace_data),
                role=record["role"],
                joined_at=record["joined_at"],
            )
        )

    return result


@router.post(
    "",
    response_model=WorkspaceRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace",
)
async def create_workspace(
    data: WorkspaceCreate,
    auth: AuthContextDependency,
    gateway: SupabaseGatewayDependency,
) -> WorkspaceRecord:

    # Do not request INSERT ... RETURNING here. The workspaces SELECT policy
    # only exposes a workspace to its members, while the AFTER INSERT trigger
    # creates the creator's Brand Owner membership. A separate SELECT after
    # the INSERT allows that trigger to complete before the row is read back.
    await gateway.request(
        "POST",
        "workspaces",
        payload={
            "name": data.name,
            "slug": data.slug,
            "created_by": str(auth.user.id),
        },
        prefer="return=minimal",
    )

    # The database trigger should now have added the creator as Brand Owner.
    # Read the row back using the same authenticated user's RLS-scoped token.
    records = await gateway.request(
        "GET",
        "workspaces",
        params={
            "select": "id,name,slug,created_by,created_at,updated_at",
            "slug": f"eq.{data.slug}",
            "created_by": f"eq.{auth.user.id}",
            "limit": "1",
        },
    )

    if not records:
        logger.error(
            "Workspace insert completed but the creator could not read the "
            "workspace afterwards; check the owner-membership trigger."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Workspace creation completed but could not be loaded. "
                "Please refresh and try again."
            ),
        )

    return WorkspaceRecord.model_validate(records[0])


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberRecord],
    summary="List workspace members",
)
async def list_workspace_members(
    workspace_id: UUID,
    gateway: SupabaseGatewayDependency,
) -> list[WorkspaceMemberRecord]:

    records = await gateway.request(
        "GET",
        "workspace_members",
        params={
            "select": ("workspace_id,user_id,role,invited_by,joined_at"),
            "workspace_id": f"eq.{workspace_id}",
            "order": "joined_at.asc",
        },
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or membership unavailable.",
        )

    return [WorkspaceMemberRecord.model_validate(record) for record in records]


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Add an existing registered user to a workspace",
)
async def add_workspace_member(
    workspace_id: UUID,
    data: WorkspaceMemberCreate,
    auth: AuthContextDependency,
    gateway: SupabaseGatewayDependency,
) -> WorkspaceMemberRecord:

    await require_workspace_owner(
        workspace_id,
        auth,
        gateway,
    )

    if data.user_id == auth.user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The current user is already a workspace member.",
        )

    records = await gateway.request(
        "POST",
        "workspace_members",
        payload={
            "workspace_id": str(workspace_id),
            "user_id": str(data.user_id),
            "role": data.role.value,
            "invited_by": str(auth.user.id),
        },
        prefer="return=representation",
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Member creation returned no record.",
        )

    return WorkspaceMemberRecord.model_validate(records[0])


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberRecord,
    summary="Change a workspace member's role",
)
async def update_workspace_member_role(
    workspace_id: UUID,
    user_id: UUID,
    data: WorkspaceMemberRoleUpdate,
    auth: AuthContextDependency,
    gateway: SupabaseGatewayDependency,
) -> WorkspaceMemberRecord:

    await require_workspace_owner(
        workspace_id,
        auth,
        gateway,
    )

    records = await gateway.request(
        "PATCH",
        "workspace_members",
        params={
            "workspace_id": f"eq.{workspace_id}",
            "user_id": f"eq.{user_id}",
        },
        payload={
            "role": data.role.value,
        },
        prefer="return=representation",
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace member not found.",
        )

    return WorkspaceMemberRecord.model_validate(records[0])


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a workspace member",
)
async def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    auth: AuthContextDependency,
    gateway: SupabaseGatewayDependency,
) -> Response:

    await require_workspace_owner(
        workspace_id,
        auth,
        gateway,
    )

    records = await gateway.request(
        "DELETE",
        "workspace_members",
        params={
            "workspace_id": f"eq.{workspace_id}",
            "user_id": f"eq.{user_id}",
        },
        prefer="return=representation",
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace member not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
