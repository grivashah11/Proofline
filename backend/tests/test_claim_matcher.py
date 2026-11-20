from datetime import date, timedelta
from uuid import uuid4

from app.schemas.claim_extraction import ExtractedClaim, PassportMatchStatus
from app.schemas.claim_passports import ClaimKind
from app.services.claim_matcher import match_claims

WORKSPACE_ID = str(uuid4())


def make_claim(
    *,
    text="The HydraLite Bottle keeps beverages cold for up to 24 hours.",
    product_scope="HydraLite Bottle",
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
        product_scope=product_scope,
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


def test_supported_time_unit_conversion_detects_numeric_conflict():
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

    assert assessment.status == PassportMatchStatus.CONFLICT


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
        product_scope="13-inch MacBook Air with M4 chip (2025)",
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
        product_scope="13-inch MacBook Air with M4 chip (2025)",
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


def test_normalized_claim_uses_canonical_units_and_retains_model_year():
    content = (
        "The 13-inch MacBook Air with the M4 chip (2025) offers up to 24 hr."
    )
    claim = make_claim(
        text=content,
        subject="13-inch MacBook Air with the M4 chip (2025)",
        attribute="Battery life",
        numeric_value="24",
        value_text="24 hr",
        unit="hr",
        qualifier="up to",
        product_scope="13-inch MacBook Air with M4 chip (2025)",
    )
    passport, version = make_records(
        subject="13-inch MacBook Air with the M4 chip",
        attribute="Battery life",
        numeric_value="24",
        product_scope="13-inch MacBook Air with M4 chip (2025)",
    )
    version["unit"] = "hours"
    version["qualifier"] = "up to"

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.SUPPORTED
    assert assessment.normalized_claim.unit == "second"
    assert assessment.normalized_claim.unit_dimension == "time"
    assert assessment.normalized_claim.numeric_value == "86400"
    assert assessment.normalized_claim.model_years == ["2025"]


def test_normalized_claim_extracts_single_numeric_value_from_value_text():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hours."
    claim = make_claim(
        text=content,
        numeric_value=None,
        value_text="up to 24 hours",
        unit="hours",
    )

    passport, version = make_records()
    version["unit"] = "hours"
    version["qualifier"] = "up to"

    assessment = run_match(content, claim, passport, version)

    assert assessment.normalized_claim.numeric_value == "86400"
    assert assessment.normalized_claim.unit == "second"


def test_missing_material_qualifier_caps_comparison_confidence():
    content = "The HydraLite Bottle keeps beverages cold for up to 24 hours."
    claim = make_claim(text=content, qualifier=None)
    passport, version = make_records()
    version["qualifier"] = "up to"

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION
    assert assessment.confidence_score <= 0.79
    qualifier_factor = next(
        factor for factor in assessment.confidence_factors
        if factor.name == "qualifier"
    )
    assert qualifier_factor.applicable is True
    assert qualifier_factor.matched is False


def test_wireless_playback_battery_attribute_alias_matches_passport():
    content = (
        "The Northstar Pulse Wireless Headphones deliver up to 30 hours "
        "of wireless audio playback on a full charge."
    )
    claim = make_claim(
        text=content,
        subject="Northstar Pulse Wireless Headphones",
        attribute="wireless playback battery life",
        product_scope="Northstar Pulse Wireless Headphones — Standard Model",
        numeric_value="30",
        unit="hours",
        qualifier="up to",
        value_text="30 hours",
    )
    passport, version = make_records(
        subject="Northstar Pulse Wireless Headphones",
        attribute="wireless audio playback battery life",
        numeric_value="30",
        permitted_value="up to 30 hours",
        product_scope="Northstar Pulse Wireless Headphones — Standard Model",
    )
    version["required_conditions"] = None

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.SUPPORTED
    assert assessment.passport_code == "PFL-TEST-001"
    assert assessment.confidence_score >= 0.85
    attribute_factor = next(
        factor for factor in assessment.confidence_factors
        if factor.name == "attribute"
    )
    assert attribute_factor.matched is True


def test_wireless_battery_alias_does_not_hide_numeric_conflict():
    content = (
        "The Northstar Pulse Wireless Headphones deliver up to 40 hours "
        "of wireless audio playback on a full charge."
    )
    claim = make_claim(
        text=content,
        subject="Northstar Pulse Wireless Headphones",
        attribute="wireless playback battery life",
        product_scope="Northstar Pulse Wireless Headphones — Standard Model",
        numeric_value="40",
        unit="hours",
        qualifier="up to",
        value_text="40 hours",
    )
    passport, version = make_records(
        subject="Northstar Pulse Wireless Headphones",
        attribute="wireless audio playback battery life",
        numeric_value="30",
        permitted_value="up to 30 hours",
        product_scope="Northstar Pulse Wireless Headphones — Standard Model",
    )
    version["required_conditions"] = None

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.CONFLICT
    assert assessment.passport_code == "PFL-TEST-001"


def test_wireless_battery_alias_does_not_match_standby_time():
    content = "The Northstar Pulse Wireless Headphones deliver up to 30 hours of standby time."
    claim = make_claim(
        text=content,
        subject="Northstar Pulse Wireless Headphones",
        attribute="standby time",
        product_scope="Northstar Pulse Wireless Headphones — Standard Model",
        numeric_value="30",
        unit="hours",
        qualifier="up to",
        value_text="30 hours",
    )
    passport, version = make_records(
        subject="Northstar Pulse Wireless Headphones",
        attribute="wireless audio playback battery life",
        numeric_value="30",
        permitted_value="up to 30 hours",
        product_scope="Northstar Pulse Wireless Headphones — Standard Model",
    )
    version["required_conditions"] = None

    assessment = run_match(content, claim, passport, version)

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION
    assert assessment.passport_code is None
    factors = {factor.name: factor for factor in assessment.confidence_factors}
    assert factors["subject"].matched is True
    assert factors["attribute"].matched is False
    assert factors["passport_unique"].matched is False


def _northstar_extracted_variant_case(*, hours="30", variant="Standard Model", conditions=None):
    base_subject = "Northstar Pulse Wireless Headphones"
    full_variant = f"{base_subject} — {variant}"
    content = (
        f"The {full_variant} deliver up to {hours} hours of continuous "
        "wireless audio playback on a full charge under the stated demo test conditions."
    )
    claim = make_claim(
        text=content,
        subject=full_variant,
        attribute="continuous wireless audio playback hours",
        product_scope="variant",
        numeric_value=hours,
        unit="hours",
        qualifier="up to",
        conditions=conditions,
        value_text=f"{hours} hours",
    )
    passport, version = make_records(
        subject=base_subject,
        attribute="wireless audio playback battery life",
        numeric_value="30",
        permitted_value="up to 30 hours",
        product_scope=f"{base_subject} — Standard Model",
        channel_scope="Website",
        market_scope="India",
    )
    version["required_conditions"] = None
    return content, claim, passport, version


def test_actual_extracted_variant_subject_and_duration_attribute_match_passport():
    """Reproduce the exact subject/attribute wording seen in the live UI test."""
    content, claim, passport, version = _northstar_extracted_variant_case()

    assessment = run_match(
        content,
        claim,
        passport,
        version,
        channel="Website",
        market="India",
    )

    assert assessment.status == PassportMatchStatus.SUPPORTED
    assert assessment.passport_code == "PFL-TEST-001"
    assert assessment.confidence_score >= 0.85
    assert next(
        factor for factor in assessment.confidence_factors
        if factor.name == "subject"
    ).matched is True
    assert next(
        factor for factor in assessment.confidence_factors
        if factor.name == "attribute"
    ).matched is True
    assert next(
        factor for factor in assessment.confidence_factors
        if factor.name == "scope"
    ).matched is True


def test_observed_continuous_playback_hours_phrase_matches_with_full_conditions():
    base_subject = "Northstar Pulse Wireless Headphones"
    full_variant = f"{base_subject} — Standard Model"
    content = (
        f"The {full_variant} deliver up to 30 hours of continuous "
        "wireless audio playback on a full charge. "
        "Test conditions: Continuous Bluetooth audio playback using AAC codec "
        "at 50% volume, Active Noise Cancellation (ANC) turned off, standard "
        "firmware and ambient temperature of 23 ± 2°C. Testing starts with a "
        "fully charged battery and continues until playback stops."
    )
    claim = make_claim(
        text=(
            f"The {full_variant} deliver up to 30 hours of continuous "
            "wireless audio playback on a full charge."
        ),
        subject=full_variant,
        attribute="continuous wireless audio playback hours",
        product_scope="variant",
        numeric_value="30",
        unit="hours",
        qualifier="up to",
        conditions=(
            "Continuous Bluetooth audio playback using AAC codec at 50% volume, "
            "Active Noise Cancellation (ANC) turned off, standard firmware and "
            "ambient temperature of 23 ± 2°C. Testing starts with a fully "
            "charged battery and continues until playback stops."
        ),
        value_text="30 hours",
    )
    passport, version = make_records(
        subject=base_subject,
        attribute="wireless audio playback battery life",
        numeric_value="30",
        permitted_value="up to 30 hours",
        product_scope=full_variant,
        channel_scope="Website",
        market_scope="India",
    )
    version["required_conditions"] = (
        "Continuous Bluetooth audio playback using AAC codec at 50% volume; "
        "Active Noise Cancellation (ANC) turned off; standard firmware; "
        "ambient temperature of 23 ± 2°C; testing starts with a fully charged battery."
    )

    assessment = run_match(
        content, claim, passport, version, channel="Website", market="India",
    )

    assert assessment.status == PassportMatchStatus.SUPPORTED
    assert assessment.passport_code == "PFL-TEST-001"
    assert assessment.confidence_score >= 0.95
    factors = {factor.name: factor for factor in assessment.confidence_factors}
    assert factors["passport_unique"].matched is True
    assert factors["subject"].matched is True
    assert factors["attribute"].matched is True
    assert factors["conditions"].matched is True


def test_actual_extracted_variant_subject_still_detects_numeric_conflict():
    content, claim, passport, version = _northstar_extracted_variant_case(hours="40")

    assessment = run_match(
        content,
        claim,
        passport,
        version,
        channel="Website",
        market="India",
    )

    assert assessment.status == PassportMatchStatus.CONFLICT
    assert assessment.passport_code == "PFL-TEST-001"
    assert "Compared 40 hours with 30 hours" in assessment.explanation


def test_exact_variant_match_does_not_bypass_incomplete_required_conditions():
    content, claim, passport, version = _northstar_extracted_variant_case(
        conditions="under the stated demo test conditions"
    )
    version["required_conditions"] = (
        "Continuous Bluetooth audio playback using AAC codec at 50% volume; "
        "Active Noise Cancellation (ANC) turned off; standard firmware; "
        "ambient temperature of 23 ± 2°C; testing starts with a fully charged battery."
    )

    assessment = run_match(
        content,
        claim,
        passport,
        version,
        channel="Website",
        market="India",
    )

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION
    assert assessment.passport_code == "PFL-TEST-001"
    assert 0.30 < assessment.confidence_score <= 0.79
    condition_factor = next(
        factor for factor in assessment.confidence_factors
        if factor.name == "conditions"
    )
    assert condition_factor.matched is False


def test_full_subject_cannot_match_a_different_registered_product_variant():
    content, claim, passport, version = _northstar_extracted_variant_case(
        variant="Pro Model"
    )

    assessment = run_match(
        content,
        claim,
        passport,
        version,
        channel="Website",
        market="India",
    )

    assert assessment.status == PassportMatchStatus.NEEDS_VERIFICATION
    assert assessment.passport_code is None
    assert assessment.confidence_score <= 0.30
