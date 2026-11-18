"""Run the deterministic labelled Claim Passport matching evaluation dataset."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.claim_extraction import ExtractedClaim  # noqa: E402
from app.services.claim_matcher import match_claims  # noqa: E402

DATASET_PATH = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "claim_matching_evaluation.json"
)


def stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"proofline-claim-eval:{value}"))


def offset_date(days: int | None) -> str | None:
    if days is None:
        return None
    return (date.today() + timedelta(days=days)).isoformat()


def build_records(case: dict) -> tuple[list[dict], list[dict]]:
    source = case.get("passport")
    if source is None:
        return [], []

    passports: list[dict] = []
    versions: list[dict] = []
    count = int(case.get("passport_count", 1))
    for index in range(count):
        passport_id = stable_id(f"{case['id']}:passport:{index}")
        version_id = stable_id(f"{case['id']}:version:{index}")
        passports.append(
            {
                "id": passport_id,
                "passport_code": f"PFL-EVAL-{case['id']}-{index}",
                "subject": source["subject"],
                "claim_type": source["claim_type"],
                "status": source["status"],
                "current_version_id": version_id,
            }
        )
        versions.append(
            {
                "id": version_id,
                "claim_passport_id": passport_id,
                "version_number": 1,
                "status": "active",
                "approved_wording": source.get("permitted_value") or "Synthetic approved wording",
                "subject": source["subject"],
                "attribute": source["attribute"],
                "permitted_value": source.get("permitted_value"),
                "numeric_value": source.get("numeric_value"),
                "unit": source.get("unit"),
                "qualifier": source.get("qualifier"),
                "required_conditions": source.get("required_conditions"),
                "product_scope": source.get("product_scope"),
                "channel_scope": source.get("channel_scope"),
                "market_scope": source.get("market_scope"),
                "review_by": offset_date(source.get("review_by_days", 30)),
                "valid_until": offset_date(source.get("valid_until_days")),
                "valid_from": offset_date(source.get("valid_from_days")),
                "evidence_source_title": "Synthetic evaluation fixture",
                "evidence_source_url": None,
                "evidence_reference": "Fixture only",
                "evidence_excerpt": "Synthetic data; not a real-world product claim.",
            }
        )
    return passports, versions


def main() -> int:
    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    failures: list[str] = []
    confidence_scores: list[float] = []

    for case in cases:
        claim = ExtractedClaim.model_validate(case["claim"])
        passports, versions = build_records(case)
        assessments = match_claims(
            content=case["draft"],
            claims=[claim],
            passports=passports,
            versions=versions,
            channel=case.get("channel"),
            market=case.get("market"),
        )
        actual = assessments[0].status.value
        expected = case["expected_status"]
        confusion[expected][actual] += 1
        confidence_scores.append(assessments[0].confidence_score)
        if expected != actual:
            failures.append(
                f"{case['id']}: expected {expected}, received {actual} — {case['description']}"
            )

    print(f"Evaluation cases: {len(cases)}")
    print(f"Exact outcome matches: {len(cases) - len(failures)}/{len(cases)}")
    print(f"Mean deterministic comparison confidence: {sum(confidence_scores) / max(1, len(confidence_scores)):.3f}")
    print("\nConfusion matrix (expected rows / actual columns):")
    statuses = sorted({key for row in confusion.values() for key in row} | set(confusion))
    print("expected\\actual | " + " | ".join(statuses))
    for expected in statuses:
        print(expected + " | " + " | ".join(str(confusion[expected][actual]) for actual in statuses))
    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("\nAll labelled outcomes matched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
