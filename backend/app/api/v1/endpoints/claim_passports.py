from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.core.permissions import (
    require_workspace_member,
    require_workspace_owner,
)
from app.core.supabase_gateway import SupabaseGateway
from app.schemas.claim_passports import (
    ClaimPassportCreate,
    ClaimPassportRecord,
    PassportVersionCreate,
    PassportVersionRecord,
)
from app.services.claim_matcher import INDIA_TIMEZONE
from app.schemas.source_documents import (
    ClaimPassportVersionSourceRecord,
    PassportReverificationReminder,
    ReverificationStatus,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/claim-passports",
    tags=["Claim Passports"],
)


AuthDependency = Annotated[
    AuthContext,
    Depends(get_auth_context),
]

GatewayDependency = Annotated[
    SupabaseGateway,
    Depends(get_supabase_gateway),
]


async def get_passport_or_404(
    workspace_id: UUID,
    passport_id: UUID,
    gateway: SupabaseGateway,
) -> dict:

    records = await gateway.request(
        "GET",
        "claim_passports",
        params={
            "select": "*",
            "id": f"eq.{passport_id}",
            "workspace_id": f"eq.{workspace_id}",
            "limit": "1",
        },
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim Passport not found.",
        )

    return records[0]


@router.get(
    "",
    response_model=list[ClaimPassportRecord],
    summary="List Claim Passports",
)
async def list_claim_passports(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ClaimPassportRecord]:

    await require_workspace_member(
        workspace_id,
        auth,
        gateway,
    )

    records = await gateway.request(
        "GET",
        "claim_passports",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )

    return [ClaimPassportRecord.model_validate(record) for record in records]


