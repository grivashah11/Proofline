from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.main import app
from app.schemas.auth import AuthenticatedUser


class ReviewTestGateway:
    def __init__(self, user_id):
        self.user_id = user_id
        self.workspace_id = uuid4()
        self.content_id = uuid4()
        self.revision_id = uuid4()
        self.analysis_id = uuid4()

        self.role = "creator"
        self.membership_available = True
        self.analysis_available = True

        now = datetime.now(UTC).isoformat()

        self.content = {
            "id": str(self.content_id),
            "workspace_id": str(self.workspace_id),
            "title": "Judge campaign",
            "content_type": "social_post",
            "product_context": "Judge product",
            "channel": "Instagram",
            "market": "India",
            "status": "draft",
            "current_revision_id": str(self.revision_id),
            "submitted_analysis_run_id": None,
            "created_by": str(user_id),
            "created_at": now,
            "updated_at": now,
        }

        self.comments = []
        self.decisions = []
        self.audit_events = []

    @staticmethod
    def now():
        return datetime.now(UTC).isoformat()

    async def request(self, method, resource, *, params=None, **kwargs):
        params = params or {}

        if resource == "workspace_members":
            if not self.membership_available:
                return []
            return [{"role": self.role}]

        if resource == "contents":
            if params.get("workspace_id") != f"eq.{self.workspace_id}":
                return []

            requested_id = params.get("id")

            if requested_id and requested_id != f"eq.{self.content_id}":
                return []

            requested_status = params.get("status")

            if requested_status and requested_status != f"eq.{self.content['status']}":
                return []

            return [self.content]

        if resource == "content_comments":
            return [
                item
                for item in self.comments
                if item["workspace_id"] == str(self.workspace_id)
                and item["content_id"] == str(self.content_id)
                and item["revision_id"]
                == params.get("revision_id", "").removeprefix("eq.")
            ]

        if resource == "review_decisions":
            return [
                item
                for item in self.decisions
                if item["workspace_id"] == str(self.workspace_id)
                and item["content_id"] == str(self.content_id)
            ]

        if resource == "audit_events":
            return [
                item
                for item in self.audit_events
                if item["workspace_id"] == str(self.workspace_id)
                and item["content_id"] == str(self.content_id)
            ]

        raise AssertionError(f"Unexpected resource: {resource}")

    async def rpc(self, function_name, payload):
        now = self.now()

        if function_name == "submit_content_for_review":
            if not self.analysis_available:
                raise HTTPException(
                    status_code=409,
                    detail="Run analysis before submitting.",
                )

            if self.content["status"] != "draft":
                raise HTTPException(
                    status_code=409,
                    detail="Only draft content can be submitted.",
                )

            self.content["status"] = "in_review"
            self.content["submitted_analysis_run_id"] = str(self.analysis_id)
            self.content["updated_at"] = now

            self.audit_events.append(
                {
                    "id": str(uuid4()),
                    "workspace_id": str(self.workspace_id),
                    "content_id": str(self.content_id),
                    "revision_id": str(self.revision_id),
                    "event_type": "submitted_for_review",
                    "actor_id": str(self.user_id),
                    "details": {
                        "analysis_run_id": str(self.analysis_id),
                        "analysis_status": "completed",
                        "ai_extraction_status": "completed",
                    },
                    "created_at": now,
                }
            )

            return {
                "content": self.content,
                "analysis_run_id": str(self.analysis_id),
                "analysis_status": "completed",
            }

        if function_name == "add_content_comment":
            if payload["p_revision_id"] != str(self.revision_id):
                raise HTTPException(
                    status_code=404,
                    detail="Revision not found.",
                )

            comment = {
                "id": str(uuid4()),
                "workspace_id": str(self.workspace_id),
                "content_id": str(self.content_id),
                "revision_id": str(self.revision_id),
                "body": payload["p_body"],
                "created_by": str(self.user_id),
                "created_at": now,
            }

            self.comments.append(comment)

            self.audit_events.append(
                {
                    "id": str(uuid4()),
                    "workspace_id": str(self.workspace_id),
                    "content_id": str(self.content_id),
                    "revision_id": str(self.revision_id),
                    "event_type": "comment_added",
                    "actor_id": str(self.user_id),
                    "details": {"comment_id": comment["id"]},
                    "created_at": now,
                }
            )

            return comment

        if function_name == "record_content_review_decision":
            if self.role != "brand_owner":
                raise HTTPException(
                    status_code=403,
                    detail="Brand Owner permission required.",
                )

            if self.content["status"] != "in_review":
                raise HTTPException(
                    status_code=409,
                    detail="Content is not awaiting review.",
                )

            decision = payload["p_decision"]

            new_status = {
                "approved": "approved",
                "changes_requested": "changes_requested",
                "rejected": "rejected",
            }[decision]

            record = {
                "id": str(uuid4()),
                "workspace_id": str(self.workspace_id),
                "content_id": str(self.content_id),
                "revision_id": str(self.revision_id),
                "analysis_run_id": str(self.analysis_id),
                "decision": decision,
                "reviewer_comment": payload["p_reviewer_comment"],
                "reviewer_id": str(self.user_id),
                "created_at": now,
            }

            self.decisions.append(record)
            self.content["status"] = new_status
            self.content["updated_at"] = now

            self.audit_events.append(
                {
                    "id": str(uuid4()),
                    "workspace_id": str(self.workspace_id),
                    "content_id": str(self.content_id),
                    "revision_id": str(self.revision_id),
                    "event_type": "review_decision_recorded",
                    "actor_id": str(self.user_id),
                    "details": {
                        "review_decision_id": record["id"],
                        "decision": decision,
                        "analysis_run_id": str(self.analysis_id),
                    },
                    "created_at": now,
                }
            )

            return {
                "content": self.content,
                "decision": record,
            }

        raise AssertionError(f"Unexpected RPC: {function_name}")


