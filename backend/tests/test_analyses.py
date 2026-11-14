from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.endpoints import analyses as analysis_endpoint
from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.main import app
from app.schemas.auth import AuthenticatedUser
from app.schemas.claim_extraction import AIClaimExtraction, ExtractedClaim


class AnalysisTestGateway:
    def __init__(self, user_id):
        self.user_id = user_id
        self.workspace_id = uuid4()
        self.content_id = uuid4()
        self.revision_id = uuid4()
        self.analysis = None
        self.findings = []
        self.membership_available = True

        now = datetime.now(UTC).isoformat()

        self.content = {
            "id": str(self.content_id),
            "workspace_id": str(self.workspace_id),
            "title": "Test campaign",
            "content_type": "social_post",
            "product_context": "Test product",
            "channel": "social",
            "market": "India",
            "status": "draft",
            "current_revision_id": str(self.revision_id),
            "created_by": str(user_id),
            "created_at": now,
            "updated_at": now,
        }

        self.revision = {
            "id": str(self.revision_id),
            "workspace_id": str(self.workspace_id),
            "content_id": str(self.content_id),
            "revision_number": 1,
            "content_text": "Our test product keeps drinks cold for 24 hours.",
            "created_by": str(user_id),
            "created_at": now,
        }

    async def request(self, method, resource, *, params=None, **kwargs):
        params = params or {}

        if resource == "workspace_members":
            if not self.membership_available:
                return []
            return [{"role": "creator"}]

        if resource == "contents":
            if params.get("workspace_id") != f"eq.{self.workspace_id}":
                return []

            requested_id = params.get("id")
            if requested_id and requested_id != f"eq.{self.content['id']}":
                return []

            return [self.content]

        if resource == "content_revisions":
            if params.get("workspace_id") != f"eq.{self.workspace_id}":
                return []

            if params.get("content_id") != f"eq.{self.content['id']}":
                return []

            requested_id = params.get("id")
            if requested_id and requested_id != f"eq.{self.revision['id']}":
                return []

            return [self.revision]

        if resource in {
            "term_entries",
            "brand_rules",
            "claim_passports",
            "claim_passport_versions",
        }:
            return []

        if resource == "analysis_runs":
            if self.analysis is None:
                return []

            if params.get("workspace_id") != f"eq.{self.workspace_id}":
                return []

            if params.get("content_id") != f"eq.{self.content_id}":
                return []

            if params.get("revision_id") and params["revision_id"] != (
                f"eq.{self.analysis['revision_id']}"
            ):
                return []

            if params.get("model") and params["model"] != (
                f"eq.{self.analysis['model']}"
            ):
                return []

            if params.get("ai_extraction_status") and params["ai_extraction_status"] != (
                f"eq.{self.analysis['ai_extraction_status']}"
            ):
                return []

            requested_id = params.get("id")
            if requested_id and requested_id != f"eq.{self.analysis['id']}":
                return []

            return [self.analysis]

        if resource == "analysis_findings":
            if params.get("workspace_id") != f"eq.{self.workspace_id}":
                return []

            if self.analysis is None:
                return []

            if params.get("analysis_run_id") != f"eq.{self.analysis['id']}":
                return []

            return self.findings

        raise AssertionError(f"Unexpected resource: {resource}")

    async def rpc(self, function_name, payload):
        now = datetime.now(UTC).isoformat()

        if function_name == "add_manual_claim_to_analysis":
            if self.analysis is None or self.analysis["id"] != payload["p_analysis_id"]:
                raise HTTPException(status_code=404, detail="Analysis not found")
            if payload["p_revision_id"] != str(self.revision_id):
                raise HTTPException(status_code=409, detail="Revision is stale")

            candidate = payload["p_candidate_claim"]
            duplicate = any(
                finding.get("candidate_claim", {}).get("exact_text") == candidate["exact_text"]
                and finding.get("candidate_claim", {}).get("subject") == candidate["subject"]
                and finding.get("candidate_claim", {}).get("attribute") == candidate["attribute"]
                for finding in self.findings
                if isinstance(finding.get("candidate_claim"), dict)
            )
            if duplicate:
                raise HTTPException(status_code=409, detail="Claim already exists")

            finding = {
                "id": str(uuid4()),
                "workspace_id": str(self.workspace_id),
                "analysis_run_id": self.analysis["id"],
                "revision_id": str(self.revision_id),
                "finding_number": len(self.findings) + 1,
                "source": "ai_claim",
                "source_id": None,
                "category": "claim",
                "outcome": "needs_verification",
                "severity": "warning",
                "title": "Manually added claim needs verification",
                "message": "Manually added candidate claim requires human verification.",
                "recommended_action": "Ask the Brand Owner to verify the claim before approval.",
                "start_index": payload["p_start_index"],
                "end_index": payload["p_end_index"],
                "matched_text": candidate["exact_text"],
                "source_span_verified": True,
                "candidate_claim": candidate,
                "passport_id": None,
                "passport_version_id": None,
                "passport_version_number": None,
                "approved_wording": None,
                "evidence_source_title": None,
                "evidence_source_url": None,
                "evidence_reference": None,
                "evidence_excerpt": None,
                "created_at": now,
            }
            self.findings.append(finding)
            self.analysis["claim_needs_verification_count"] += 1
            return {"analysis": self.analysis, "findings": self.findings}

        assert function_name == "save_content_analysis"
        analysis_id = uuid4()

        self.analysis = {
            "id": str(analysis_id),
            "workspace_id": payload["p_workspace_id"],
            "content_id": payload["p_content_id"],
            "revision_id": payload["p_revision_id"],
            "run_number": 1,
            "model": payload["p_model"],
            "status": payload["p_analysis_status"],
            "ai_extraction_status": payload["p_ai_extraction_status"],
            "content_length": payload["p_content_length"],
            "channel": payload["p_channel"],
            "rule_checks_run": payload["p_rule_checks_run"],
            "rule_passed_checks": payload["p_rule_passed_checks"],
            "rule_conflict_count": payload["p_rule_conflict_count"],
            "rule_needs_review_count": payload["p_rule_needs_review_count"],
            "claim_supported_count": payload["p_claim_supported_count"],
            "claim_conflict_count": payload["p_claim_conflict_count"],
            "claim_review_due_count": payload["p_claim_review_due_count"],
            "claim_needs_verification_count": (
                payload["p_claim_needs_verification_count"]
            ),
            "human_approval_required": True,
            "created_by": str(self.user_id),
            "created_at": now,
        }

        self.findings = []

        for number, finding in enumerate(payload["p_findings"], start=1):
            self.findings.append(
                {
                    "id": str(uuid4()),
                    "workspace_id": payload["p_workspace_id"],
                    "analysis_run_id": str(analysis_id),
                    "revision_id": payload["p_revision_id"],
                    "finding_number": number,
                    **finding,
                    "created_at": now,
                }
            )

        return {
            "analysis": self.analysis,
            "findings": self.findings,
        }