@router.post(
    "",
    response_model=ClaimPassportRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Claim Passport",
)
async def create_claim_passport(
    workspace_id: UUID,
    data: ClaimPassportCreate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> ClaimPassportRecord:

    await require_workspace_owner(
        workspace_id,
        auth,
        gateway,
    )

    records = await gateway.request(
        "POST",
        "claim_passports",
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
            detail="Claim Passport creation returned no record.",
        )

    return ClaimPassportRecord.model_validate(records[0])


@router.get(
    "/reverification-reminders",
    response_model=list[PassportReverificationReminder],
    summary="List active Claim Passports due for re-verification or expiry",
)
async def list_reverification_reminders(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    within_days: int = Query(default=30, ge=0, le=365),
) -> list[PassportReverificationReminder]:
    await require_workspace_owner(workspace_id, auth, gateway)

    today = datetime.now(INDIA_TIMEZONE).date()
    cutoff = today + timedelta(days=within_days)
    versions = await gateway.request(
        "GET",
        "claim_passport_versions",
        params={
            "select": "id,claim_passport_id,version_number,review_by,valid_until,status",
            "workspace_id": f"eq.{workspace_id}",
            "status": "eq.active",
            "or": (
                f"(review_by.lte.{cutoff.isoformat()}"
                f",valid_until.lte.{cutoff.isoformat()})"
            ),
            "order": "review_by.asc",
            "limit": "200",
        },
    )

    if not versions:
        return []

    passport_ids = sorted({str(item["claim_passport_id"]) for item in versions})
    passports = await gateway.request(
        "GET",
        "claim_passports",
        params={
            "select": "id,passport_code,subject",
            "workspace_id": f"eq.{workspace_id}",
            "id": f"in.({','.join(passport_ids)})",
        },
    )
    passport_by_id = {str(item["id"]): item for item in passports}

    reminders: list[PassportReverificationReminder] = []
    for version in versions:
        passport = passport_by_id.get(str(version["claim_passport_id"]))
        if passport is None:
            continue

        review_by = date.fromisoformat(version["review_by"]) if version.get("review_by") else None
        valid_until_value = version.get("valid_until")
        valid_until = date.fromisoformat(valid_until_value) if valid_until_value else None
        action_dates = [value for value in (review_by, valid_until) if value is not None]
        if not action_dates:
            continue

        action_date = min(action_dates)
        if valid_until is not None and valid_until < today:
            reminder_status = ReverificationStatus.EXPIRED
        elif review_by is not None and review_by < today:
            reminder_status = ReverificationStatus.OVERDUE
        else:
            reminder_status = ReverificationStatus.DUE_SOON

        reminders.append(
            PassportReverificationReminder(
                passport_id=passport["id"],
                passport_code=passport["passport_code"],
                subject=passport["subject"],
                version_id=version["id"],
                version_number=version["version_number"],
                review_by=review_by,
                valid_until=valid_until,
                status=reminder_status,
                days_until_action=(action_date - today).days,
            )
        )

    return sorted(reminders, key=lambda item: item.days_until_action)


@router.get(
    "/{passport_id}",
    response_model=ClaimPassportRecord,
    summary="Get a Claim Passport",
)
async def get_claim_passport(
    workspace_id: UUID,
    passport_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> ClaimPassportRecord:

    await require_workspace_member(
        workspace_id,
        auth,
        gateway,
    )

    record = await get_passport_or_404(
        workspace_id,
        passport_id,
        gateway,
    )

    return ClaimPassportRecord.model_validate(record)


@router.get(
    "/{passport_id}/versions",
    response_model=list[PassportVersionRecord],
    summary="List Claim Passport versions",
)
async def list_passport_versions(
    workspace_id: UUID,
    passport_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> list[PassportVersionRecord]:

    await require_workspace_member(
        workspace_id,
        auth,
        gateway,
    )

    await get_passport_or_404(
        workspace_id,
        passport_id,
        gateway,
    )

    records = await gateway.request(
        "GET",
        "claim_passport_versions",
        params={
            "select": "*",
            "claim_passport_id": f"eq.{passport_id}",
            "workspace_id": f"eq.{workspace_id}",
            "order": "version_number.desc",
        },
    )

    return [PassportVersionRecord.model_validate(record) for record in records]


@router.get(
    "/{passport_id}/versions/{version_id}/sources",
    response_model=list[ClaimPassportVersionSourceRecord],
    summary="List source-document excerpts linked to a Passport version",
)
async def list_passport_version_sources(
    workspace_id: UUID,
    passport_id: UUID,
    version_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> list[ClaimPassportVersionSourceRecord]:
    await require_workspace_member(workspace_id, auth, gateway)
    await get_passport_or_404(workspace_id, passport_id, gateway)

    versions = await gateway.request(
        "GET",
        "claim_passport_versions",
        params={
            "select": "id",
            "id": f"eq.{version_id}",
            "claim_passport_id": f"eq.{passport_id}",
            "workspace_id": f"eq.{workspace_id}",
            "limit": "1",
        },
    )
    if not versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim Passport version not found.",
        )

    records = await gateway.request(
        "GET",
        "claim_passport_version_sources",
        params={
            "select": "*",
            "claim_passport_id": f"eq.{passport_id}",
            "passport_version_id": f"eq.{version_id}",
            "workspace_id": f"eq.{workspace_id}",
            "order": "created_at.asc",
        },
    )
    return [ClaimPassportVersionSourceRecord.model_validate(record) for record in records]


@router.post(
    "/{passport_id}/versions",
    response_model=PassportVersionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new draft Passport version",
)
async def create_passport_version(
    workspace_id: UUID,
    passport_id: UUID,
    data: PassportVersionCreate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> PassportVersionRecord:

    await require_workspace_owner(
        workspace_id,
        auth,
        gateway,
    )

    passport = await get_passport_or_404(
        workspace_id,
        passport_id,
        gateway,
    )

    if passport["status"] == "retired":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot create a version for a retired Passport.",
        )

    if data.source_document_id is not None:
        result = await gateway.rpc(
            "create_claim_passport_version_from_source",
            {
                "p_claim_passport_id": str(passport_id),
                "p_source_document_id": str(data.source_document_id),
                "p_source_segment_id": str(data.source_document_segment_id),
                "p_source_excerpt": data.source_excerpt,
                "p_version_data": data.model_dump(
                    mode="json",
                    exclude={
                        "source_document_id",
                        "source_document_segment_id",
                        "source_excerpt",
                    },
                ),
            },
        )
        if not isinstance(result, dict) or not isinstance(result.get("version"), dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Document-backed Passport version creation returned an invalid response.",
            )
        return PassportVersionRecord.model_validate(result["version"])

    existing_versions = await gateway.request(
        "GET",
        "claim_passport_versions",
        params={
            "select": "version_number",
            "claim_passport_id": f"eq.{passport_id}",
            "workspace_id": f"eq.{workspace_id}",
            "order": "version_number.desc",
            "limit": "1",
        },
    )

    next_version = (
        existing_versions[0]["version_number"] + 1 if existing_versions else 1
    )

    payload = {
        "workspace_id": str(workspace_id),
        "claim_passport_id": str(passport_id),
        "version_number": next_version,
        **data.model_dump(mode="json"),
        "owner_id": str(auth.user.id),
        "created_by": str(auth.user.id),
    }

    records = await gateway.request(
        "POST",
        "claim_passport_versions",
        payload=payload,
        prefer="return=representation",
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Passport version creation returned no record.",
        )

    return PassportVersionRecord.model_validate(records[0])


@router.post(
    "/{passport_id}/versions/{version_id}/activate",
    response_model=ClaimPassportRecord,
    summary="Verify and activate a draft Passport version",
)
async def activate_passport_version(
    workspace_id: UUID,
    passport_id: UUID,
    version_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> ClaimPassportRecord:

    await require_workspace_owner(
        workspace_id,
        auth,
        gateway,
    )

    await get_passport_or_404(
        workspace_id,
        passport_id,
        gateway,
    )

    result = await gateway.rpc(
        "activate_claim_passport_version",
        {
            "p_claim_passport_id": str(passport_id),
            "p_version_id": str(version_id),
        },
    )

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Passport activation returned an invalid response.",
        )

    return ClaimPassportRecord.model_validate(result)
