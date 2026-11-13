from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.core.permissions import require_workspace_member
from app.core.supabase_gateway import SupabaseGateway
from app.schemas.contents import (
    ContentCreate,
    ContentDetail,
    ContentRecord,
    ContentRevisionCreate,
    ContentRevisionRecord,
    ContentStatus,
    ContentWithRevision,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/contents",
    tags=["Content Submissions"],
)

AuthDependency = Annotated[
    AuthContext,
    Depends(get_auth_context),
]

GatewayDependency = Annotated[
    SupabaseGateway,
    Depends(get_supabase_gateway),
]


def parse_content_with_revision(result: object) -> ContentWithRevision:
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Content operation returned an invalid response.",
        )

    try:
        return ContentWithRevision.model_validate(result)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Content operation returned an invalid record.",
        ) from None


async def get_content_or_404(
    workspace_id: UUID,
    content_id: UUID,
    gateway: SupabaseGateway,
) -> dict:
    records = await gateway.request(
        "GET",
        "contents",
        params={
            "select": "*",
            "id": f"eq.{content_id}",
            "workspace_id": f"eq.{workspace_id}",
            "limit": "1",
        },
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content submission not found.",
        )

    return records[0]


@router.get(
    "",
    response_model=list[ContentRecord],
    summary="List workspace content submissions",
)
async def list_contents(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    content_status: Annotated[ContentStatus | None, Query(alias="status")] = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ContentRecord]:
    await require_workspace_member(workspace_id, auth, gateway)

    params = {
        "select": "*",
        "workspace_id": f"eq.{workspace_id}",
        "order": "updated_at.desc",
        "limit": str(limit),
    }

    if content_status is not None:
        params["status"] = f"eq.{content_status.value}"

    records = await gateway.request(
        "GET",
        "contents",
        params=params,
    )

    return [ContentRecord.model_validate(record) for record in records]


@router.post(
    "",
    response_model=ContentWithRevision,
    status_code=status.HTTP_201_CREATED,
    summary="Create a content submission with its first revision",
)
async def create_content(
    workspace_id: UUID,
    data: ContentCreate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> ContentWithRevision:
    await require_workspace_member(workspace_id, auth, gateway)

    result = await gateway.rpc(
        "create_content_with_revision",
        {
            "p_workspace_id": str(workspace_id),
            "p_title": data.title,
            "p_content_type": data.content_type.value,
            "p_product_context": data.product_context,
            "p_channel": data.channel,
            "p_market": data.market,
            "p_content_text": data.content_text,
        },
    )

    return parse_content_with_revision(result)


@router.get(
    "/{content_id}",
    response_model=ContentDetail,
    summary="Retrieve a submission and its revision history",
)
async def get_content(
    workspace_id: UUID,
    content_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> ContentDetail:
    await require_workspace_member(workspace_id, auth, gateway)

    content = await get_content_or_404(
        workspace_id,
        content_id,
        gateway,
    )

    revisions = await gateway.request(
        "GET",
        "content_revisions",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "content_id": f"eq.{content_id}",
            "order": "revision_number.desc",
            "limit": "200",
        },
    )

    return ContentDetail(
        content=ContentRecord.model_validate(content),
        revisions=[
            ContentRevisionRecord.model_validate(record) for record in revisions
        ],
    )


@router.get(
    "/{content_id}/revisions",
    response_model=list[ContentRevisionRecord],
    summary="List content revisions",
)
async def list_content_revisions(
    workspace_id: UUID,
    content_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> list[ContentRevisionRecord]:
    await require_workspace_member(workspace_id, auth, gateway)

    await get_content_or_404(
        workspace_id,
        content_id,
        gateway,
    )

    records = await gateway.request(
        "GET",
        "content_revisions",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "content_id": f"eq.{content_id}",
            "order": "revision_number.desc",
            "limit": "200",
        },
    )

    return [ContentRevisionRecord.model_validate(record) for record in records]


@router.post(
    "/{content_id}/revisions",
    response_model=ContentWithRevision,
    status_code=status.HTTP_201_CREATED,
    summary="Save a new immutable content revision",
)
async def create_content_revision(
    workspace_id: UUID,
    content_id: UUID,
    data: ContentRevisionCreate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> ContentWithRevision:
    await require_workspace_member(workspace_id, auth, gateway)

    result = await gateway.rpc(
        "create_content_revision",
        {
            "p_workspace_id": str(workspace_id),
            "p_content_id": str(content_id),
            "p_content_text": data.content_text,
        },
    )

    return parse_content_with_revision(result)
