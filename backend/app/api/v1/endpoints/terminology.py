from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.core.permissions import (
    require_workspace_member,
    require_workspace_owner,
)
from app.core.supabase_gateway import SupabaseGateway
from app.schemas.brand_knowledge import (
    TermEntryCreate,
    TermEntryKind,
    TermEntryRecord,
    TermEntryUpdate,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/terminology",
    tags=["Brand Knowledge"],
)


AuthDependency = Annotated[
    AuthContext,
    Depends(get_auth_context),
]

GatewayDependency = Annotated[
    SupabaseGateway,
    Depends(get_supabase_gateway),
]


@router.get(
    "",
    response_model=list[TermEntryRecord],
    summary="List brand terminology",
)
async def list_terminology(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[TermEntryRecord]:

    await require_workspace_member(
        workspace_id,
        auth,
        gateway,
    )

    records = await gateway.request(
        "GET",
        "term_entries",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )

    return [TermEntryRecord.model_validate(record) for record in records]


@router.post(
    "",
    response_model=TermEntryRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a terminology entry",
)
async def create_terminology(
    workspace_id: UUID,
    data: TermEntryCreate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> TermEntryRecord:

    await require_workspace_owner(
        workspace_id,
        auth,
        gateway,
    )

    records = await gateway.request(
        "POST",
        "term_entries",
        payload={
            "workspace_id": str(workspace_id),
            **data.model_dump(mode="json"),
            "created_by": str(auth.user.id),
        },
        prefer="return=representation",
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Terminology creation returned no record.",
        )

    return TermEntryRecord.model_validate(records[0])


@router.patch(
    "/{term_id}",
    response_model=TermEntryRecord,
    summary="Update a terminology entry",
)
async def update_terminology(
    workspace_id: UUID,
    term_id: UUID,
    data: TermEntryUpdate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> TermEntryRecord:

    await require_workspace_owner(
        workspace_id,
        auth,
        gateway,
    )

    updates = data.model_dump(
        mode="json",
        exclude_unset=True,
    )

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be supplied.",
        )

    existing = await gateway.request(
        "GET",
        "term_entries",
        params={
            "select": "term_type,preferred_replacement",
            "id": f"eq.{term_id}",
            "workspace_id": f"eq.{workspace_id}",
            "limit": "1",
        },
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terminology entry not found.",
        )

    effective_type = updates.get(
        "term_type",
        existing[0]["term_type"],
    )

    effective_replacement = updates.get(
        "preferred_replacement",
        existing[0]["preferred_replacement"],
    )

    if effective_type == TermEntryKind.RESTRICTED.value and not effective_replacement:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=("Restricted terminology must have a suggested replacement."),
        )

    records = await gateway.request(
        "PATCH",
        "term_entries",
        params={
            "id": f"eq.{term_id}",
            "workspace_id": f"eq.{workspace_id}",
        },
        payload=updates,
        prefer="return=representation",
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terminology entry not found.",
        )

    return TermEntryRecord.model_validate(records[0])


@router.delete(
    "/{term_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a terminology entry",
)
async def delete_terminology(
    workspace_id: UUID,
    term_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> Response:

    await require_workspace_owner(
        workspace_id,
        auth,
        gateway,
    )

    records = await gateway.request(
        "DELETE",
        "term_entries",
        params={
            "id": f"eq.{term_id}",
            "workspace_id": f"eq.{workspace_id}",
        },
        prefer="return=representation",
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terminology entry not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
