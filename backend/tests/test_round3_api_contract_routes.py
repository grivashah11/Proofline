from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.schemas.analysis import AnalysisFindingRecord


def test_round3_improvement_endpoints_are_registered():
    application = FastAPI()
    application.include_router(api_router, prefix="/api/v1")
    paths = application.openapi()["paths"]

    expected = {
        "/api/v1/workspaces/{workspace_id}/contents/{content_id}/revision-diff": {"get"},
        "/api/v1/workspaces/{workspace_id}/contents/{content_id}/finding-lifecycle": {"get"},
        "/api/v1/workspaces/{workspace_id}/governance/insights": {"get"},
        "/api/v1/workspaces/{workspace_id}/claim-extraction": {"post"},
        "/api/v1/workspaces/{workspace_id}/claim-passports/reverification-reminders": {"get"},
    }

    for path, methods in expected.items():
        assert path in paths
        assert methods.issubset(paths[path].keys())


def test_revision_diff_and_governance_routes_are_read_only():
    application = FastAPI()
    application.include_router(api_router, prefix="/api/v1")
    paths = application.openapi()["paths"]

    assert set(paths[
        "/api/v1/workspaces/{workspace_id}/contents/{content_id}/revision-diff"
    ]) == {"get"}
    assert set(paths[
        "/api/v1/workspaces/{workspace_id}/contents/{content_id}/finding-lifecycle"
    ]) == {"get"}
    assert set(paths[
        "/api/v1/workspaces/{workspace_id}/governance/insights"
    ]) == {"get"}


def test_historical_analysis_findings_can_have_null_new_metadata():
    now = datetime.now(UTC)
    finding = AnalysisFindingRecord.model_validate(
        {
            "id": uuid4(),
            "workspace_id": uuid4(),
            "analysis_run_id": uuid4(),
            "revision_id": uuid4(),
            "finding_number": 1,
            "source": "ai_claim",
            "category": "claim",
            "outcome": "needs_verification",
            "severity": "warning",
            "title": "Needs verification",
            "message": "No active Passport matched.",
            "recommended_action": "Ask the Brand Owner to verify.",
            "source_span_verified": True,
            "match_confidence": None,
            "match_confidence_band": None,
            "match_confidence_factors": None,
            "normalized_claim": None,
            "finding_fingerprint": None,
            "created_at": now,
        }
    )
    assert finding.match_confidence is None
    assert finding.match_confidence_factors is None
