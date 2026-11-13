from typing import Annotated
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import (
    get_supabase_gateway,
    get_supabase_storage_gateway,
)
from app.core.permissions import (
    get_workspace_role,
    require_workspace_member,
    require_workspace_owner,
)
from app.core.supabase_gateway import SupabaseGateway
from app.core.supabase_storage import SupabaseStorageGateway
from app.schemas.images import (
    AltTextStatus,
    AssetMatchStatus,
    BrandAssetMatch,
    BrandAssetRecord,
    BrandAssetUpdate,
    ImageCheckAnalysis,
    ImageCheckRecord,
    ImageFinding,
    ImageFindingSeverity,
)
from app.schemas.workspaces import WorkspaceRole
from app.services.image_processing import process_image, read_upload

router = APIRouter(tags=["Image Assets and Checks"])

AuthDependency = Annotated[AuthContext, Depends(get_auth_context)]
GatewayDependency = Annotated[SupabaseGateway, Depends(get_supabase_gateway)]
StorageDependency = Annotated[
    SupabaseStorageGateway,
    Depends(get_supabase_storage_gateway),
]


def _inline_image_response(content: bytes, mime_type: str, filename: str) -> Response:
    safe_filename = filename.replace("\r", "").replace("\n", "")
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(safe_filename)}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def _get_asset_or_404(
    workspace_id: UUID,
    asset_id: UUID,
    gateway: SupabaseGateway,
) -> dict:
    records = await gateway.request(
        "GET",
        "brand_assets",
        params={
            "select": "*",
            "id": f"eq.{asset_id}",
            "workspace_id": f"eq.{workspace_id}",
            "limit": "1",
        },
    )
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approved brand asset not found.",
        )
    return records[0]


async def _get_image_check_or_404(
    workspace_id: UUID,
    image_check_id: UUID,
    gateway: SupabaseGateway,
) -> dict:
    records = await gateway.request(
        "GET",
        "image_checks",
        params={
            "select": "*",
            "id": f"eq.{image_check_id}",
            "workspace_id": f"eq.{workspace_id}",
            "limit": "1",
        },
    )
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image check not found.",
        )
    return records[0]


@router.get(
    "/workspaces/{workspace_id}/brand-assets",
    response_model=list[BrandAssetRecord],
    summary="List approved brand assets",
)
async def list_brand_assets(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[BrandAssetRecord]:
    await require_workspace_member(workspace_id, auth, gateway)
    records = await gateway.request(
        "GET",
        "brand_assets",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    return [BrandAssetRecord.model_validate(record) for record in records]


@router.post(
    "/workspaces/{workspace_id}/brand-assets",
    response_model=BrandAssetRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register an approved brand asset",
)
async def create_brand_asset(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    storage: StorageDependency,
    file: Annotated[UploadFile, File(description="JPEG, PNG, or WebP image")],
    asset_name: Annotated[str, Form(min_length=2, max_length=120)],
    description: Annotated[str | None, Form(max_length=2000)] = None,
) -> BrandAssetRecord:
    await require_workspace_owner(workspace_id, auth, gateway)

    normalized_name = asset_name.strip()
    if len(normalized_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Asset name must contain at least two non-space characters.",
        )

    content = await read_upload(file)
    metadata = process_image(content, file.filename)

    duplicates = await gateway.request(
        "GET",
        "brand_assets",
        params={
            "select": "id,asset_name,is_active",
            "workspace_id": f"eq.{workspace_id}",
            "sha256_hash": f"eq.{metadata['sha256_hash']}",
            "limit": "1",
        },
    )
    if duplicates:
        existing = duplicates[0]
        state = "active" if existing.get("is_active") else "archived"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This exact image is already registered as '{existing['asset_name']}' "
                f"({state}). Reuse or reactivate that record instead of uploading a duplicate."
            ),
        )

    asset_id = uuid4()
    storage_path = (
        f"{workspace_id}/brand-assets/{asset_id}{metadata['extension']}"
    )

    await storage.upload(storage_path, content, metadata["mime_type"])

    payload = {
        "id": str(asset_id),
        "workspace_id": str(workspace_id),
        "asset_name": normalized_name,
        "description": (description or "").strip() or None,
        "original_filename": metadata["original_filename"],
        "storage_path": storage_path,
        "mime_type": metadata["mime_type"],
        "file_size_bytes": metadata["file_size_bytes"],
        "sha256_hash": metadata["sha256_hash"],
        "image_format": metadata["image_format"],
        "width": metadata["width"],
        "height": metadata["height"],
        "dominant_colors": metadata["dominant_colors"],
        "is_active": True,
        "created_by": str(auth.user.id),
    }

    try:
        records = await gateway.request(
            "POST",
            "brand_assets",
            payload=payload,
            prefer="return=representation",
        )
    except Exception:
        await storage.remove(storage_path)
        raise

    if not records:
        await storage.remove(storage_path)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Brand asset registration returned no record.",
        )

    return BrandAssetRecord.model_validate(records[0])