@pytest.fixture
def analysis_client():
    user_id = uuid4()
    gateway = AnalysisTestGateway(user_id)

    def override_auth():
        return AuthContext(
            user=AuthenticatedUser(
                id=user_id,
                email="analysis-test@example.com",
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


def analysis_url(gateway):
    return (
        f"/api/v1/workspaces/{gateway.workspace_id}"
        f"/contents/{gateway.content_id}/analyses"
    )


def test_analysis_requires_authentication():
    workspace_id = uuid4()
    content_id = uuid4()

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/contents/{content_id}/analyses"
        )

    assert response.status_code == 401


def test_analysis_persists_completed_ai_result(
    analysis_client,
    monkeypatch,
):
    client, gateway = analysis_client

    async def fake_extract_claims(client, settings, content):
        return AIClaimExtraction(claims=[])

    monkeypatch.setattr(
        analysis_endpoint,
        "extract_claims",
        fake_extract_claims,
    )

    response = client.post(analysis_url(gateway))

    assert response.status_code == 201

    result = response.json()

    assert result["analysis"]["status"] == "completed"
    assert result["analysis"]["ai_extraction_status"] == "completed"
    assert result["analysis"]["run_number"] == 1
    assert result["analysis"]["human_approval_required"] is True
    assert result["findings"] == []


def test_analysis_persists_claim_needing_verification(
    analysis_client,
    monkeypatch,
):
    client, gateway = analysis_client

    async def fake_extract_claims(client, settings, content):
        return AIClaimExtraction(
            claims=[
                ExtractedClaim(
                    exact_text="Our test product keeps drinks cold for 24 hours.",
                    subject="Test product",
                    attribute="cold retention",
                    claim_kind="factual",
                    value_text="24",
                    numeric_value="24",
                    unit="hours",
                    extraction_note="Candidate claim extracted from the draft.",
                )
            ]
        )

    monkeypatch.setattr(
        analysis_endpoint,
        "extract_claims",
        fake_extract_claims,
    )

    response = client.post(analysis_url(gateway))

    assert response.status_code == 201

    result = response.json()

    assert result["analysis"]["claim_needs_verification_count"] == 1
    assert len(result["findings"]) == 1

    finding = result["findings"][0]

    assert finding["source"] == "ai_claim"
    assert finding["outcome"] == "needs_verification"
    assert finding["candidate_claim"]["subject"] == "Test product"
    assert finding["revision_id"] == str(gateway.revision_id)


def test_analysis_reuses_persisted_ai_extraction_for_same_revision(
    analysis_client,
    monkeypatch,
):
    client, gateway = analysis_client
    extraction_calls = 0

    async def fake_extract_claims(client, settings, content):
        nonlocal extraction_calls
        extraction_calls += 1
        return AIClaimExtraction(
            claims=[
                ExtractedClaim(
                    exact_text="Our test product keeps drinks cold for 24 hours.",
                    subject="Test product",
                    attribute="cold retention",
                    claim_kind="factual",
                    value_text="24",
                    numeric_value="24",
                    unit="hours",
                    extraction_note="Candidate claim extracted from the draft.",
                )
            ]
        )

    monkeypatch.setattr(
        analysis_endpoint,
        "extract_claims",
        fake_extract_claims,
    )

    first_response = client.post(analysis_url(gateway))
    second_response = client.post(analysis_url(gateway))

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert extraction_calls == 1
    assert first_response.json()["analysis"]["ai_extraction_status"] == "completed"
    assert second_response.json()["analysis"]["ai_extraction_status"] == "completed"
    assert second_response.json()["findings"][0]["candidate_claim"]["exact_text"] == (
        "Our test product keeps drinks cold for 24 hours."
    )


def test_analysis_cache_is_invalidated_for_a_new_revision(
    analysis_client,
    monkeypatch,
):
    client, gateway = analysis_client
    extraction_calls = 0

    async def fake_extract_claims(client, settings, content):
        nonlocal extraction_calls
        extraction_calls += 1
        return AIClaimExtraction(
            claims=[
                ExtractedClaim(
                    exact_text="Our test product keeps drinks cold for 24 hours.",
                    subject="Test product",
                    attribute="cold retention",
                    claim_kind="factual",
                    value_text="24",
                    numeric_value="24",
                    unit="hours",
                    extraction_note="Candidate claim extracted from the draft.",
                )
            ]
        )

    monkeypatch.setattr(
        analysis_endpoint,
        "extract_claims",
        fake_extract_claims,
    )

    first_response = client.post(analysis_url(gateway))
    assert first_response.status_code == 201
    assert extraction_calls == 1

    new_revision_id = uuid4()
    gateway.revision_id = new_revision_id
    gateway.content["current_revision_id"] = str(new_revision_id)
    gateway.revision = {
        **gateway.revision,
        "id": str(new_revision_id),
        "revision_number": 2,
    }

    second_response = client.post(analysis_url(gateway))

    assert second_response.status_code == 201
    assert extraction_calls == 2


def test_analysis_preserves_deterministic_findings_when_ai_fails(
    analysis_client,
    monkeypatch,
):
    client, gateway = analysis_client
    original_request = gateway.request

    async def request_with_brand_rule(method, resource, *, params=None, **kwargs):
        if resource == "brand_rules":
            return [
                {
                    "id": str(uuid4()),
                    "rule_kind": "brand_voice",
                    "title": "Brand voice requires human review",
                    "rule_text": "Use concise, factual wording.",
                    "tone_examples": None,
                    "channel": None,
                    "check_type": "manual_review",
                    "check_value": None,
                }
            ]
        return await original_request(method, resource, params=params, **kwargs)

    async def unavailable_ai(client, settings, content):
        raise HTTPException(status_code=502, detail="Synthetic incomplete AI response.")

    monkeypatch.setattr(gateway, "request", request_with_brand_rule)
    monkeypatch.setattr(
        analysis_endpoint,
        "extract_claims",
        unavailable_ai,
    )

    response = client.post(analysis_url(gateway))

    assert response.status_code == 201
    result = response.json()
    assert result["analysis"]["status"] == "partial"
    assert result["analysis"]["ai_extraction_status"] == "unavailable"
    assert any(
        finding["source"] == "brand_rule"
        and finding["title"] == "Brand voice requires human review"
        for finding in result["findings"]
    )


def test_analysis_retries_live_ai_when_persisted_cache_cannot_be_read(
    analysis_client,
    monkeypatch,
):
    client, gateway = analysis_client
    extraction_calls = 0
    original_request = gateway.request

    async def request_with_cache_read_failure(method, resource, *, params=None, **kwargs):
        if resource == "analysis_runs":
            raise HTTPException(status_code=503, detail="Synthetic cache read failure.")
        return await original_request(method, resource, params=params, **kwargs)

    async def fake_extract_claims(client, settings, content):
        nonlocal extraction_calls
        extraction_calls += 1
        return AIClaimExtraction(claims=[])

    monkeypatch.setattr(gateway, "request", request_with_cache_read_failure)
    monkeypatch.setattr(
        analysis_endpoint,
        "extract_claims",
        fake_extract_claims,
    )

    response = client.post(analysis_url(gateway))

    assert response.status_code == 201
    assert extraction_calls == 1
    assert response.json()["analysis"]["status"] == "completed"


@pytest.mark.parametrize(
    "failure_status",
    [422, 429, 502, 503],
)
def test_analysis_saves_partial_result_when_ai_returns_http_error(
    analysis_client,
    monkeypatch,
    failure_status,
):
    client, gateway = analysis_client

    async def unavailable_ai(client, settings, content):
        raise HTTPException(
            status_code=failure_status,
            detail="Provider failure details are intentionally not exposed.",
        )

    monkeypatch.setattr(
        analysis_endpoint,
        "extract_claims",
        unavailable_ai,
    )

    response = client.post(analysis_url(gateway))

    assert response.status_code == 201

    result = response.json()

    assert result["analysis"]["status"] == "partial"
    assert result["analysis"]["ai_extraction_status"] == "unavailable"
    assert result["analysis"]["human_approval_required"] is True


def test_analysis_saves_partial_result_when_ai_client_raises_unexpected_error(
    analysis_client,
    monkeypatch,
):
    client, gateway = analysis_client

    async def broken_ai(client, settings, content):
        raise RuntimeError("Synthetic provider client failure.")

    monkeypatch.setattr(
        analysis_endpoint,
        "extract_claims",
        broken_ai,
    )

    response = client.post(analysis_url(gateway))

    assert response.status_code == 201

    result = response.json()

    assert result["analysis"]["status"] == "partial"
    assert result["analysis"]["ai_extraction_status"] == "unavailable"
    assert result["analysis"]["human_approval_required"] is True


def test_analysis_rejects_missing_content(analysis_client):
    client, gateway = analysis_client
    gateway.content_id = uuid4()

    response = client.post(analysis_url(gateway))

    assert response.status_code == 404


def test_analysis_rejects_non_member(analysis_client):
    client, gateway = analysis_client
    gateway.membership_available = False

    response = client.post(analysis_url(gateway))

    assert response.status_code == 404


def test_manual_claim_adds_missed_excerpt_for_verification(analysis_client, monkeypatch):
    client, gateway = analysis_client

    async def fake_extract_claims(client, settings, content):
        return AIClaimExtraction(claims=[])

    monkeypatch.setattr(analysis_endpoint, "extract_claims", fake_extract_claims)
    created = client.post(analysis_url(gateway))
    assert created.status_code == 201
    analysis_id = created.json()["analysis"]["id"]

    response = client.post(
        f"{analysis_url(gateway)}/{analysis_id}/manual-claims",
        json={
            "exact_text": "Our test product keeps drinks cold for 24 hours.",
            "subject": "Test product",
            "attribute": "cold retention",
            "claim_kind": "factual",
            "numeric_value": "24",
            "unit": "hours",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["analysis"]["claim_needs_verification_count"] == 1
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["outcome"] == "needs_verification"
    assert finding["source_span_verified"] is True
    assert finding["candidate_claim"]["extraction_note"].startswith("Manually added")


def test_manual_claim_rejects_excerpt_not_in_current_revision(analysis_client, monkeypatch):
    client, gateway = analysis_client

    async def fake_extract_claims(client, settings, content):
        return AIClaimExtraction(claims=[])

    monkeypatch.setattr(analysis_endpoint, "extract_claims", fake_extract_claims)
    created = client.post(analysis_url(gateway))
    analysis_id = created.json()["analysis"]["id"]

    response = client.post(
        f"{analysis_url(gateway)}/{analysis_id}/manual-claims",
        json={
            "exact_text": "This sentence is not in the draft.",
            "subject": "Test product",
            "attribute": "cold retention",
            "claim_kind": "factual",
        },
    )

    assert response.status_code == 422
    assert "exactly match" in response.json()["detail"]


def test_retrieve_analysis_returns_saved_findings(
    analysis_client,
    monkeypatch,
):
    client, gateway = analysis_client

    async def fake_extract_claims(client, settings, content):
        return AIClaimExtraction(claims=[])

    monkeypatch.setattr(
        analysis_endpoint,
        "extract_claims",
        fake_extract_claims,
    )

    created = client.post(analysis_url(gateway))
    assert created.status_code == 201

    analysis_id = created.json()["analysis"]["id"]

    response = client.get(f"{analysis_url(gateway)}/{analysis_id}")

    assert response.status_code == 200
    assert response.json()["analysis"]["id"] == analysis_id
