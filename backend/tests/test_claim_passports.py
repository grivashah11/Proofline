from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.claim_passports import (
    ClaimKind,
    ClaimPassportCreate,
    PassportVersionCreate,
)


def test_claim_passport_creation():
    passport = ClaimPassportCreate(
        passport_code="PFL-TEST-001",
        subject="HydraLite Bottle",
        claim_type=ClaimKind.PROMOTIONAL,
        summary="Demonstration claim.",
    )

    assert passport.passport_code == "PFL-TEST-001"
    assert passport.subject == "HydraLite Bottle"


def test_claim_passport_rejects_lowercase_code():
    with pytest.raises(ValidationError):
        ClaimPassportCreate(
            passport_code="pfl-test-001",
            subject="HydraLite Bottle",
            claim_type=ClaimKind.PROMOTIONAL,
        )


def test_claim_passport_rejects_invalid_type():
    with pytest.raises(ValidationError):
        ClaimPassportCreate(
            passport_code="PFL-TEST-001",
            subject="HydraLite Bottle",
            claim_type="invalid",
        )


def test_claim_passport_trims_subject():
    passport = ClaimPassportCreate(
        passport_code="PFL-TEST-001",
        subject="  HydraLite Bottle  ",
        claim_type=ClaimKind.FACTUAL,
    )

    assert passport.subject == "HydraLite Bottle"


def test_passport_version_creation():
    version = PassportVersionCreate(
        approved_wording="Keeps beverages cold for up to 24 hours.",
        subject="HydraLite Bottle",
        attribute="Cold temperature retention",
        numeric_value=Decimal(24),
        unit="hours",
        evidence_source_title="Demo Test Report",
        evidence_excerpt="Synthetic demonstration evidence.",
        evidence_reference="Section 2.1",
        review_by=date.today() + timedelta(days=30),
    )

    assert version.numeric_value == Decimal(24)
    assert version.unit == "hours"


def test_numeric_claim_requires_unit():
    with pytest.raises(ValidationError):
        PassportVersionCreate(
            approved_wording="Keeps beverages cold for 24 hours.",
            subject="HydraLite Bottle",
            attribute="Cold temperature retention",
            numeric_value=Decimal(24),
        )


def test_version_validity_dates_are_checked():
    with pytest.raises(ValidationError):
        PassportVersionCreate(
            approved_wording="Approved wording.",
            subject="HydraLite Bottle",
            attribute="Temperature retention",
            valid_from=date.today(),
            valid_until=date.today() - timedelta(days=1),
        )


def test_passport_version_accepts_source_url():
    version = PassportVersionCreate(
        approved_wording="Demonstration claim.",
        subject="HydraLite Bottle",
        attribute="Temperature retention",
        evidence_source_title="Test Report",
        evidence_source_url="https://example.com/report",
    )

    assert str(version.evidence_source_url).startswith("https://")


def test_passport_version_rejects_invalid_source_url():
    with pytest.raises(ValidationError):
        PassportVersionCreate(
            approved_wording="Demonstration claim.",
            subject="HydraLite Bottle",
            attribute="Temperature retention",
            evidence_source_url="not-a-valid-url",
        )


def test_passport_routes_require_authentication():
    workspace_id = uuid4()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/workspaces/{workspace_id}/claim-passports")

    assert response.status_code == 401


def test_passport_creation_requires_authentication():
    workspace_id = uuid4()

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/claim-passports",
            json={
                "passport_code": "PFL-TEST-001",
                "subject": "HydraLite Bottle",
                "claim_type": "promotional",
            },
        )

    assert response.status_code == 401
