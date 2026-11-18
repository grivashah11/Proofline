import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from app.schemas.claim_extraction import (
    ClaimAssessment,
    ExtractedClaim,
    MatchConfidenceBand,
    MatchConfidenceFactor,
    NormalizedClaimFields,
    PassportMatchStatus,
)

INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")

# We convert only well-defined units within the same physical dimension.
# Unknown units are compared only when their normalized spelling is identical.
_UNIT_DEFINITIONS: dict[str, tuple[str, str, Decimal]] = {}


def _register_units(
    dimension: str,
    canonical: str,
    factor: str,
    aliases: tuple[str, ...],
) -> None:
    value = Decimal(factor)
    for alias in aliases:
        _UNIT_DEFINITIONS[alias] = (dimension, canonical, value)


_register_units("time", "second", "1", ("s", "sec", "secs", "second", "seconds"))
_register_units("time", "second", "60", ("min", "mins", "minute", "minutes"))
_register_units("time", "second", "3600", ("h", "hr", "hrs", "hour", "hours"))
_register_units("time", "second", "86400", ("d", "day", "days"))
_register_units("time", "second", "604800", ("wk", "week", "weeks"))
_register_units("length", "meter", "0.001", ("mm", "millimeter", "millimeters", "millimetre", "millimetres"))
_register_units("length", "meter", "0.01", ("cm", "centimeter", "centimeters", "centimetre", "centimetres"))
_register_units("length", "meter", "1", ("m", "meter", "meters", "metre", "metres"))
_register_units("length", "meter", "1000", ("km", "kilometer", "kilometers", "kilometre", "kilometres"))
_register_units("mass", "gram", "0.001", ("mg", "milligram", "milligrams"))
_register_units("mass", "gram", "1", ("g", "gram", "grams"))
_register_units("mass", "gram", "1000", ("kg", "kilogram", "kilograms"))
_register_units("volume", "liter", "0.001", ("ml", "milliliter", "milliliters", "millilitre", "millilitres"))
_register_units("volume", "liter", "1", ("l", "liter", "liters", "litre", "litres"))
_register_units("power", "watt", "1", ("w", "watt", "watts"))
_register_units("power", "watt", "1000", ("kw", "kilowatt", "kilowatts"))
_register_units("capacity", "milliampere_hour", "1", ("mah", "milliampere hour", "milliamp hours"))
_register_units("capacity", "milliampere_hour", "1000", ("ah", "ampere hour", "amp hours"))
_register_units("percentage", "percent", "1", ("%", "percent", "percentage", "percentages"))
_register_units("data", "byte", "1", ("b", "byte", "bytes"))
_register_units("data", "byte", "1000", ("kb", "kilobyte", "kilobytes"))
_register_units("data", "byte", "1000000", ("mb", "megabyte", "megabytes"))
_register_units("data", "byte", "1000000000", ("gb", "gigabyte", "gigabytes"))
_register_units("data", "byte", "1024", ("kib", "kibibyte", "kibibytes"))
_register_units("data", "byte", "1048576", ("mib", "mebibyte", "mebibytes"))
_register_units("data", "byte", "1073741824", ("gib", "gibibyte", "gibibytes"))


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_identity(value: str | None) -> str:
    """Normalize punctuation/spacing only; do not infer semantic synonyms."""
    normalized = normalize_text(value)
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_subject(value: str | None) -> str:
    """Ignore only a trailing parenthesized model year; retain it for scope checks."""
    normalized = normalize_text(value)
    normalized = re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", normalized)
    return normalize_identity(normalized)


def normalize_attribute(value: str | None) -> str:
    return normalize_identity(value)


def normalize_scope(value: str | None) -> str:
    return normalize_identity(value)


def subject_model_years(*values: str | None) -> set[str]:
    years: set[str] = set()
    for value in values:
        if value:
            years.update(re.findall(r"\b(?:19|20)\d{2}\b", value))
    return years


