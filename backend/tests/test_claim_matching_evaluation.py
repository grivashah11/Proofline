import json
from datetime import date, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from app.schemas.claim_extraction import ExtractedClaim, PassportMatchStatus
from app.services.claim_matcher import match_claims

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "claim_matching_evaluation.json"
DATASET = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _uuid(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"proofline-claim-eval:{value}"))


def _date_with_offset(value: int | None) -> str | None:
    if value is None:
        return None
    return (date.today() + timedelta(days=value)).isoformat()


def _make_records(case: dict):
    passport_data = case["passport"]
    if passport_data is None:
        return [], []

    passports = []
    versions = []
    for index in range(case.get("passport_count", 1)):
        passport_id = _uuid(f"{case['id']}:passport:{index}")
        version_id = _uuid(f"{case['id']}:version:{index}")
        passport = {
            "id": passport_id,
            "passport_code": f"PFL-EVAL-{case['id']}-{index}",
            "subject": passport_data["subject"],
            "claim_type": passport_data["claim_type"],
            "status": passport_data["status"],
            "current_version_id": version_id,
        }
        version = {
            "id": version_id,
            "claim_passport_id": passport_id,
            "version_number": 1,
            "status": "active",
            "approved_wording": passport_data.get("permitted_value") or "Approved test wording",
            "subject": passport_data["subject"],
            "attribute": passport_data["attribute"],
            "permitted_value": passport_data.get("permitted_value"),
            "numeric_value": passport_data.get("numeric_value"),
            "unit": passport_data.get("unit"),
            "qualifier": passport_data.get("qualifier"),
            "required_conditions": passport_data.get("required_conditions"),
            "product_scope": passport_data.get("product_scope"),
            "channel_scope": passport_data.get("channel_scope"),
            "market_scope": passport_data.get("market_scope"),
            "review_by": _date_with_offset(passport_data.get("review_by_days", 30)),
            "valid_until": _date_with_offset(passport_data.get("valid_until_days")),
            "valid_from": _date_with_offset(passport_data.get("valid_from_days")),
            "evidence_source_title": "Synthetic evaluation evidence",
            "evidence_source_url": None,
            "evidence_reference": "Fixture section 1",
            "evidence_excerpt": "Synthetic data, not a real product claim.",
        }
        passports.append(passport)
        versions.append(version)
    return passports, versions


@pytest.mark.parametrize("case", DATASET, ids=[item["id"] for item in DATASET])
def test_labelled_claim_matching_dataset(case: dict):
    claim = ExtractedClaim.model_validate(case["claim"])
    passports, versions = _make_records(case)

    assessments = match_claims(
        content=case["draft"],
        claims=[claim],
        passports=passports,
        versions=versions,
        channel=case.get("channel"),
        market=case.get("market"),
    )

    assert len(assessments) == 1
    assessment = assessments[0]
    assert assessment.status == PassportMatchStatus(case["expected_status"]), case["description"]
    assert 0.0 <= assessment.confidence_score <= 1.0
    assert assessment.confidence_band.value in {"high", "moderate", "low"}
    assert assessment.confidence_factors
    assert assessment.normalized_claim is not None

    if not assessment.source_span_verified:
        assert assessment.confidence_score <= 0.49
        assert assessment.confidence_band.value != "high"

    if case["expected_status"] == "supported":
        assert assessment.confidence_score >= 0.85
        assert assessment.confidence_band.value == "high"

    if case["expected_status"] == "review_due":
        assert assessment.confidence_score <= 0.79
        assert assessment.confidence_band.value != "high"
