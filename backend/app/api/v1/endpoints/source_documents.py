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
    require_workspace_member,
    require_workspace_owner,
)
from app.core.supabase_gateway import SupabaseGateway
from app.core.supabase_storage import (
    SOURCE_DOCUMENT_BUCKET,
    SupabaseStorageGateway,
)
from app.schemas.source_documents import (
    SourceDocumentRecord,
    SourceDocumentSegmentRecord,
)
from app.services.document_extraction import (
    MAX_SOURCE_DOCUMENT_BYTES,
    extract_source_document,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/source-documents",
    tags=["Source Documents"],
)

AuthDependency = Annotated[AuthContext, Depends(get_auth_context)]
GatewayDependency = Annotated[SupabaseGateway, Depends(get_supabase_gateway)]
StorageDependency = Annotated[
    SupabaseStorageGateway,
    Depends(get_supabase_storage_gateway),
]


def _download_response(content: bytes, mime_type: str, filename: str) -> Response:
    safe_filename = filename.replace("\r", "").replace("\n", "")
    encoded_filename = quote(safe_filename, safe="")
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def _get_source_document_or_404(
    workspace_id: UUID,
    document_id: UUID,
    gateway: SupabaseGateway,
) -> dict:
    records = await gateway.request(
        "GET",
        "source_documents",
        params={
            "select": "*",
            "id": f"eq.{document_id}",
            "workspace_id": f"eq.{workspace_id}",
            "limit": "1",
        },
    )
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source document not found.",
        )
    return records[0]


@router.get(
    "",
    response_model=list[SourceDocumentRecord],
    summary="List supporting source documents",
)
async def list_source_documents(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[SourceDocumentRecord]:
    await require_workspace_member(workspace_id, auth, gateway)
    records = await gateway.request(
        "GET",
        "source_documents",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    return [SourceDocumentRecord.model_validate(record) for record in records]


@router.post(
    "",
    response_model=SourceDocumentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and extract a supporting PDF or DOCX",
)
async def upload_source_document(
    workspace_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    storage: StorageDependency,
    file: Annotated[
        UploadFile,
        File(description="A text-readable PDF or DOCX document, up to 15 MB"),
    ],
    title: Annotated[str | None, Form(max_length=300)] = None,
) -> SourceDocumentRecord:
    await require_workspace_owner(workspace_id, auth, gateway)

    content = await file.read(MAX_SOURCE_DOCUMENT_BYTES + 1)
    await file.close()
    extracted = extract_source_document(
        content,
        file.filename,
        file.content_type,
    )

    normalized_title = (title or extracted.original_filename).strip()
    if not normalized_title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Document title cannot be empty.",
        )
    if len(normalized_title) > 300:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Document title cannot exceed 300 characters.",
        )

    duplicates = await gateway.request(
        "GET",
        "source_documents",
        params={
            "select": "id,title",
            "workspace_id": f"eq.{workspace_id}",
            "sha256_hash": f"eq.{extracted.sha256_hash}",
            "limit": "1",
        },
    )
    if duplicates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This exact document is already registered in this workspace as "
                f"'{duplicates[0]['title']}'. Reuse the existing source document."
            ),
        )

    document_id = uuid4()
    extension = ".pdf" if extracted.document_format == "PDF" else ".docx"
    storage_path = (
        f"{workspace_id}/source-documents/{document_id}/"
        f"{document_id}{extension}"
    )

    await storage.upload(
        storage_path,
        content,
        extracted.mime_type,
        bucket=SOURCE_DOCUMENT_BUCKET,
    )

    segments_payload = [
        {
            "id": str(uuid4()),
            "segment_index": segment.segment_index,
            "location_type": segment.location_type,
            "location_label": segment.location_label,
            "page_number": segment.page_number,
            "section_path": segment.section_path,
            "paragraph_number": segment.paragraph_number,
            "text_content": segment.text_content,
            "sha256_hash": segment.sha256_hash,
        }
        for segment in extracted.segments
    ]

    document_payload = {
        "id": str(document_id),
        "workspace_id": str(workspace_id),
        "title": normalized_title,
        "original_filename": extracted.original_filename,
        "storage_path": storage_path,
        "mime_type": extracted.mime_type,
        "document_format": extracted.document_format,
        "file_size_bytes": extracted.file_size_bytes,
        "sha256_hash": extracted.sha256_hash,
        "page_count": extracted.page_count,
        "segment_count": extracted.segment_count,
        "extraction_warnings": extracted.extraction_warnings,
    }

    try:
        record = await gateway.rpc(
            "register_source_document",
            {
                "p_document": document_payload,
                "p_segments": segments_payload,
            },
        )
    except Exception:
        await storage.remove(
            storage_path,
            bucket=SOURCE_DOCUMENT_BUCKET,
        )
        raise

    if not isinstance(record, dict):
        await storage.remove(
            storage_path,
            bucket=SOURCE_DOCUMENT_BUCKET,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Source document registration returned an invalid response.",
        )

    return SourceDocumentRecord.model_validate(record)


@router.get(
    "/{document_id}",
    response_model=SourceDocumentRecord,
    summary="Get source document details",
)
async def get_source_document(
    workspace_id: UUID,
    document_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
) -> SourceDocumentRecord:
    await require_workspace_member(workspace_id, auth, gateway)
    record = await _get_source_document_or_404(
        workspace_id,
        document_id,
        gateway,
    )
    return SourceDocumentRecord.model_validate(record)


@router.get(
    "/{document_id}/segments",
    response_model=list[SourceDocumentSegmentRecord],
    summary="Inspect extracted source passages and their locations",
)
async def list_source_document_segments(
    workspace_id: UUID,
    document_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
) -> list[SourceDocumentSegmentRecord]:
    await require_workspace_member(workspace_id, auth, gateway)
    await _get_source_document_or_404(workspace_id, document_id, gateway)

    records = await gateway.request(
        "GET",
        "source_document_segments",
        params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "source_document_id": f"eq.{document_id}",
            "order": "segment_index.asc",
            "limit": str(limit),
            "offset": str(offset),
        },
    )
    return [SourceDocumentSegmentRecord.model_validate(record) for record in records]


@router.get(
    "/{document_id}/file",
    response_class=Response,
    summary="Download the original supporting source document",
)
async def download_source_document(
    workspace_id: UUID,
    document_id: UUID,
    auth: AuthDependency,
    gateway: GatewayDependency,
    storage: StorageDependency,
) -> Response:
    await require_workspace_member(workspace_id, auth, gateway)
    record = await _get_source_document_or_404(
        workspace_id,
        document_id,
        gateway,
    )
    content = await storage.download(
        record["storage_path"],
        bucket=SOURCE_DOCUMENT_BUCKET,
    )
    return _download_response(
        content,
        record["mime_type"],
        record["original_filename"],
    )
