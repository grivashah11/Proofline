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
