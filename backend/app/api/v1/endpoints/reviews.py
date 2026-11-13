from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.core.permissions import (
    require_workspace_member,
    require_workspace_owner,
)
from app.core.supabase_gateway import SupabaseGateway
from app.schemas.contents import ContentRecord
from app.schemas.reviews import (
    AuditEventRecord,
    ContentCommentCreate,
    ContentCommentRecord,
    ReviewDecisionCreate,
    ReviewDecisionRecord,
    ReviewDecisionResult,
    ReviewSubmissionResult,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["Review and Approval"],
)

AuthDependency = Annotated[
    AuthContext,
    Depends(get_auth_context),
]

GatewayDependency = Annotated[
    SupabaseGateway,
    Depends(get_supabase_gateway),
]


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


@router.post(
    "/contents/{content_id}/submit-for-review",
    response_model=ReviewSubmissionResult,
    summary="Submit the current analysed revision for review",
)
async def submit_for_review(
    workspace_id: UUID,
    content_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> ReviewSubmissionResult:
    await require_workspace_member(workspace_id, auth, gateway)

    await get_content_or_404(
        workspace_id,
        content_id,
        gateway,
    )

    result = await gateway.rpc(
        "submit_content_for_review",
        {
            "p_workspace_id": str(workspace_id),
            "p_content_id": str(content_id),
        },
    )

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Review submission returned an invalid response.",
        )

    try:
        return ReviewSubmissionResult.model_validate(result)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Review submission returned invalid data.",
        ) from None


@router.get(
    "/review-queue",
    response_model=list[ContentRecord],
    summary="List content waiting for Brand Owner review",
)
async def get_review_queue(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ContentRecord]:
    await require_workspace_owner(workspace_id, auth, gateway)

    records = await gateway.request(
        "GET",
        "contents",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "status": "eq.in_review",
            "order": "updated_at.asc",
            "limit": str(limit),
        },
    )

    return [ContentRecord.model_validate(record) for record in records]


@router.post(
    "/contents/{content_id}/reviews",
    response_model=ReviewDecisionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Record a Brand Owner review decision",
)
async def record_review_decision(
    workspace_id: UUID,
    content_id: UUID,
    data: ReviewDecisionCreate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> ReviewDecisionResult:
    await require_workspace_owner(workspace_id, auth, gateway)

    await get_content_or_404(
        workspace_id,
        content_id,
        gateway,
    )

    result = await gateway.rpc(
        "record_content_review_decision",
        {
            "p_workspace_id": str(workspace_id),
            "p_content_id": str(content_id),
            "p_decision": data.decision.value,
            "p_reviewer_comment": data.reviewer_comment,
        },
    )

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Review decision returned an invalid response.",
        )

    try:
        return ReviewDecisionResult.model_validate(result)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Review decision returned invalid data.",
        ) from None


@router.get(
    "/contents/{content_id}/reviews",
    response_model=list[ReviewDecisionRecord],
    summary="List review decisions for a submission",
)
async def list_review_decisions(
    workspace_id: UUID,
    content_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> list[ReviewDecisionRecord]:
    await require_workspace_member(workspace_id, auth, gateway)

    await get_content_or_404(
        workspace_id,
        content_id,
        gateway,
    )

    records = await gateway.request(
        "GET",
        "review_decisions",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "content_id": f"eq.{content_id}",
            "order": "created_at.desc",
            "limit": "100",
        },
    )

    return [ReviewDecisionRecord.model_validate(record) for record in records]


@router.post(
    "/contents/{content_id}/revisions/{revision_id}/comments",
    response_model=ContentCommentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a specific revision",
)
async def add_content_comment(
    workspace_id: UUID,
    content_id: UUID,
    revision_id: UUID,
    data: ContentCommentCreate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> ContentCommentRecord:
    await require_workspace_member(workspace_id, auth, gateway)

    await get_content_or_404(
        workspace_id,
        content_id,
        gateway,
    )

    result = await gateway.rpc(
        "add_content_comment",
        {
            "p_workspace_id": str(workspace_id),
            "p_content_id": str(content_id),
            "p_revision_id": str(revision_id),
            "p_body": data.body,
        },
    )

    try:
        return ContentCommentRecord.model_validate(result)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Comment creation returned invalid data.",
        ) from None


@router.get(
    "/contents/{content_id}/revisions/{revision_id}/comments",
    response_model=list[ContentCommentRecord],
    summary="List comments for a specific revision",
)
async def list_content_comments(
    workspace_id: UUID,
    content_id: UUID,
    revision_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> list[ContentCommentRecord]:
    await require_workspace_member(workspace_id, auth, gateway)

    await get_content_or_404(
        workspace_id,
        content_id,
        gateway,
    )

    records = await gateway.request(
        "GET",
        "content_comments",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "content_id": f"eq.{content_id}",
            "revision_id": f"eq.{revision_id}",
            "order": "created_at.asc",
            "limit": "200",
        },
    )

    return [ContentCommentRecord.model_validate(record) for record in records]


@router.get(
    "/contents/{content_id}/audit-events",
    response_model=list[AuditEventRecord],
    summary="Retrieve the audit history for a content submission",
)
async def list_content_audit_events(
    workspace_id: UUID,
    content_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[AuditEventRecord]:
    await require_workspace_member(workspace_id, auth, gateway)

    await get_content_or_404(
        workspace_id,
        content_id,
        gateway,
    )

    records = await gateway.request(
        "GET",
        "audit_events",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "content_id": f"eq.{content_id}",
            "order": "created_at.asc",
            "limit": str(limit),
        },
    )

    return [AuditEventRecord.model_validate(record) for record in records]