def normalize_condition_text(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_qualifier(value: str | None) -> str:
    """Preserve material qualifiers such as 'up to' and 'approximately'."""
    return normalize_condition_text(value)


def required_conditions_are_present(
    required_conditions: str | None,
    extracted_conditions: str | None,
) -> bool:
    required = (required_conditions or "").strip()
    extracted = normalize_condition_text(extracted_conditions)
    if not required:
        return True
    if not extracted:
        return False
    clauses = [
        normalize_condition_text(part)
        for part in re.split(r"[.;\n]+", required)
    ]
    clauses = [clause for clause in clauses if clause]
    return bool(clauses) and all(clause in extracted for clause in clauses)


def scope_is_unrestricted(value: str | None) -> bool:
    return normalize_scope(value) in {
        "", "all", "any", "", "all channels", "any channel",
        "all markets", "any market", "all products", "any product", "*",
    }


def normalize_unit(value: str | None) -> str:
    normalized = normalize_text(value)
    return normalized


def _unit_definition(value: str | None) -> tuple[str, str, Decimal] | None:
    normalized = normalize_unit(value)
    if not normalized:
        return None
    return _UNIT_DEFINITIONS.get(normalized)


def units_comparable(expected: str | None, actual: str | None) -> bool:
    expected_norm = normalize_unit(expected)
    actual_norm = normalize_unit(actual)
    if not expected_norm or not actual_norm:
        return False
    if expected_norm == actual_norm:
        return True
    expected_def = _unit_definition(expected_norm)
    actual_def = _unit_definition(actual_norm)
    return bool(
        expected_def
        and actual_def
        and expected_def[0] == actual_def[0]
        and expected_def[1] == actual_def[1]
    )


def convert_measurement(value: Decimal, unit: str | None) -> tuple[str, Decimal] | None:
    definition = _unit_definition(unit)
    if definition is None:
        return None
    dimension, canonical, factor = definition
    return f"{dimension}:{canonical}", value * factor


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def locate_exact_excerpt(
    content: str,
    excerpt: str,
    search_from: int = 0,
) -> tuple[int | None, int | None, int]:
    start = content.find(excerpt, search_from)
    if start == -1:
        start = content.find(excerpt)
    if start == -1:
        return None, None, search_from
    end = start + len(excerpt)
    return utf16_length(content[:start]), utf16_length(content[:end]), end


def parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def decimal_value(value) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _extract_single_number(value: str | None) -> Decimal | None:
    if not value:
        return None
    values = re.findall(
        r"(?<![\w.])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?![\w.])",
        value,
    )
    return decimal_value(values[0]) if len(values) == 1 else None


def _compare_values(
    claim: ExtractedClaim,
    version: dict,
) -> tuple[bool, bool | None, str]:
    expected_numeric = decimal_value(version.get("numeric_value"))
    actual_numeric = decimal_value(claim.numeric_value)
    if actual_numeric is None:
        actual_numeric = _extract_single_number(claim.value_text)

    expected_unit = version.get("unit")
    actual_unit = claim.unit

    if expected_numeric is not None:
        if actual_numeric is None:
            return False, None, "The draft's numerical value could not be reliably extracted."
        if expected_unit and actual_unit:
            expected_converted = convert_measurement(expected_numeric, expected_unit)
            actual_converted = convert_measurement(actual_numeric, actual_unit)
            if expected_converted and actual_converted:
                if expected_converted[0] != actual_converted[0]:
                    return False, None, "The draft and Passport use units from different dimensions."
                return (
                    True,
                    expected_converted[1] == actual_converted[1],
                    f"Compared {actual_numeric} {actual_unit} with {expected_numeric} {expected_unit} using a deterministic unit conversion.",
                )
            if normalize_unit(expected_unit) == normalize_unit(actual_unit):
                return True, expected_numeric == actual_numeric, "The numeric values use the same normalized unit."
            return False, None, "The units are not in a supported, safely comparable conversion family."
        if expected_unit and not actual_unit:
            return False, None, "The draft's unit is missing."
        if not expected_unit and actual_unit:
            return False, None, "The Passport does not specify a unit for comparison."
        return True, expected_numeric == actual_numeric, "The numeric values are directly comparable."

    expected_text = version.get("permitted_value")
    actual_text = claim.value_text or claim.numeric_value
    if expected_text is None or actual_text is None:
        return False, None, "The approved and draft values cannot be compared reliably."

    if expected_unit or actual_unit:
        if not expected_unit or not actual_unit:
            return False, None, "A unit is missing from one side of the comparison."
        if not units_comparable(expected_unit, actual_unit):
            return False, None, "The text values use units that cannot be safely compared."

    return (
        True,
        normalize_condition_text(str(expected_text)) == normalize_condition_text(str(actual_text)),
        "The approved and draft text values were compared after Unicode and whitespace normalization.",
    )


def _scope_match(expected: str | None, actual: str | None) -> tuple[bool | None, str]:
    if scope_is_unrestricted(expected):
        return None, "The Passport does not restrict this scope."
    if not actual:
        return False, "The required scope is missing from the draft context."
    if normalize_scope(expected) == normalize_scope(actual):
        return True, "The scope matches after Unicode, punctuation and whitespace normalization."
    return False, "The draft scope differs from the Passport scope."


def _normalized_claim(claim: ExtractedClaim) -> NormalizedClaimFields:
    numeric = decimal_value(claim.numeric_value)
    if numeric is None:
        numeric = _extract_single_number(claim.value_text)

    unit_definition = _unit_definition(claim.unit)
    if unit_definition is not None:
        unit_dimension, canonical_unit, factor = unit_definition
        normalized_numeric = numeric * factor if numeric is not None else None
        normalized_unit = canonical_unit
    else:
        unit_dimension = None
        normalized_numeric = numeric
        normalized_unit = normalize_unit(claim.unit) or None

    years = subject_model_years(claim.subject, claim.product_scope)

    return NormalizedClaimFields(
        subject=normalize_subject(claim.subject),
        attribute=normalize_attribute(claim.attribute),
        claim_kind=claim.claim_kind,
        value_text=normalize_condition_text(claim.value_text) or None,
        numeric_value=(
            format(normalized_numeric.normalize(), "f")
            if normalized_numeric is not None else None
        ),
        unit=normalized_unit,
        unit_dimension=unit_dimension,
        model_years=sorted(years),
        qualifier=normalize_qualifier(claim.qualifier) or None,
        conditions=normalize_condition_text(claim.conditions) or None,
        product_scope=normalize_scope(claim.product_scope) or None,
        channel_scope=normalize_scope(claim.channel_scope) or None,
        market_scope=normalize_scope(claim.market_scope) or None,
    )


@dataclass(frozen=True)
class _ConfidenceInput:
    name: str
    label: str
    weight: float
    applicable: bool
    matched: bool | None
    explanation: str


def _confidence_result(
    claim: ExtractedClaim,
    *,
    span_verified: bool,
    matching_count: int,
    passport: dict | None,
    version: dict | None,
    channel: str | None,
    market: str | None,
    today: date,
) -> tuple[float, MatchConfidenceBand, list[MatchConfidenceFactor]]:
    factors: list[_ConfidenceInput] = [
        _ConfidenceInput(
            "source_excerpt", "Exact draft excerpt", 0.10, True, span_verified,
            "The extracted passage was located exactly in the saved draft."
            if span_verified else "The extracted passage could not be located exactly in the saved draft.",
        ),
        _ConfidenceInput(
            "passport_unique", "Unique Passport candidate", 0.15, True,
            matching_count == 1,
            "Exactly one active Passport candidate matches the identity fields."
            if matching_count == 1 else (
                "No matching Passport candidate was found." if matching_count == 0
                else "More than one Passport candidate matches; evidence selection is ambiguous."
            ),
        ),
        _ConfidenceInput(
            "subject", "Subject identity", 0.15, True,
            bool(passport),
            "Subject identity matched after conservative normalization."
            if passport else "Subject identity could not be linked to a Passport.",
        ),
        _ConfidenceInput(
            "attribute", "Claim attribute", 0.10, True,
            bool(passport and version and normalize_attribute(claim.attribute) == normalize_attribute(version.get("attribute"))),
            "The attribute matched after conservative normalization."
            if passport and version and normalize_attribute(claim.attribute) == normalize_attribute(version.get("attribute"))
            else "The attribute could not be confirmed against a unique Passport.",
        ),
    ]

    if not passport or not version:
        for name, label, weight, explanation in (
            ("value", "Value comparability", 0.15, "A Passport value is not available for comparison."),
            ("unit", "Unit comparability", 0.10, "A Passport unit is not available for comparison."),
            ("qualifier", "Qualifier identification", 0.10, "A Passport qualifier is not available for comparison."),
            ("conditions", "Required conditions", 0.05, "Passport conditions are not available for comparison."),
            ("scope", "Product/channel/market scope", 0.05, "Passport scope is not available for comparison."),
            ("evidence_current", "Evidence validity", 0.05, "Passport validity cannot be checked without a unique record."),
        ):
            factors.append(_ConfidenceInput(name, label, weight, True, False, explanation))
    else:
        value_comparable, _, value_note = _compare_values(claim, version)
        factors.append(_ConfidenceInput("value", "Value comparability", 0.15, True, value_comparable, value_note))

        expected_unit = version.get("unit")
        actual_unit = claim.unit
        if not expected_unit and not actual_unit:
            factors.append(_ConfidenceInput("unit", "Unit comparability", 0.10, False, None, "Neither record specifies a unit."))
        else:
            factors.append(_ConfidenceInput(
                "unit", "Unit comparability", 0.10, True,
                bool(expected_unit and actual_unit and units_comparable(expected_unit, actual_unit)),
                "The units are identical or have a supported deterministic conversion."
                if expected_unit and actual_unit and units_comparable(expected_unit, actual_unit)
                else "The units are missing or cannot be safely compared.",
            ))

        expected_qualifier = normalize_qualifier(version.get("qualifier"))
        actual_qualifier = normalize_qualifier(claim.qualifier)
        if not expected_qualifier and not actual_qualifier:
            factors.append(_ConfidenceInput("qualifier", "Qualifier identification", 0.10, False, None, "Neither record specifies a material qualifier."))
        else:
            factors.append(_ConfidenceInput(
                "qualifier", "Qualifier identification", 0.10, True,
                bool(expected_qualifier and actual_qualifier),
                "Both sides contain a qualifier that can be compared."
                if expected_qualifier and actual_qualifier
                else "A material qualifier is missing from one side.",
            ))

        required_conditions = version.get("required_conditions")
        if not required_conditions:
            factors.append(_ConfidenceInput("conditions", "Required conditions", 0.05, False, None, "The Passport has no mandatory conditions."))
        else:
            conditions_match = required_conditions_are_present(required_conditions, claim.conditions)
            factors.append(_ConfidenceInput(
                "conditions", "Required conditions", 0.05, True, conditions_match,
                "All required condition clauses were found in the extracted conditions."
                if conditions_match else "One or more required condition clauses are missing or unconfirmed.",
            ))

        scope_checks = [
            _scope_match(version.get("product_scope"), claim.product_scope),
            _scope_match(version.get("channel_scope"), channel or claim.channel_scope),
            _scope_match(version.get("market_scope"), market or claim.market_scope),
        ]
        applicable_scope_checks = [item for item in scope_checks if item[0] is not None]
        scope_match = all(item[0] is True for item in applicable_scope_checks)
        factors.append(_ConfidenceInput(
            "scope", "Product/channel/market scope", 0.05,
            bool(applicable_scope_checks),
            scope_match if applicable_scope_checks else None,
            "Every configured scope was identified and matched."
            if applicable_scope_checks and scope_match
            else "One or more configured scopes are missing or different."
            if applicable_scope_checks
            else "The Passport does not restrict product, channel or market scope.",
        ))

        review_by = parse_date(version.get("review_by"))
        valid_until = parse_date(version.get("valid_until"))
        status_current = (
            passport.get("status") == "active"
            and version.get("status") == "active"
            and review_by is not None
            and review_by > today
            and (valid_until is None or valid_until >= today)
        )
        factors.append(_ConfidenceInput(
            "evidence_current", "Evidence validity", 0.05, True, status_current,
            "The Passport is active and has not reached its review/expiry date."
            if status_current else "The Passport is inactive, missing a review date, expired or due for review.",
        ))

    denominator = sum(f.weight for f in factors if f.applicable)
    numerator = sum(f.weight for f in factors if f.applicable and f.matched)
    score = numerator / denominator if denominator else 0.0

    # An unlocatable excerpt or unresolved candidate ambiguity must never be
    # represented as high-confidence matching, even if other fields look alike.
    if not span_verified or matching_count != 1:
        score = min(score, 0.49)
    if matching_count == 0:
        score = min(score, 0.30)

    critical_gaps = {"unit", "qualifier", "conditions", "scope", "evidence_current"}
    if any(
        factor.name in critical_gaps
        and factor.applicable
        and factor.matched is False
        for factor in factors
    ):
        score = min(score, 0.79)

    band = (
        MatchConfidenceBand.HIGH if score >= 0.85
        else MatchConfidenceBand.MODERATE if score >= 0.60
        else MatchConfidenceBand.LOW
    )

    return (
        round(score, 4),
        band,
        [
            MatchConfidenceFactor(
                name=f.name,
                label=f.label,
                weight=f.weight,
                applicable=f.applicable,
                matched=f.matched,
                explanation=f.explanation,
            )
            for f in factors
        ],
    )


def create_assessment(
    claim: ExtractedClaim,
    status: PassportMatchStatus,
    span_verified: bool,
    start_index: int | None,
    end_index: int | None,
    explanation: str,
    recommended_action: str,
    passport: dict | None = None,
    version: dict | None = None,
    *,
    confidence_score: float = 0.0,
    confidence_band: MatchConfidenceBand = MatchConfidenceBand.LOW,
    confidence_factors: list[MatchConfidenceFactor] | None = None,
) -> ClaimAssessment:
    return ClaimAssessment(
        candidate=claim,
        status=status,
        source_span_verified=span_verified,
        start_index=start_index,
        end_index=end_index,
        passport_id=passport.get("id") if passport else None,
        passport_code=passport.get("passport_code") if passport else None,
        passport_version_id=version.get("id") if version else None,
        passport_version_number=(version.get("version_number") if version else None),
        approved_wording=(version.get("approved_wording") if version else None),
        evidence_source_title=(version.get("evidence_source_title") if version else None),
        evidence_source_url=(version.get("evidence_source_url") if version else None),
        evidence_reference=(version.get("evidence_reference") if version else None),
        evidence_excerpt=(version.get("evidence_excerpt") if version else None),
        confidence_score=confidence_score,
        confidence_band=confidence_band,
        confidence_factors=confidence_factors or [],
        normalized_claim=_normalized_claim(claim),
        explanation=explanation,
        recommended_action=recommended_action,
    )


def find_matching_passports(
    claim: ExtractedClaim,
    passports: list[dict],
    versions_by_id: dict[str, dict],
) -> list[tuple[dict, dict]]:
    matches: list[tuple[dict, dict]] = []
    claim_subject = normalize_subject(claim.subject)
    claim_attribute = normalize_attribute(claim.attribute)

    for passport in passports:
        if passport.get("status") not in {"active", "review_due"}:
            continue
        passport_subject = normalize_subject(passport.get("subject"))
        if not claim_subject or claim_subject != passport_subject:
            continue

        version_id = passport.get("current_version_id")
        if not version_id:
            continue
        version = versions_by_id.get(str(version_id))
        if not version or version.get("status") != "active":
            continue
        if normalize_subject(version.get("subject")) != claim_subject:
            continue
        if normalize_attribute(version.get("attribute")) != claim_attribute:
            continue

        claim_years = subject_model_years(claim.subject, claim.product_scope)
        passport_years = subject_model_years(
            passport.get("subject"), version.get("subject"),
            version.get("product_scope"),
        )
        # If a model year is specified on only one side, identity is incomplete.
        # Do not treat a generic Passport as evidence for a year-specific draft.
        if (claim_years or passport_years) and not (claim_years & passport_years):
            continue

        matches.append((passport, version))

    return matches


def evaluate_passport_claim(
    claim: ExtractedClaim,
    passport: dict,
    version: dict,
    *,
    channel: str | None,
    market: str | None,
    today: date,
) -> tuple[PassportMatchStatus, str, str]:
    if claim.claim_kind.value != passport.get("claim_type"):
        return (
            PassportMatchStatus.NEEDS_VERIFICATION,
            "The extracted claim category differs from the Passport category.",
            "Ask an authorised Brand Owner to verify the claim classification.",
        )

    review_by = parse_date(version.get("review_by"))
    valid_from = parse_date(version.get("valid_from"))
    valid_until = parse_date(version.get("valid_until"))
    if (
        passport.get("status") == "review_due"
        or review_by is None
        or review_by <= today
        or (valid_until is not None and valid_until < today)
    ):
        return (
            PassportMatchStatus.REVIEW_DUE,
            "The Passport evidence has reached its review date or is no longer current.",
            "Ask the Brand Owner to verify and refresh the supporting evidence.",
        )

    if valid_from is not None and valid_from > today:
        return (
            PassportMatchStatus.NEEDS_VERIFICATION,
            "The Passport version is not yet valid.",
            "Verify the applicable effective date with the Brand Owner.",
        )

    scope_results = [
        _scope_match(version.get("product_scope"), claim.product_scope),
        _scope_match(version.get("channel_scope"), channel or claim.channel_scope),
        _scope_match(version.get("market_scope"), market or claim.market_scope),
    ]
    scope_failures = [note for matched, note in scope_results if matched is False]
    if scope_failures:
        return (
            PassportMatchStatus.NEEDS_VERIFICATION,
            " ".join(scope_failures),
            "Confirm the product, channel and market context with the Brand Owner.",
        )

    conflicts: list[str] = []
    uncertainties: list[str] = []

    value_comparable, value_equal, value_note = _compare_values(claim, version)
    if not value_comparable:
        uncertainties.append(value_note)
    elif value_equal is False:
        conflicts.append(value_note)

    expected_qualifier = normalize_qualifier(version.get("qualifier"))
    actual_qualifier = normalize_qualifier(claim.qualifier)
    if expected_qualifier:
        if not actual_qualifier:
            uncertainties.append("The approved qualifier could not be identified in the draft.")
        elif expected_qualifier != actual_qualifier:
            conflicts.append("The draft's qualifier differs from the approved qualifier (for example, 'up to' versus 'approximately').")
    elif actual_qualifier:
        uncertainties.append("The draft includes a qualifier that the Passport does not specify.")

    required_conditions = version.get("required_conditions")
    if required_conditions and not required_conditions_are_present(required_conditions, claim.conditions):
        if not claim.conditions:
            uncertainties.append("Required claim conditions could not be identified.")
        else:
            uncertainties.append("The draft's extracted conditions do not establish all required Passport conditions.")

    if conflicts:
        return (
            PassportMatchStatus.CONFLICT,
            " ".join(conflicts),
            "Review the conflicting claim fields and revise the draft using the approved wording.",
        )
    if uncertainties:
        return (
            PassportMatchStatus.NEEDS_VERIFICATION,
            " ".join(uncertainties),
            "Send the claim to an authorised reviewer for evidence verification.",
        )
    return (
        PassportMatchStatus.SUPPORTED,
        "The normalized claim fields match the active Passport record. This is an application-level comparison, not independent verification of the source.",
        "Retain the supported wording and submit it for human review.",
    )


def match_claims(
    *,
    content: str,
    claims: list[ExtractedClaim],
    passports: list[dict],
    versions: list[dict],
    channel: str | None,
    market: str | None,
) -> list[ClaimAssessment]:
    versions_by_id = {str(version["id"]): version for version in versions}
    today = datetime.now(INDIA_TIMEZONE).date()
    assessments: list[ClaimAssessment] = []
    search_cursor = 0

    for claim in claims:
        start_index, end_index, next_cursor = locate_exact_excerpt(content, claim.exact_text, search_cursor)
        span_verified = start_index is not None
        if span_verified:
            search_cursor = next_cursor

        matching = find_matching_passports(claim, passports, versions_by_id)
        passport = matching[0][0] if len(matching) == 1 else None
        version = matching[0][1] if len(matching) == 1 else None

        if len(matching) == 0:
            outcome = (
                PassportMatchStatus.NEEDS_VERIFICATION,
                "No active Claim Passport with a matching normalized subject and attribute was found.",
                "Ask the Brand Owner to verify the claim and, if appropriate, register an approved Claim Passport.",
            )
        elif len(matching) > 1:
            outcome = (
                PassportMatchStatus.NEEDS_VERIFICATION,
                "Multiple active Claim Passports match the normalized subject and attribute. The correct evidence record is ambiguous.",
                "Ask the Brand Owner to resolve the matching Passport records before relying on this comparison.",
            )
        elif not span_verified:
            outcome = (
                PassportMatchStatus.NEEDS_VERIFICATION,
                "The extracted claim excerpt could not be located exactly in the submitted draft.",
                "Manually select the original claim text before review.",
            )
        else:
            outcome = evaluate_passport_claim(
                claim, passport, version, channel=channel, market=market, today=today,
            )

        score, band, factors = _confidence_result(
            claim,
            span_verified=span_verified,
            matching_count=len(matching),
            passport=passport,
            version=version,
            channel=channel,
            market=market,
            today=today,
        )

        assessments.append(create_assessment(
            claim,
            outcome[0],
            span_verified,
            start_index,
            end_index,
            outcome[1],
            outcome[2],
            passport,
            version,
            confidence_score=score,
            confidence_band=band,
            confidence_factors=factors,
        ))

    return assessments
