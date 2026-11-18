from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from fastapi import HTTPException

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway, get_supabase_storage_gateway
from app.main import app
from app.schemas.auth import AuthenticatedUser
from app.core.supabase_storage import SOURCE_DOCUMENT_BUCKET


def make_pdf_bytes() -> bytes:
    output = BytesIO()
    document = canvas.Canvas(output, pagesize=letter)
    document.drawString(72, 720, "The product operates for up to 30 hours per charge.")
    document.save()
    return output.getvalue()


class SourceDocumentGateway:
    def __init__(self, user_id, role="brand_owner", fail_rpc=False):
        self.user_id = user_id
        self.role = role
        self.fail_rpc = fail_rpc
        self.workspace_id = uuid4()
        self.rpc_payload = None

    async def request(self, method, resource, *, params=None, payload=None, prefer=None):
        if resource == "workspace_members":
            return [{"role": self.role}]
        if resource == "source_documents":
            return []
        raise AssertionError(f"Unexpected database request: {resource}")

    async def rpc(self, function_name, payload):
        assert function_name == "register_source_document"
        self.rpc_payload = payload
        if self.fail_rpc:
            raise HTTPException(status_code=409, detail="Synthetic database conflict.")

        document = dict(payload["p_document"])
        document["uploaded_by"] = str(self.user_id)
        document["created_at"] = datetime.now(timezone.utc).isoformat()
        return document


class SourceDocumentStorage:
    def __init__(self):
        self.uploads = []
        self.removals = []

    async def upload(self, path, content, mime_type, *, bucket):
        self.uploads.append((path, content, mime_type, bucket))

    async def remove(self, path, *, bucket):
        self.removals.append((path, bucket))

    async def download(self, path, *, bucket):
        return b"downloaded source document"


@pytest.fixture
def source_document_client():
    user_id = uuid4()
    gateway = SourceDocumentGateway(user_id)
    storage = SourceDocumentStorage()

    def override_auth():
        return AuthContext(
            user=AuthenticatedUser(
                id=user_id,
                email="source-document-test@example.com",
            ),
            access_token="test-token",
        )

    previous = {
        get_auth_context: app.dependency_overrides.get(get_auth_context),
        get_supabase_gateway: app.dependency_overrides.get(get_supabase_gateway),
        get_supabase_storage_gateway: app.dependency_overrides.get(get_supabase_storage_gateway),
    }
    app.dependency_overrides[get_auth_context] = override_auth
    app.dependency_overrides[get_supabase_gateway] = lambda: gateway
    app.dependency_overrides[get_supabase_storage_gateway] = lambda: storage

    try:
        with TestClient(app) as client:
            yield client, gateway, storage
    finally:
        for dependency, old_override in previous.items():
            if old_override is None:
                app.dependency_overrides.pop(dependency, None)
            else:
                app.dependency_overrides[dependency] = old_override


