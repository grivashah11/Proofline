from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AuthContext, get_auth_context
from app.core.config import Settings, get_settings
from app.core.dependencies import get_supabase_gateway
from app.core.http_client import get_ai_http_client
from app.core.permissions import require_workspace_member
from app.core.supabase_gateway import SupabaseGateway
from app.schemas.claim_extraction import (
    ClaimAssessment,
    ClaimExtractionRequest,
    ClaimExtractionResponse,
)
from app.services.ai.openai_client import extract_claims
from app.services.claim_matcher import match_claims

router = APIRouter(
    prefix="/workspaces/{workspace_id}/claim-extraction",
    tags=["AI Claim Extraction"],
)


AuthDependency = Annotated[
    AuthContext,
    Depends(get_auth_context),
]

GatewayDependency = Annotated[
    SupabaseGateway,
    Depends(get_supabase_gateway),
]

SettingsDependency = Annotated[
    Settings,
    Depends(get_settings),
]

AIClientDependency = Annotated[
    httpx.AsyncClient,
    Depends(get_ai_http_client),
]


@router.post(
    "",
    response_model=ClaimExtractionResponse,
    summary="Extract draft claims and match them against Claim Passports",
)
async def extract_and_match_claims(
    workspace_id: UUID,
    data: ClaimExtractionRequest,
    auth: AuthDependency,
    gateway: GatewayDependency,
    settings: SettingsDependency,
    ai_client: AIClientDependency,
) -> ClaimExtractionResponse:

    # Verify membership before sending any content to the AI provider.

    await require_workspace_member(
        workspace_id,
        auth,
        gateway,
    )

    # Extract candidate claims. The AI does not decide their validity.

    extraction = await extract_claims(
        client=ai_client,
        settings=settings,
        content=data.content,
    )

    passports = await gateway.request(
        "GET",
        "claim_passports",
        params={
            "select": ("id,passport_code,subject,claim_type,status,current_version_id"),
            "workspace_id": f"eq.{workspace_id}",
            "status": "in.(active,review_due)",
            "order": "created_at.asc",
            "limit": "501",
        },
    )

    if len(passports) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Workspace contains too many active Passports "
                "for a single review request."
            ),
        )

    current_version_ids = list(
        dict.fromkeys(
            str(passport["current_version_id"])
            for passport in passports
            if passport.get("current_version_id")
        )
    )

    versions = []

    if current_version_ids:
        versions = await gateway.request(
            "GET",
            "claim_passport_versions",
            params={
                "select": (
                    "id,claim_passport_id,version_number,status,"
                    "approved_wording,subject,attribute,"
                    "permitted_value,numeric_value,unit,"
                    "qualifier,required_conditions,"
                    "product_scope,channel_scope,market_scope,"
                    "valid_from,valid_until,review_by,"
                    "evidence_source_title,evidence_source_url,"
                    "evidence_reference,evidence_excerpt"
                ),
                "workspace_id": f"eq.{workspace_id}",
                "id": f"in.({','.join(current_version_ids)})",
                "status": "eq.active",
                "limit": "501",
            },
        )

    if len(versions) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Too many Passport versions for a single review request.",
        )

    assessments: list[ClaimAssessment] = match_claims(
        content=data.content,
        claims=extraction.claims,
        passports=passports,
        versions=versions,
        channel=data.channel,
        market=data.market,
    )

    counts = {
        "supported": 0,
        "conflict": 0,
        "review_due": 0,
        "needs_verification": 0,
    }

    for assessment in assessments:
        counts[assessment.status.value] += 1

    return ClaimExtractionResponse(
        workspace_id=workspace_id,
        model=settings.openai_model,
        extracted_claim_count=len(assessments),
        supported_count=counts["supported"],
        conflict_count=counts["conflict"],
        review_due_count=counts["review_due"],
        needs_verification_count=counts["needs_verification"],
        human_approval_required=True,
        assessments=assessments,
    )