@router.patch(
    "/workspaces/{workspace_id}/brand-assets/{asset_id}",
    response_model=BrandAssetRecord,
    summary="Update or reactivate an approved brand asset",
)
async def update_brand_asset(
    workspace_id: UUID,
    asset_id: UUID,
    data: BrandAssetUpdate,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> BrandAssetRecord:
    await require_workspace_owner(workspace_id, auth, gateway)
    await _get_asset_or_404(workspace_id, asset_id, gateway)
    updates = data.model_dump(mode="json", exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be supplied.",
        )

    if "asset_name" in updates and not updates["asset_name"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Asset name cannot be empty.",
        )
    if "is_active" in updates and updates["is_active"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="is_active must be true or false.",
        )

    records = await gateway.request(
        "PATCH",
        "brand_assets",
        params={
            "id": f"eq.{asset_id}",
            "workspace_id": f"eq.{workspace_id}",
        },
        payload=updates,
        prefer="return=representation",
    )
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approved brand asset not found.",
        )
    return BrandAssetRecord.model_validate(records[0])


@router.delete(
    "/workspaces/{workspace_id}/brand-assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive an approved brand asset",
)
async def archive_brand_asset(
    workspace_id: UUID,
    asset_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> Response:
    await require_workspace_owner(workspace_id, auth, gateway)
    await _get_asset_or_404(workspace_id, asset_id, gateway)
    await gateway.request(
        "PATCH",
        "brand_assets",
        params={
            "id": f"eq.{asset_id}",
            "workspace_id": f"eq.{workspace_id}",
        },
        payload={"is_active": False},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/workspaces/{workspace_id}/brand-assets/{asset_id}/file",
    summary="Download an approved brand asset",
    response_class=Response,
)
async def download_brand_asset(
    workspace_id: UUID,
    asset_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    storage: StorageDependency,
) -> Response:
    role = await get_workspace_role(workspace_id, auth, gateway)
    asset = await _get_asset_or_404(workspace_id, asset_id, gateway)
    if not asset.get("is_active") and role != WorkspaceRole.BRAND_OWNER:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approved brand asset not found.",
        )
    content = await storage.download(asset["storage_path"])
    return _inline_image_response(
        content,
        asset["mime_type"],
        asset["original_filename"],
    )