def test_source_document_upload_uses_private_bucket_and_atomic_registration(source_document_client):
    client, gateway, storage = source_document_client
    response = client.post(
        f"/api/v1/workspaces/{gateway.workspace_id}/source-documents",
        files={"file": ("technical-report.pdf", make_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["document_format"] == "PDF"
    assert payload["page_count"] == 1
    assert payload["segment_count"] == 1
    assert storage.uploads[0][3] == SOURCE_DOCUMENT_BUCKET
    assert gateway.rpc_payload["p_segments"][0]["location_label"] == "Page 1"
    assert storage.removals == []


def test_creator_cannot_upload_source_documents(source_document_client):
    client, gateway, storage = source_document_client
    gateway.role = "creator"

    response = client.post(
        f"/api/v1/workspaces/{gateway.workspace_id}/source-documents",
        files={"file": ("technical-report.pdf", make_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 403
    assert storage.uploads == []


def test_source_document_upload_rolls_back_storage_when_database_registration_fails(
    source_document_client,
):
    client, gateway, storage = source_document_client
    gateway.fail_rpc = True

    response = client.post(
        f"/api/v1/workspaces/{gateway.workspace_id}/source-documents",
        files={"file": ("technical-report.pdf", make_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 409
    assert len(storage.uploads) == 1
    assert storage.removals == [(storage.uploads[0][0], SOURCE_DOCUMENT_BUCKET)]


def test_source_document_routes_require_authentication():
    workspace_id = uuid4()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/workspaces/{workspace_id}/source-documents")
    assert response.status_code == 401

class PassportSourceGateway:
    def __init__(self, user_id):
        self.user_id = user_id
        self.workspace_id = uuid4()
        self.passport_id = uuid4()
        self.rpc_payload = None

    async def request(self, method, resource, *, params=None, payload=None, prefer=None):
        if resource == "workspace_members":
            return [{"role": "brand_owner"}]
        if resource == "claim_passports":
            return [
                {
                    "id": str(self.passport_id),
                    "workspace_id": str(self.workspace_id),
                    "passport_code": "PFL-ROUND3-001",
                    "subject": "Proofline Sample Device",
                    "claim_type": "factual",
                    "summary": None,
                    "status": "draft",
                    "current_version_id": None,
                    "created_by": str(self.user_id),
                    "created_at": "2026-11-18T10:00:00Z",
                    "updated_at": "2026-11-18T10:00:00Z",
                }
            ]
        raise AssertionError(f"Unexpected database request: {resource}")

    async def rpc(self, function_name, payload):
        assert function_name == "create_claim_passport_version_from_source"
        self.rpc_payload = payload
        version = {
            "id": str(uuid4()),
            "workspace_id": str(self.workspace_id),
            "claim_passport_id": str(self.passport_id),
            "version_number": 1,
            "approved_wording": payload["p_version_data"]["approved_wording"],
            "subject": payload["p_version_data"]["subject"],
            "attribute": payload["p_version_data"]["attribute"],
            "permitted_value": None,
            "numeric_value": None,
            "unit": None,
            "qualifier": None,
            "required_conditions": None,
            "product_scope": None,
            "channel_scope": None,
            "market_scope": None,
            "valid_from": None,
            "valid_until": None,
            "evidence_source_title": "Technical Report",
            "evidence_source_url": None,
            "evidence_reference": "Page 1",
            "evidence_excerpt": payload["p_source_excerpt"],
            "evidence_source_version": "sha256:" + "a" * 64,
            "owner_id": str(self.user_id),
            "verified_by": None,
            "verified_at": None,
            "review_by": payload["p_version_data"]["review_by"],
            "status": "draft",
            "created_by": str(self.user_id),
            "created_at": "2026-11-18T10:00:00Z",
            "updated_at": "2026-11-18T10:00:00Z",
        }
        return {"version": version, "source": {}}


def test_create_passport_version_with_document_source_uses_atomic_rpc():
    from app.core.auth import get_auth_context
    from app.core.dependencies import get_supabase_gateway

    user_id = uuid4()
    gateway = PassportSourceGateway(user_id)

    def override_auth():
        return AuthContext(
            user=AuthenticatedUser(id=user_id, email="passport-source@example.com"),
            access_token="test-token",
        )

    previous_auth = app.dependency_overrides.get(get_auth_context)
    previous_gateway = app.dependency_overrides.get(get_supabase_gateway)
    app.dependency_overrides[get_auth_context] = override_auth
    app.dependency_overrides[get_supabase_gateway] = lambda: gateway

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/workspaces/{gateway.workspace_id}/claim-passports/"
                f"{gateway.passport_id}/versions",
                json={
                    "approved_wording": "Battery life is up to 30 hours.",
                    "subject": "Proofline Sample Device",
                    "attribute": "Battery life",
                    "review_by": "2026-12-18",
                    "source_document_id": str(uuid4()),
                    "source_document_segment_id": str(uuid4()),
                    "source_excerpt": "Battery life is up to 30 hours.",
                },
            )

        assert response.status_code == 201, response.text
        assert response.json()["evidence_source_title"] == "Technical Report"
        assert response.json()["evidence_reference"] == "Page 1"
        assert gateway.rpc_payload["p_source_excerpt"] == "Battery life is up to 30 hours."
        assert "source_document_id" not in gateway.rpc_payload["p_version_data"]
    finally:
        if previous_auth is None:
            app.dependency_overrides.pop(get_auth_context, None)
        else:
            app.dependency_overrides[get_auth_context] = previous_auth
        if previous_gateway is None:
            app.dependency_overrides.pop(get_supabase_gateway, None)
        else:
            app.dependency_overrides[get_supabase_gateway] = previous_gateway
