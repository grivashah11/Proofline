from datetime import date, timedelta
from uuid import uuid4

from app.schemas.claim_extraction import ExtractedClaim, PassportMatchStatus
from app.schemas.claim_passports import ClaimKind
from app.services.claim_matcher import match_claims

WORKSPACE_ID = str(uuid4())


def make_claim(
    *,
    text="The HydraLite Bottle keeps beverages cold for up to 24 hours.",
    numeric_value="24",
    unit="hours",
    qualifier="up to",
    conditions=None,
    subject="HydraLite Bottle",
    attribute="Cold temperature retention",
    value_text="24 hours",
):
    return ExtractedClaim(
        exact_text=text,
        subject=subject,
        attribute=attribute,
        claim_kind="promotional",
        value_text=value_text,
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
    subject="HydraLite Bottle",
    attribute="Cold temperature retention",
    numeric_value="24",
    permitted_value="24 hours",
    product_scope="HydraLite Bottle",
):
    passport_id = str(uuid4())
    version_id = str(uuid4())

    passport = {
        "id": passport_id,
        "passport_code": "PFL-TEST-001",
        "subject": subject,
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
            f"{subject} keeps beverages cold for up to {numeric_value} hours."
        ),
        "subject": subject,
        "attribute": attribute,
        "permitted_value": permitted_value,
        "numeric_value": numeric_value,
        "unit": "hours",
        "qualifier": "up to",
        "required_conditions": required_conditions,
        "product_scope": product_scope,
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



def test_subject_matching_ignores_trailing_model_year_when_scope_agrees():
    content = (
        "For the 13-inch MacBook Air with the M4 chip (2025), "
        "video streaming battery life is up to 18 hours."
    )
    claim = make_claim(
        text=content,
        subject="13-inch MacBook Air with the M4 chip (2025)",
        attribute="video streaming battery life",
        numeric_value="18",
        value_text="18 hours",
        unit="hours",
        qualifier="up to",
    )
    passport, version = make_records(
        subject="13-inch MacBook Air with the M4 chip",
        attribute="video streaming battery life",
        numeric_value="18",
        permitted_value="18 hours",
        product_scope="13-inch MacBook Air with M4 chip (2025)",
    )
    version["unit"] = "hours"
    version["qualifier"] = "up to"

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.SUPPORTED
    assert assessment.passport_code == "PFL-TEST-001"


def test_subject_matching_does_not_ignore_conflicting_model_years():
    content = "The 13-inch MacBook Air with the M4 chip (2024) lasts up to 18 hours."
    claim = make_claim(
        text=content,
        subject="13-inch MacBook Air with the M4 chip (2024)",
        attribute="Battery life",
        numeric_value="18",
    )
    passport, version = make_records(
        subject="13-inch MacBook Air with the M4 chip",
        attribute="Battery life",
        numeric_value="18",
        product_scope="13-inch MacBook Air with M4 chip (2025)",
    )

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION
    assert assessment.passport_id is None


def test_all_channel_and_market_scopes_are_wildcards():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hours."
    claim = make_claim(text=content)
    passport, version = make_records(
        channel_scope="All",
        market_scope="All",
    )

    assessment = run_match(
        content,
        claim,
        passport,
        version,
        channel="Website",
        market="India",
    )

    assert assessment.status == PassportMatchStatus.SUPPORTED


def test_numeric_conflict_is_detected_when_value_text_has_one_number():
    content = "The 13-inch MacBook Air with the M4 chip offers up to 30 hours."
    claim = make_claim(
        text=content,
        subject="13-inch MacBook Air with the M4 chip",
        attribute="Battery life",
        numeric_value=None,
        value_text="up to 30 hours",
        unit="hours",
        qualifier="up to",
    )
    passport, version = make_records(
        subject="13-inch MacBook Air with the M4 chip",
        attribute="Battery life",
        numeric_value="18",
        permitted_value="18 hours",
    )
    version["unit"] = "hours"
    version["qualifier"] = "up to"

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.CONFLICT
    assert "30" in assessment.explanation


def test_required_conditions_match_across_punctuation_and_separators():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hours."
    claim = make_claim(
        text=content,
        conditions=(
            "Only under controlled laboratory test conditions; "
            "at an ambient temperature of 20 C."
        ),
    )
    passport, version = make_records(
        required_conditions=(
            "Only under controlled laboratory test conditions. "
            "At an ambient temperature of 20 C."
        ),
    )

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.SUPPORTED


def test_missing_one_required_condition_clause_needs_verification():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hours."
    claim = make_claim(
        text=content,
        conditions="Only under controlled laboratory test conditions.",
    )
    passport, version = make_records(
        required_conditions=(
            "Only under controlled laboratory test conditions. "
            "At an ambient temperature of 20 C."
        ),
    )

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION


def test_hour_and_hours_are_equivalent_units_without_conversion():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hour."
    claim = make_claim(text=content, unit="hour")
    passport, version = make_records()

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.SUPPORTED


def test_m4_30_hour_claim_conflicts_after_model_year_normalization():
    content = (
        "For the 13-inch MacBook Air with the M4 chip (2025), "
        "video streaming battery life is up to 30 hours."
    )
    claim = make_claim(
        text=content,
        subject="13-inch MacBook Air with the M4 chip (2025)",
        attribute="video streaming battery life",
        numeric_value="30",
        value_text="30 hours",
        unit="hours",
        qualifier="up to",
    )
    passport, version = make_records(
        subject="13-inch MacBook Air with the M4 chip",
        attribute="video streaming battery life",
        numeric_value="18",
        permitted_value="18 hours",
        product_scope="13-inch MacBook Air with M4 chip (2025)",
        channel_scope="Website",
        market_scope="India",
    )
    version["qualifier"] = "up to"

    assessment = run_match(
        content,
        claim,
        passport,
        version,
        channel="Website",
        market="India",
    )

    assert assessment.status == PassportMatchStatus.CONFLICT
    assert "30" in assessment.explanation
    assert assessment.passport_code == "PFL-TEST-001"



def test_factual_battery_spec_matches_factual_passport_even_in_promotional_draft():
    content = "The 13-inch MacBook Air with the M4 chip offers up to 18 hours."
    claim = make_claim(
        text=content,
        subject="13-inch MacBook Air with the M4 chip",
        attribute="Battery life",
        numeric_value="18",
        value_text="18 hours",
        unit="hours",
        qualifier="up to",
    )
    passport, version = make_records(
        subject="13-inch MacBook Air with the M4 chip",
        attribute="Battery life",
        numeric_value="18",
        permitted_value="18 hours",
    )
    passport["claim_type"] = "factual"
    claim = claim.model_copy(update={"claim_kind": ClaimKind.FACTUAL})

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.SUPPORTED


def test_mismatched_claim_kind_stays_needs_verification():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hours."
    claim = make_claim(text=content, numeric_value="24")
    passport, version = make_records()
    passport["claim_type"] = "factual"

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION
