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
    BrandRuleCreate,
    BrandRuleRecord,
    BrandRuleUpdate,
    validate_brand_rule_configuration,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/brand-rules",
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
    response_model=list[BrandRuleRecord],
    summary="List brand rules",
)
async def list_brand_rules(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[BrandRuleRecord]:
    await require_workspace_member(workspace_id, auth, gateway)

    records = await gateway.request(
        "GET",
        "brand_rules",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )

    return [BrandRuleRecord.model_validate(record) for record in records]


@router.post(
    "",
    response_model=BrandRuleRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a brand rule",
)
async def create_brand_rule(
    workspace_id: UUID,
    data: BrandRuleCreate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> BrandRuleRecord:
    await require_workspace_owner(workspace_id, auth, gateway)

    records = await gateway.request(
        "POST",
        "brand_rules",
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
            detail="Brand rule creation returned no record.",
        )

    return BrandRuleRecord.model_validate(records[0])


@router.patch(
    "/{rule_id}",
    response_model=BrandRuleRecord,
    summary="Update a brand rule",
)
async def update_brand_rule(
    workspace_id: UUID,
    rule_id: UUID,
    data: BrandRuleUpdate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> BrandRuleRecord:
    await require_workspace_owner(workspace_id, auth, gateway)

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
        "brand_rules",
        params={
            "select": "rule_kind,check_type,check_value",
            "id": f"eq.{rule_id}",
            "workspace_id": f"eq.{workspace_id}",
            "limit": "1",
        },
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand rule not found.",
        )

    current = existing[0]

    try:
        validate_brand_rule_configuration(
            updates.get("rule_kind", current["rule_kind"]),
            updates.get("check_type", current["check_type"]),
            updates.get("check_value", current["check_value"]),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    records = await gateway.request(
        "PATCH",
        "brand_rules",
        params={
            "id": f"eq.{rule_id}",
            "workspace_id": f"eq.{workspace_id}",
        },
        payload=updates,
        prefer="return=representation",
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand rule not found.",
        )

    return BrandRuleRecord.model_validate(records[0])


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a brand rule",
)
async def delete_brand_rule(
    workspace_id: UUID,
    rule_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> Response:
    await require_workspace_owner(workspace_id, auth, gateway)

    records = await gateway.request(
        "DELETE",
        "brand_rules",
        params={
            "id": f"eq.{rule_id}",
            "workspace_id": f"eq.{workspace_id}",
        },
        prefer="return=representation",
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand rule not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