@router.get(
    "/workspaces/{workspace_id}/image-checks",
    response_model=list[ImageCheckRecord],
    summary="List workspace image checks",
)
async def list_image_checks(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ImageCheckRecord]:
    await require_workspace_member(workspace_id, auth, gateway)
    records = await gateway.request(
        "GET",
        "image_checks",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    return [ImageCheckRecord.model_validate(record) for record in records]


@router.post(
    "/workspaces/{workspace_id}/image-checks",
    response_model=ImageCheckRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Check a static image against approved brand assets",
)
async def create_image_check(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    storage: StorageDependency,
    file: Annotated[UploadFile, File(description="JPEG, PNG, or WebP image")],
    alt_text: Annotated[str | None, Form(max_length=1000)] = None,
) -> ImageCheckRecord:
    await require_workspace_member(workspace_id, auth, gateway)

    content = await read_upload(file)
    metadata = process_image(content, file.filename)
    normalized_alt_text = (alt_text or "").strip() or None

    approved_assets = await gateway.request(
        "GET",
        "brand_assets",
        params={
            "select": "id,asset_name,description,sha256_hash",
            "workspace_id": f"eq.{workspace_id}",
            "is_active": "eq.true",
            "order": "created_at.asc",
            "limit": "201",
        },
    )
    if len(approved_assets) > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The workspace has too many approved assets to check safely (maximum 200).",
        )

    match = next(
        (
            asset
            for asset in approved_assets
            if asset["sha256_hash"] == metadata["sha256_hash"]
        ),
        None,
    )

    findings: list[ImageFinding] = []
    if match:
        asset_match_status = AssetMatchStatus.EXACT_MATCH
        matched_asset = BrandAssetMatch(
            id=match["id"],
            asset_name=match["asset_name"],
            description=match.get("description"),
        )
        findings.append(
            ImageFinding(
                code="approved_asset_exact_match",
                severity=ImageFindingSeverity.INFO,
                title="Exact approved-asset match",
                message=(
                    f"The uploaded file is byte-for-byte identical to the approved asset "
                    f"'{match['asset_name']}'."
                ),
                recommended_action="Use the registered asset without modifying its file.",
            )
        )
    else:
        asset_match_status = AssetMatchStatus.NO_EXACT_MATCH
        matched_asset = None
        findings.append(
            ImageFinding(
                code="no_exact_approved_asset_match",
                severity=ImageFindingSeverity.WARNING,
                title="No exact approved-asset match",
                message=(
                    "No active approved brand asset has the same SHA-256 file hash. "
                    "This does not prove the image is unauthorised; it may be a modified "
                    "or newly supplied asset."
                ),
                recommended_action=(
                    "Ask the Brand Owner to review the image and register it if it is approved."
                ),
            )
        )

    if normalized_alt_text:
        alt_text_status = AltTextStatus.PROVIDED
        findings.append(
            ImageFinding(
                code="alt_text_provided_manual_review_required",
                severity=ImageFindingSeverity.INFO,
                title="Alt text supplied",
                message=(
                    "Alt text was supplied. This check does not assess whether the description "
                    "is accurate, useful, or appropriate for the image's context."
                ),
                recommended_action=(
                    "Have a reviewer confirm that the alt text communicates the image's purpose."
                ),
            )
        )
    else:
        alt_text_status = AltTextStatus.MISSING
        findings.append(
            ImageFinding(
                code="missing_alt_text",
                severity=ImageFindingSeverity.WARNING,
                title="Alt text is missing",
                message="No alternative text was supplied for this image.",
                recommended_action=(
                    "Add concise, context-appropriate alt text before publishing the image."
                ),
            )
        )

    analysis = ImageCheckAnalysis(
        asset_match_status=asset_match_status,
        matched_asset=matched_asset,
        dominant_colors=metadata["dominant_colors"],
        alt_text_status=alt_text_status,
        findings=findings,
        limitations=[
            (
                "Asset matching is exact SHA-256 matching only. Resized, recompressed, "
                "cropped, or visually similar images will not match."
            ),
            (
                "Dominant colors are descriptive metadata; this version does not score "
                "compliance with a brand color palette."
            ),
            (
                "Alt-text presence is checked, but semantic accuracy and accessibility "
                "quality require human review."
            ),
        ],
    )

    check_id = uuid4()
    storage_path = (
        f"{workspace_id}/image-checks/{auth.user.id}/"
        f"{check_id}{metadata['extension']}"
    )
    await storage.upload(storage_path, content, metadata["mime_type"])

    payload = {
        "id": str(check_id),
        "workspace_id": str(workspace_id),
        "storage_path": storage_path,
        "original_filename": metadata["original_filename"],
        "mime_type": metadata["mime_type"],
        "file_size_bytes": metadata["file_size_bytes"],
        "sha256_hash": metadata["sha256_hash"],
        "image_format": metadata["image_format"],
        "width": metadata["width"],
        "height": metadata["height"],
        "alt_text": normalized_alt_text,
        "matched_asset_id": str(match["id"]) if match else None,
        "analysis": analysis.model_dump(mode="json"),
        "created_by": str(auth.user.id),
    }

    try:
        records = await gateway.request(
            "POST",
            "image_checks",
            payload=payload,
            prefer="return=representation",
        )
    except Exception:
        await storage.remove(storage_path)
        raise

    if not records:
        await storage.remove(storage_path)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Image check could not be saved.",
        )

    return ImageCheckRecord.model_validate(records[0])


@router.get(
    "/workspaces/{workspace_id}/image-checks/{image_check_id}",
    response_model=ImageCheckRecord,
    summary="Get an image check",
)
async def get_image_check(
    workspace_id: UUID,
    image_check_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> ImageCheckRecord:
    await require_workspace_member(workspace_id, auth, gateway)
    record = await _get_image_check_or_404(workspace_id, image_check_id, gateway)
    return ImageCheckRecord.model_validate(record)


@router.get(
    "/workspaces/{workspace_id}/image-checks/{image_check_id}/file",
    summary="Download the image submitted for checking",
    response_class=Response,
)
async def download_checked_image(
    workspace_id: UUID,
    image_check_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    storage: StorageDependency,
) -> Response:
    await require_workspace_member(workspace_id, auth, gateway)
    record = await _get_image_check_or_404(workspace_id, image_check_id, gateway)
    content = await storage.download(record["storage_path"])
    return _inline_image_response(
        content,
        record["mime_type"],
        record["original_filename"],
    )
