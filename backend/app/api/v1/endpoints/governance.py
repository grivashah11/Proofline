from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.core.permissions import require_workspace_member, require_workspace_owner
from app.core.supabase_gateway import SupabaseGateway
from app.schemas.governance import (
    FindingLifecycleEventRecord,
    FindingLifecycleRecord,
    GovernanceInsightsResponse,
)
from app.services.governance_insights import build_governance_insights

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["Governance Insights"],
)

AuthDependency = Annotated[AuthContext, Depends(get_auth_context)]
GatewayDependency = Annotated[SupabaseGateway, Depends(get_supabase_gateway)]


async def _require_content(workspace_id: UUID, content_id: UUID, gateway: SupabaseGateway) -> None:
    records = await gateway.request(
        "GET",
        "contents",
        params={
            "select": "id",
            "workspace_id": f"eq.{workspace_id}",
            "id": f"eq.{content_id}",
            "limit": "1",
        },
    )
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content submission not found.",
        )


@router.get(
    "/contents/{content_id}/finding-lifecycle",
    response_model=list[FindingLifecycleRecord],
    summary="Retrieve finding status and its cross-revision event history",
)
async def get_finding_lifecycle(
    workspace_id: UUID,
    content_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[FindingLifecycleRecord]:
    await require_workspace_member(workspace_id, auth, gateway)
    await _require_content(workspace_id, content_id, gateway)

    rows = await gateway.request(
        "GET",
        "finding_lifecycle",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "content_id": f"eq.{content_id}",
            "order": "last_seen_at.desc",
            "limit": str(limit),
        },
    )
    if not rows:
        return []

    lifecycle_ids = [str(row["id"]) for row in rows]
    events = await gateway.request(
        "GET",
        "finding_lifecycle_events",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "content_id": f"eq.{content_id}",
            "lifecycle_id": f"in.({','.join(lifecycle_ids)})",
            "order": "created_at.asc",
            "limit": "2000",
        },
    )
    events_by_lifecycle: dict[str, list[FindingLifecycleEventRecord]] = {}
    for event in events:
        item = FindingLifecycleEventRecord.model_validate(event)
        events_by_lifecycle.setdefault(str(item.lifecycle_id), []).append(item)

    return [
        FindingLifecycleRecord.model_validate(
            {**row, "events": events_by_lifecycle.get(str(row["id"]), [])}
        )
        for row in rows
    ]


@router.get(
    "/governance/insights",
    response_model=GovernanceInsightsResponse,
    summary="Summarize recurring governance issues and candidate guideline gaps",
)
async def get_governance_insights(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    window_days: int = Query(default=90, ge=7, le=365),
    min_distinct_submissions: int = Query(default=3, ge=2, le=20),
    limit: int = Query(default=50, ge=1, le=100),
) -> GovernanceInsightsResponse:
    await require_workspace_owner(workspace_id, auth, gateway)

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)
    rows = await gateway.request(
        "GET",
        "finding_lifecycle",
        params={
            "select": (
                "fingerprint,content_id,source,category,source_id,issue_title,"
                "claim_subject,claim_attribute,last_outcome,status,occurrence_count,reappeared_count,last_seen_at"
            ),
            "workspace_id": f"eq.{workspace_id}",
            "order": "last_seen_at.desc",
            "limit": "5001",
        },
    )
    if len(rows) > 5000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "This workspace has more than 5,000 finding lifecycle records. "
                "Narrow the reporting window before requesting governance insights."
            ),
        )

    return build_governance_insights(
        workspace_id=workspace_id,
        records=rows,
        window_start=window_start,
        window_days=window_days,
        min_distinct_submissions=min_distinct_submissions,
        limit=limit,
    )
