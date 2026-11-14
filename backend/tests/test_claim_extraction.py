from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.core.http_client import get_ai_http_client
from app.main import app
from app.schemas.auth import AuthenticatedUser


@pytest.fixture
def authenticated_client():
    """Provide a test-authenticated client without contacting Supabase."""

    previous_auth_override = app.dependency_overrides.get(get_auth_context)
    previous_gateway_override = app.dependency_overrides.get(get_supabase_gateway)
    previous_ai_override = app.dependency_overrides.get(get_ai_http_client)

    def override_auth_context() -> AuthContext:
        return AuthContext(
            user=AuthenticatedUser(
                id=uuid4(),
                email="proofline-test@example.com",
            ),
            access_token="test-access-token",
        )

    app.dependency_overrides[get_auth_context] = override_auth_context
    # These invalid-request tests must reach Pydantic validation without
    # depending on local Supabase credentials or a live AI client.
    app.dependency_overrides[get_supabase_gateway] = lambda: object()
    app.dependency_overrides[get_ai_http_client] = lambda: object()

    try:
        with TestClient(app) as client:
            yield client
    finally:
        for dependency, previous in (
            (get_auth_context, previous_auth_override),
            (get_supabase_gateway, previous_gateway_override),
            (get_ai_http_client, previous_ai_override),
        ):
            if previous is None:
                app.dependency_overrides.pop(dependency, None)
            else:
                app.dependency_overrides[dependency] = previous


def test_claim_extraction_requires_authentication():
    workspace_id = uuid4()

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/claim-extraction",
            json={
                "content": "The product improves performance.",
                "channel": "social",
            },
        )

    assert response.status_code == 401


def test_claim_extraction_rejects_empty_content(
    authenticated_client: TestClient,
):
    workspace_id = uuid4()

    response = authenticated_client.post(
        f"/api/v1/workspaces/{workspace_id}/claim-extraction",
        json={
            "content": "   ",
            "channel": "social",
        },
    )

    assert response.status_code == 422


def test_claim_extraction_rejects_unknown_fields(
    authenticated_client: TestClient,
):
    workspace_id = uuid4()

    response = authenticated_client.post(
        f"/api/v1/workspaces/{workspace_id}/claim-extraction",
        json={
            "content": "The product improves performance.",
            "unknown_field": "invalid",
        },
    )

    assert response.status_code == 422
