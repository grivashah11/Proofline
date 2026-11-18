from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.governance_insights import build_governance_insights


def _row(*, fingerprint, content_id, source, category, outcome, status="open", title="Repeated issue", **extra):
    return {
        "fingerprint": fingerprint,
        "workspace_id": str(uuid4()),
        "content_id": str(content_id),
        "source": source,
        "category": category,
        "source_id": str(uuid4()) if source == "brand_rule" else None,
        "issue_title": title,
        "claim_subject": extra.get("claim_subject"),
        "claim_attribute": extra.get("claim_attribute"),
        "last_outcome": outcome,
        "status": status,
        "occurrence_count": extra.get("occurrence_count", 1),
        "reappeared_count": extra.get("reappeared_count", 0),
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }


def test_recurring_manual_review_rule_becomes_candidate_guideline_gap():
    rows = [
        _row(
            fingerprint="a" * 32,
            content_id=uuid4(),
            source="brand_rule",
            category="brand_voice",
            outcome="needs_review",
            title="Use a warm, direct brand voice",
        )
        for _ in range(3)
    ]

    response = build_governance_insights(
        workspace_id=uuid4(),
        records=rows,
        window_start=datetime.now(timezone.utc) - timedelta(days=90),
        window_days=90,
        min_distinct_submissions=3,
        limit=20,
    )

    assert len(response.recurring_issues) == 1
    assert response.recurring_issues[0].distinct_submissions == 3
    assert len(response.candidate_guideline_gaps) == 1
    assert response.candidate_guideline_gaps[0].requires_owner_confirmation is True
    assert "tone criteria" in response.candidate_guideline_gaps[0].suggested_clarification


def test_repeated_unverified_claim_becomes_evidence_gap_candidate():
    rows = [
        _row(
            fingerprint="b" * 32,
            content_id=uuid4(),
            source="ai_claim",
            category="claim",
            outcome="needs_verification",
            title="Claim needs verification",
            claim_subject="HydraLite Bottle",
            claim_attribute="Cold temperature retention",
        )
        for _ in range(3)
    ]

    response = build_governance_insights(
        workspace_id=uuid4(),
        records=rows,
        window_start=datetime.now(timezone.utc) - timedelta(days=90),
        window_days=90,
        min_distinct_submissions=3,
        limit=20,
    )

    assert len(response.evidence_gaps) == 1
    assert response.evidence_gaps[0].subject == "HydraLite Bottle"
    assert response.evidence_gaps[0].attribute == "Cold temperature retention"


def test_unverified_claim_tied_to_a_passport_can_be_an_evidence_gap_candidate():
    rows = [
        _row(
            fingerprint="d" * 32,
            content_id=uuid4(),
            source="claim_passport",
            category="claim",
            outcome="needs_verification",
            title="Claim needs verification",
            claim_subject="HydraLite Bottle",
            claim_attribute="Cold temperature retention",
        )
        for _ in range(3)
    ]

    response = build_governance_insights(
        workspace_id=uuid4(),
        records=rows,
        window_start=datetime.now(timezone.utc) - timedelta(days=90),
        window_days=90,
        min_distinct_submissions=3,
        limit=20,
    )

    assert len(response.evidence_gaps) == 1


def test_guideline_gap_is_not_suggested_below_distinct_submission_threshold():
    rows = [
        _row(
            fingerprint="c" * 32,
            content_id=uuid4(),
            source="brand_rule",
            category="messaging",
            outcome="needs_review",
        )
        for _ in range(2)
    ]

    response = build_governance_insights(
        workspace_id=uuid4(),
        records=rows,
        window_start=datetime.now(timezone.utc) - timedelta(days=90),
        window_days=90,
        min_distinct_submissions=3,
        limit=20,
    )

    assert response.candidate_guideline_gaps == []
