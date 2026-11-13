from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.main import app
from app.schemas.auth import AuthenticatedUser


class InMemoryGateway:
    def __init__(self, user_id):
        self.user_id = user_id
        self.contents = []
        self.revisions = []

    @staticmethod
    def now():
        return datetime.now(UTC).isoformat()

    async def request(self, method, resource, *, params=None, **kwargs):
        params = params or {}

        if resource == "workspace_members":
            return [{"role": "brand_owner"}]

        workspace_id = params.get("workspace_id", "").removeprefix("eq.")
        content_id = params.get("content_id", "").removeprefix("eq.")
        record_id = params.get("id", "").removeprefix("eq.")

        if resource == "contents":
            records = [
                item
                for item in self.contents
                if str(item["workspace_id"]) == workspace_id
            ]

            if record_id:
                records = [item for item in records if str(item["id"]) == record_id]

            status_filter = params.get("status")
            if status_filter:
                expected = status_filter.removeprefix("eq.")
                records = [item for item in records if item["status"] == expected]

            return records

        if resource == "content_revisions":
            return [
                item
                for item in self.revisions
                if str(item["workspace_id"]) == workspace_id
                and str(item["content_id"]) == content_id
            ]

        raise AssertionError(f"Unexpected resource: {resource}")

    async def rpc(self, function_name, payload):
        now = self.now()

        if function_name == "create_content_with_revision":
            content_id = uuid4()
            revision_id = uuid4()

            content = {
                "id": str(content_id),
                "workspace_id": payload["p_workspace_id"],
                "title": payload["p_title"],
                "content_type": payload["p_content_type"],
                "product_context": payload["p_product_context"],
                "channel": payload["p_channel"],
                "market": payload["p_market"],
                "status": "draft",
                "current_revision_id": str(revision_id),
                "created_by": str(self.user_id),
                "created_at": now,
                "updated_at": now,
            }

            revision = {
                "id": str(revision_id),
                "workspace_id": payload["p_workspace_id"],
                "content_id": str(content_id),
                "revision_number": 1,
                "content_text": payload["p_content_text"],
                "created_by": str(self.user_id),
                "created_at": now,
            }

            self.contents.append(content)
            self.revisions.append(revision)

            return {"content": content, "revision": revision}

        if function_name == "create_content_revision":
            content = next(
                (
                    item
                    for item in self.contents
                    if item["id"] == payload["p_content_id"]
                    and item["workspace_id"] == payload["p_workspace_id"]
                ),
                None,
            )

            if content is None:
                raise AssertionError("Test content not found.")

            revision_id = uuid4()

            previous = [
                item
                for item in self.revisions
                if item["content_id"] == payload["p_content_id"]
            ]

            revision = {
                "id": str(revision_id),
                "workspace_id": payload["p_workspace_id"],
                "content_id": payload["p_content_id"],
                "revision_number": len(previous) + 1,
                "content_text": payload["p_content_text"],
                "created_by": str(self.user_id),
                "created_at": now,
            }

            self.revisions.append(revision)
            content["current_revision_id"] = str(revision_id)
            content["status"] = "draft"
            content["updated_at"] = now

            return {"content": content, "revision": revision}

        raise AssertionError(f"Unexpected RPC: {function_name}")


@pytest.fixture
def api_client():
    user_id = uuid4()
    gateway = InMemoryGateway(user_id)

    def override_auth():
        return AuthContext(
            user=AuthenticatedUser(
                id=user_id,
                email="proofline-test@example.com",
            ),
            access_token="test-token",
        )

    def override_gateway():
        return gateway

    previous_auth = app.dependency_overrides.get(get_auth_context)
    previous_gateway = app.dependency_overrides.get(get_supabase_gateway)

    app.dependency_overrides[get_auth_context] = override_auth
    app.dependency_overrides[get_supabase_gateway] = override_gateway

    try:
        with TestClient(app) as client:
            yield client, gateway
    finally:
        if previous_auth is None:
            app.dependency_overrides.pop(get_auth_context, None)
        else:
            app.dependency_overrides[get_auth_context] = previous_auth

        if previous_gateway is None:
            app.dependency_overrides.pop(get_supabase_gateway, None)
        else:
            app.dependency_overrides[get_supabase_gateway] = previous_gateway


def test_create_content_requires_authentication():
    workspace_id = uuid4()

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/contents",
            json={},
        )

    assert response.status_code == 401


def test_create_content_with_initial_revision(api_client):
    client, gateway = api_client
    workspace_id = uuid4()

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/contents",
        json={
            "title": "Summer campaign",
            "content_type": "social_post",
            "product_context": "HydraLite Bottle",
            "channel": "Instagram",
            "market": "India",
            "content_text": "Keep beverages cold for up to 24 hours.",
        },
    )

    assert response.status_code == 201
    result = response.json()

    assert result["content"]["title"] == "Summer campaign"
    assert result["content"]["product_context"] == "HydraLite Bottle"
    assert result["content"]["status"] == "draft"
    assert result["revision"]["revision_number"] == 1
    assert result["revision"]["content_text"] == (
        "Keep beverages cold for up to 24 hours."
    )
    assert len(gateway.contents) == 1
    assert len(gateway.revisions) == 1


def test_create_content_rejects_blank_text(api_client):
    client, _ = api_client
    workspace_id = uuid4()

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/contents",
        json={
            "title": "Invalid campaign",
            "content_type": "advertisement",
            "content_text": "   ",
        },
    )

    assert response.status_code == 422


def test_create_revision_preserves_previous_revision(api_client):
    client, gateway = api_client
    workspace_id = uuid4()

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/contents",
        json={
            "title": "Bottle campaign",
            "content_type": "social_post",
            "content_text": "Original campaign text.",
        },
    )

    content_id = created.json()["content"]["id"]

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/contents/{content_id}/revisions",
        json={"content_text": "Updated campaign text."},
    )

    assert response.status_code == 201
    result = response.json()

    assert result["revision"]["revision_number"] == 2
    assert result["revision"]["content_text"] == "Updated campaign text."
    assert len(gateway.revisions) == 2
    assert gateway.revisions[0]["content_text"] == "Original campaign text."
    assert result["content"]["status"] == "draft"


def test_get_content_returns_revision_history(api_client):
    client, _ = api_client
    workspace_id = uuid4()

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/contents",
        json={
            "title": "Email campaign",
            "content_type": "email",
            "content_text": "First version.",
        },
    )

    content_id = created.json()["content"]["id"]

    client.post(
        f"/api/v1/workspaces/{workspace_id}/contents/{content_id}/revisions",
        json={"content_text": "Second version."},
    )

    response = client.get(f"/api/v1/workspaces/{workspace_id}/contents/{content_id}")

    assert response.status_code == 200
    assert len(response.json()["revisions"]) == 2


def test_list_contents_returns_workspace_records(api_client):
    client, _ = api_client
    workspace_id = uuid4()

    client.post(
        f"/api/v1/workspaces/{workspace_id}/contents",
        json={
            "title": "Product advertisement",
            "content_type": "advertisement",
            "content_text": "Discover our new product.",
        },
    )

    response = client.get(f"/api/v1/workspaces/{workspace_id}/contents")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Product advertisement"
