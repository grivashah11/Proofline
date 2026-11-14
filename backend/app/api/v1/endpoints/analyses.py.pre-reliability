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
from app.schemas.analysis import (
    AIExtractionState,
    AnalysisDetail,
    AnalysisFindingOutcome,
    AnalysisRunRecord,
    AnalysisRunState,
)
from app.services.ai.openai_client import extract_claims
from app.services.analysis_service import build_analysis_findings
from app.schemas.manual_claims import ManualClaimCreate
from app.services.claim_matcher import locate_exact_excerpt, match_claims, normalize_text
from app.services.rule_engine import run_rule_engine

router = APIRouter(
    prefix="/workspaces/{workspace_id}/contents/{content_id}/analyses",
    tags=["Content Analysis"],
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


async def get_current_revision(
    workspace_id: UUID,
    content: dict,
    gateway: SupabaseGateway,
) -> dict:
    revision_id = content.get("current_revision_id")

    if not revision_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Content has no current revision.",
        )

    records = await gateway.request(
        "GET",
        "content_revisions",
        params={
            "select": "*",
            "id": f"eq.{revision_id}",
            "content_id": f"eq.{content['id']}",
            "workspace_id": f"eq.{workspace_id}",
            "limit": "1",
        },
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The current content revision could not be retrieved.",
        )

    return records[0]


def filter_passports_by_product(
    passports: list[dict],
    versions: list[dict],
    product_context: str | None,
) -> tuple[list[dict], list[dict]]:
    versions_by_id = {str(version["id"]): version for version in versions}

    selected_passports: list[dict] = []
    selected_versions: list[dict] = []

    product_name = normalize_text(product_context)

    for passport in passports:
        version_id = passport.get("current_version_id")
        version = versions_by_id.get(str(version_id))

        if version is None:
            continue

        product_scope = normalize_text(version.get("product_scope"))

        if product_scope and (not product_name or product_name != product_scope):
            continue

        selected_passports.append(passport)
        selected_versions.append(version)

    return selected_passports, selected_versions


async def load_analysis_knowledge(
    workspace_id: UUID,
    content: dict,
    gateway: SupabaseGateway,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
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
            "select": "id,rule_kind,title,rule_text,tone_examples,channel,check_type,check_value",
            "workspace_id": f"eq.{workspace_id}",
            "state": "eq.active",
            "order": "created_at.asc",
            "limit": "501",
        },
    )

    if len(terms) > 500 or len(rules) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The workspace has too many active rules or terminology entries.",
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
            detail="The workspace has too many active Claim Passports.",
        )

    version_ids = list(
        dict.fromkeys(
            str(passport["current_version_id"])
            for passport in passports
            if passport.get("current_version_id")
        )
    )

    versions: list[dict] = []

    if version_ids:
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
                "id": f"in.({','.join(version_ids)})",
                "status": "eq.active",
                "limit": "501",
            },
        )

    if len(versions) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Too many Passport versions for a single analysis.",
        )

    passports, versions = filter_passports_by_product(
        passports,
        versions,
        content.get("product_context"),
    )

    return terms, rules, passports, versions


@router.post(
    "",
    response_model=AnalysisDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Analyse the current content revision",
)
async def create_content_analysis(
    workspace_id: UUID,
    content_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    settings: SettingsDependency,
    ai_client: AIClientDependency,
) -> AnalysisDetail:
    await require_workspace_member(workspace_id, auth, gateway)

    content = await get_content_or_404(
        workspace_id,
        content_id,
        gateway,
    )

    if content.get("status") == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived content cannot be analysed.",
        )

    revision = await get_current_revision(
        workspace_id,
        content,
        gateway,
    )

    draft = revision["content_text"]

    terms, rules, passports, versions = await load_analysis_knowledge(
        workspace_id,
        content,
        gateway,
    )

    rule_result = run_rule_engine(
        workspace_id=workspace_id,
        content=draft,
        channel=content.get("channel"),
        terminology_entries=terms,
        brand_rules=rules,
    )

    ai_status = AIExtractionState.COMPLETED
    assessments = []

    try:
        extraction = await extract_claims(
            client=ai_client,
            settings=settings,
            content=draft,
        )

        assessments = match_claims(
            content=draft,
            claims=extraction.claims,
            passports=passports,
            versions=versions,
            channel=content.get("channel"),
            market=content.get("market"),
        )

    except HTTPException as exc:
        if exc.status_code != status.HTTP_503_SERVICE_UNAVAILABLE:
            raise

        ai_status = AIExtractionState.UNAVAILABLE

    claim_counts = {outcome: 0 for outcome in AnalysisFindingOutcome}

    for assessment in assessments:
        claim_counts[AnalysisFindingOutcome(assessment.status.value)] += 1

    findings = build_analysis_findings(
        rule_result,
        assessments,
    )

    analysis_status = (
        AnalysisRunState.PARTIAL
        if ai_status == AIExtractionState.UNAVAILABLE
        else AnalysisRunState.COMPLETED
    )

    result = await gateway.rpc(
        "save_content_analysis",
        {
            "p_workspace_id": str(workspace_id),
            "p_content_id": str(content_id),
            "p_revision_id": str(revision["id"]),
            "p_model": settings.openai_model,
            "p_analysis_status": analysis_status.value,
            "p_ai_extraction_status": ai_status.value,
            "p_content_length": len(draft),
            "p_channel": content.get("channel"),
            "p_rule_checks_run": rule_result.checks_run,
            "p_rule_passed_checks": rule_result.passed_checks,
            "p_rule_conflict_count": rule_result.conflict_count,
            "p_rule_needs_review_count": rule_result.needs_review_count,
            "p_claim_supported_count": claim_counts[AnalysisFindingOutcome.SUPPORTED],
            "p_claim_conflict_count": claim_counts[AnalysisFindingOutcome.CONFLICT],
            "p_claim_review_due_count": claim_counts[AnalysisFindingOutcome.REVIEW_DUE],
            "p_claim_needs_verification_count": claim_counts[
                AnalysisFindingOutcome.NEEDS_VERIFICATION
            ],
            "p_findings": findings,
        },
    )

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Analysis storage returned an invalid response.",
        )

    try:
        return AnalysisDetail.model_validate(result)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Analysis storage returned invalid analysis records.",
        ) from None


