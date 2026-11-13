from datetime import date, timedelta
from uuid import uuid4

from app.schemas.claim_extraction import ExtractedClaim, PassportMatchStatus
from app.services.claim_matcher import match_claims

WORKSPACE_ID = str(uuid4())


def make_claim(
    *,
    text="The HydraLite Bottle keeps beverages cold for up to 24 hours.",
    numeric_value="24",
    unit="hours",
    qualifier="up to",
    conditions=None,
):
    return ExtractedClaim(
        exact_text=text,
        subject="HydraLite Bottle",
        attribute="Cold temperature retention",
        claim_kind="promotional",
        value_text="24 hours",
        numeric_value=numeric_value,
        unit=unit,
        qualifier=qualifier,
        conditions=conditions,
        product_scope="HydraLite Bottle",
        channel_scope=None,
        market_scope=None,
        extraction_note="Candidate claim extracted from draft text.",
    )


def make_records(
    *,
    review_by=None,
    passport_status="active",
    channel_scope=None,
    market_scope=None,
    required_conditions=None,
    valid_until=None,
):
    passport_id = str(uuid4())
    version_id = str(uuid4())

    passport = {
        "id": passport_id,
        "passport_code": "PFL-TEST-001",
        "subject": "HydraLite Bottle",
        "claim_type": "promotional",
        "status": passport_status,
        "current_version_id": version_id,
    }

    version = {
        "id": version_id,
        "claim_passport_id": passport_id,
        "workspace_id": WORKSPACE_ID,
        "version_number": 1,
        "status": "active",
        "approved_wording": (
            "The HydraLite Bottle keeps beverages cold for up to 24 hours."
        ),
        "subject": "HydraLite Bottle",
        "attribute": "Cold temperature retention",
        "permitted_value": "24 hours",
        "numeric_value": "24",
        "unit": "hours",
        "qualifier": "up to",
        "required_conditions": required_conditions,
        "product_scope": "HydraLite Bottle",
        "channel_scope": channel_scope,
        "market_scope": market_scope,
        "valid_from": None,
        "valid_until": valid_until,
        "review_by": review_by or (date.today() + timedelta(days=30)),
        "evidence_source_title": "Demo Test Report",
        "evidence_source_url": None,
        "evidence_reference": "Section 2.1",
        "evidence_excerpt": (
            "Synthetic demonstration evidence. Not a real product claim."
        ),
    }

    return passport, version


def run_match(
    content,
    claim,
    passport,
    version,
    *,
    channel=None,
    market=None,
):
    return match_claims(
        content=content,
        claims=[claim],
        passports=[passport],
        versions=[version],
        channel=channel,
        market=market,
    )[0]


def test_matching_active_passport_is_supported():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hours."

    claim = make_claim()
    passport, version = make_records()

    assessment = run_match(
        content,
        claim,
        passport,
        version,
    )

    assert assessment.status == PassportMatchStatus.SUPPORTED
    assert assessment.source_span_verified is True
    assert assessment.passport_code == "PFL-TEST-001"


def test_numeric_mismatch_is_conflict():
    content = "The HydraLite Bottle keeps beverages cold for up to 48 hours."

    claim = make_claim(
        text=content,
        numeric_value="48",
    )

    passport, version = make_records()

    assessment = run_match(
        content,
        claim,
        passport,
        version,
    )

    assert assessment.status == PassportMatchStatus.CONFLICT


def test_missing_passport_needs_verification():
    content = "The HydraLite Bottle keeps beverages cold."

    claim = make_claim(
        text=content,
        numeric_value=None,
        unit=None,
        qualifier=None,
    )

    assessment = match_claims(
        content=content,
        claims=[claim],
        passports=[],
        versions=[],
        channel=None,
        market=None,
    )[0]

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION


def test_expired_review_date_is_review_due():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hours."

    claim = make_claim()

    passport, version = make_records(
        review_by=date.today() - timedelta(days=1),
    )

    assessment = run_match(
        content,
        claim,
        passport,
        version,
    )

    assert assessment.status == PassportMatchStatus.REVIEW_DUE


def test_unlocatable_ai_excerpt_needs_verification():
    content = "The product keeps beverages cold."

    claim = make_claim(
        text="This text does not exist in the draft.",
        numeric_value=None,
        unit=None,
        qualifier=None,
    )

    passport, version = make_records()

    assessment = run_match(
        content,
        claim,
        passport,
        version,
    )

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION
    assert assessment.source_span_verified is False
    assert assessment.start_index is None


def test_emoji_offsets_use_utf16_indices():
    content = "😀 The HydraLite Bottle keeps beverages cold for up to 24 hours."

    claim = make_claim()
    passport, version = make_records()

    assessment = run_match(
        content,
        claim,
        passport,
        version,
    )

    highlighted = content.encode("utf-16-le")[
        assessment.start_index * 2 : assessment.end_index * 2
    ].decode("utf-16-le")

    assert highlighted == claim.exact_text
    assert assessment.start_index == 3


def test_unit_mismatch_requires_verification():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 days."

    claim = make_claim(
        text=content,
        unit="days",
    )

    passport, version = make_records()

    assessment = run_match(
        content,
        claim,
        passport,
        version,
    )

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION


def test_wrong_channel_scope_requires_verification():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hours."

    claim = make_claim()
    passport, version = make_records(
        channel_scope="email",
    )

    assessment = run_match(
        content,
        claim,
        passport,
        version,
        channel="social",
    )

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION


def test_missing_required_conditions_requires_verification():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hours."

    claim = make_claim()

    passport, version = make_records(
        required_conditions=("Only under controlled laboratory test conditions."),
    )

    assessment = run_match(
        content,
        claim,
        passport,
        version,
    )

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION


def test_duplicate_matching_passports_are_ambiguous():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hours."

    claim = make_claim()

    passport_one, version_one = make_records()
    passport_two, version_two = make_records()

    assessment = match_claims(
        content=content,
        claims=[claim],
        passports=[passport_one, passport_two],
        versions=[version_one, version_two],
        channel=None,
        market=None,
    )[0]

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION
    assert assessment.passport_id is None