@pytest.fixture
def review_client():
    user_id = uuid4()
    gateway = ReviewTestGateway(user_id)

    def override_auth():
        return AuthContext(
            user=AuthenticatedUser(
                id=user_id,
                email="review-test@example.com",
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


def content_url(gateway):
    return f"/api/v1/workspaces/{gateway.workspace_id}/contents/{gateway.content_id}"


def test_submit_for_review_requires_authentication():
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{uuid4()}/contents/{uuid4()}/submit-for-review"
        )

    assert response.status_code == 401


def test_creator_can_submit_analysed_revision(review_client):
    client, gateway = review_client

    response = client.post(f"{content_url(gateway)}/submit-for-review")

    assert response.status_code == 200
    assert response.json()["content"]["status"] == "in_review"
    assert response.json()["analysis_run_id"] == str(gateway.analysis_id)
    assert gateway.audit_events[0]["event_type"] == "submitted_for_review"


def test_submission_requires_analysis(review_client):
    client, gateway = review_client
    gateway.analysis_available = False

    response = client.post(f"{content_url(gateway)}/submit-for-review")

    assert response.status_code == 409
    assert gateway.content["status"] == "draft"


def test_creator_cannot_record_review_decision(review_client):
    client, gateway = review_client
    gateway.content["status"] = "in_review"
    gateway.content["submitted_analysis_run_id"] = str(gateway.analysis_id)

    response = client.post(
        f"{content_url(gateway)}/reviews",
        json={"decision": "approved"},
    )

    assert response.status_code == 403


def test_brand_owner_can_approve_submitted_revision(review_client):
    client, gateway = review_client
    gateway.role = "brand_owner"
    gateway.content["status"] = "in_review"
    gateway.content["submitted_analysis_run_id"] = str(gateway.analysis_id)

    response = client.post(
        f"{content_url(gateway)}/reviews",
        json={
            "decision": "approved",
            "reviewer_comment": "Content approved.",
        },
    )

    assert response.status_code == 201
    result = response.json()

    assert result["content"]["status"] == "approved"
    assert result["decision"]["decision"] == "approved"
    assert result["decision"]["revision_id"] == str(gateway.revision_id)
    assert result["decision"]["analysis_run_id"] == str(gateway.analysis_id)


@pytest.mark.parametrize(
    ("decision", "expected_status"),
    [
        ("changes_requested", "changes_requested"),
        ("rejected", "rejected"),
    ],
)
def test_brand_owner_can_return_or_reject(
    review_client,
    decision,
    expected_status,
):
    client, gateway = review_client
    gateway.role = "brand_owner"
    gateway.content["status"] = "in_review"
    gateway.content["submitted_analysis_run_id"] = str(gateway.analysis_id)

    response = client.post(
        f"{content_url(gateway)}/reviews",
        json={
            "decision": decision,
            "reviewer_comment": "Please address the findings.",
        },
    )

    assert response.status_code == 201
    assert response.json()["content"]["status"] == expected_status


def test_comments_are_saved_to_specific_revision(review_client):
    client, gateway = review_client

    response = client.post(
        f"{content_url(gateway)}/revisions/{gateway.revision_id}/comments",
        json={"body": "Please review the product claim."},
    )

    assert response.status_code == 201
    assert response.json()["revision_id"] == str(gateway.revision_id)
    assert response.json()["body"] == "Please review the product claim."


def test_review_queue_is_brand_owner_only(review_client):
    client, gateway = review_client

    response = client.get(f"/api/v1/workspaces/{gateway.workspace_id}/review-queue")

    assert response.status_code == 403

    gateway.role = "brand_owner"

    response = client.get(f"/api/v1/workspaces/{gateway.workspace_id}/review-queue")

    assert response.status_code == 200


def test_audit_history_contains_submission_and_comment(review_client):
    client, gateway = review_client

    client.post(f"{content_url(gateway)}/submit-for-review")

    client.post(
        f"{content_url(gateway)}/revisions/{gateway.revision_id}/comments",
        json={"body": "Review requested."},
    )

    response = client.get(f"{content_url(gateway)}/audit-events")

    assert response.status_code == 200

    event_types = [event["event_type"] for event in response.json()]

    assert "submitted_for_review" in event_types
    assert "comment_added" in event_types