@router.post(
    "/{analysis_id}/manual-claims",
    response_model=AnalysisDetail,
    summary="Add a missed candidate claim to the current analysis",
)
async def add_manual_claim(
    workspace_id: UUID,
    content_id: UUID,
    analysis_id: UUID,
    data: ManualClaimCreate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> AnalysisDetail:
    """Add a verbatim claim omitted by AI extraction.

    A manually added claim is deliberately persisted as `needs_verification`.
    Supplying candidate fields does not independently validate the claim or
    authorise it for publication.
    """
    await require_workspace_member(workspace_id, auth, gateway)

    content = await get_content_or_404(workspace_id, content_id, gateway)
    if content.get("status") not in {"draft", "changes_requested"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Manual claims can only be added to editable drafts.",
        )

    revision = await get_current_revision(workspace_id, content, gateway)
    analysis_records = await gateway.request(
        "GET",
        "analysis_runs",
        params={
            "select": "id,workspace_id,content_id,revision_id",
            "id": f"eq.{analysis_id}",
            "workspace_id": f"eq.{workspace_id}",
            "content_id": f"eq.{content_id}",
            "limit": "1",
        },
    )
    if not analysis_records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis run not found.",
        )
    if str(analysis_records[0].get("revision_id")) != str(revision["id"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Manual claims can only be added to an analysis of the current revision. Run checks again.",
        )

    start_index, end_index, _ = locate_exact_excerpt(
        revision["content_text"],
        data.exact_text,
    )
    if start_index is None or end_index is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The claim excerpt must exactly match a contiguous part of the current draft.",
        )

    result = await gateway.rpc(
        "add_manual_claim_to_analysis",
        {
            "p_workspace_id": str(workspace_id),
            "p_content_id": str(content_id),
            "p_analysis_id": str(analysis_id),
            "p_revision_id": str(revision["id"]),
            "p_candidate_claim": data.to_candidate_claim(),
            "p_start_index": start_index,
            "p_end_index": end_index,
        },
    )

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Manual claim storage returned an invalid response.",
        )

    try:
        return AnalysisDetail.model_validate(result)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Manual claim storage returned invalid analysis records.",
        ) from None


@router.get(
    "",
    response_model=list[AnalysisRunRecord],
    summary="List analyses for a content submission",
)
async def list_content_analyses(
    workspace_id: UUID,
    content_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> list[AnalysisRunRecord]:
    await require_workspace_member(workspace_id, auth, gateway)

    await get_content_or_404(
        workspace_id,
        content_id,
        gateway,
    )

    records = await gateway.request(
        "GET",
        "analysis_runs",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "content_id": f"eq.{content_id}",
            "order": "created_at.desc",
            "limit": "100",
        },
    )

    return [AnalysisRunRecord.model_validate(record) for record in records]


@router.get(
    "/{analysis_id}",
    response_model=AnalysisDetail,
    summary="Retrieve an analysis and its findings",
)
async def get_content_analysis(
    workspace_id: UUID,
    content_id: UUID,
    analysis_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> AnalysisDetail:
    await require_workspace_member(workspace_id, auth, gateway)

    await get_content_or_404(
        workspace_id,
        content_id,
        gateway,
    )

    records = await gateway.request(
        "GET",
        "analysis_runs",
        params={
            "select": "*",
            "id": f"eq.{analysis_id}",
            "workspace_id": f"eq.{workspace_id}",
            "content_id": f"eq.{content_id}",
            "limit": "1",
        },
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis run not found.",
        )

    findings = await gateway.request(
        "GET",
        "analysis_findings",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "analysis_run_id": f"eq.{analysis_id}",
            "order": "finding_number.asc",
            "limit": "1500",
        },
    )

    return AnalysisDetail(
        analysis=AnalysisRunRecord.model_validate(records[0]),
        findings=findings,
    )
