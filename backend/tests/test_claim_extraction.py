from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.auth import AuthContext, get_auth_context
from app.main import app
from app.schemas.auth import AuthenticatedUser


@pytest.fixture
def authenticated_client():
    """Provide a test-authenticated client without contacting Supabase."""

    previous_override = app.dependency_overrides.get(get_auth_context)

    def override_auth_context() -> AuthContext:
        return AuthContext(
            user=AuthenticatedUser(
                id=uuid4(),
                email="proofline-test@example.com",
            ),
            access_token="test-access-token",
        )

    app.dependency_overrides[get_auth_context] = override_auth_context

    try:
        with TestClient(app) as client:
            yield client
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_auth_context, None)
        else:
            app.dependency_overrides[get_auth_context] = previous_override


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
