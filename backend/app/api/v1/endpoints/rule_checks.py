from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.core.permissions import require_workspace_member
from app.core.supabase_gateway import SupabaseGateway
from app.schemas.rule_engine import (
    RuleCheckRequest,
    RuleCheckResponse,
)
from app.services.rule_engine import run_rule_engine

router = APIRouter(
    prefix="/workspaces/{workspace_id}/rule-checks",
    tags=["Rule Engine"],
)


AuthDependency = Annotated[
    AuthContext,
    Depends(get_auth_context),
]

GatewayDependency = Annotated[
    SupabaseGateway,
    Depends(get_supabase_gateway),
]


@router.post(
    "",
    response_model=RuleCheckResponse,
    summary="Run deterministic brand checks on draft content",
)
async def check_content(
    workspace_id: UUID,
    data: RuleCheckRequest,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> RuleCheckResponse:

    await require_workspace_member(
        workspace_id,
        auth,
        gateway,
    )

    terms = await gateway.request(
        "GET",
        "term_entries",
        params={
            "select": (
                "id,term_type,term,preferred_replacement,"
                "case_sensitive,match_whole_word"
            ),
            "workspace_id": f"eq.{workspace_id}",
            "is_active": "eq.true",
            "order": "created_at.asc",
            "limit": "501",
        },
    )

    rules = await gateway.request(
        "GET",
        "brand_rules",
        params={
            "select": ("id,rule_kind,title,rule_text,tone_examples,channel,check_type,check_value"),
            "workspace_id": f"eq.{workspace_id}",
            "state": "eq.active",
            "order": "created_at.asc",
            "limit": "501",
        },
    )

    if len(terms) > 500 or len(rules) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "The workspace has more than 500 active rules or "
                "terminology entries. Reduce the active configuration."
            ),
        )

    return run_rule_engine(
        workspace_id=workspace_id,
        content=data.content,
        channel=data.channel,
        terminology_entries=terms,
        brand_rules=rules,
    )
