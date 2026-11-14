import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from app.schemas.claim_extraction import (
    ClaimAssessment,
    ExtractedClaim,
    PassportMatchStatus,
)

INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""

    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.casefold()

    return re.sub(r"\s+", " ", normalized).strip()


def normalize_subject(value: str | None) -> str:
    """Normalize a subject while tolerating a trailing parenthesized model year.

    The year is retained separately by ``subject_model_years`` so a 2024 claim
    cannot be matched to a Passport scoped to the 2025 model.
    """
    normalized = normalize_text(value)
    normalized = re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", normalized)
    return normalized.strip()


def subject_model_years(*values: str | None) -> set[str]:
    years: set[str] = set()
    for value in values:
        if value:
            years.update(re.findall(r"\b(?:19|20)\d{2}\b", value))
    return years


def normalize_condition_text(value: str | None) -> str:
    """Normalize punctuation and whitespace without dropping condition words."""
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()


def required_conditions_are_present(
    required_conditions: str | None,
    extracted_conditions: str | None,
) -> bool:
    """Require every configured condition clause to be represented in extraction.

    Clauses are copied from the source draft by the extractor. Normalizing
    punctuation makes sentence separators immaterial, while retaining all
    words keeps this check conservative: a partial or paraphrased condition
    does not silently become a pass.
    """
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
    normalized = normalize_text(value)
    return normalized in {
        "",
        "all",
        "any",
        "*",
        "all channels",
        "any channel",
        "all markets",
        "any market",
    }


def normalize_unit(value: str | None) -> str:
    normalized = normalize_text(value)
    aliases = {
        "hour": "hour",
        "hours": "hour",
        "hr": "hour",
        "hrs": "hour",
        "minute": "minute",
        "minutes": "minute",
        "min": "minute",
        "mins": "minute",
        "day": "day",
        "days": "day",
        "week": "week",
        "weeks": "week",
        "month": "month",
        "months": "month",
        "year": "year",
        "years": "year",
    }
    return aliases.get(normalized, normalized)


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

    return (
        utf16_length(content[:start]),
        utf16_length(content[:end]),
        end,
    )


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

        if not result.is_finite():
            return None

        return result

    except (InvalidOperation, ValueError):
        return None


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
        evidence_source_title=(
            version.get("evidence_source_title") if version else None
        ),
        evidence_source_url=(version.get("evidence_source_url") if version else None),
        evidence_reference=(version.get("evidence_reference") if version else None),
        evidence_excerpt=(version.get("evidence_excerpt") if version else None),
        explanation=explanation,
        recommended_action=recommended_action,
    )


def find_matching_passports(
    claim: ExtractedClaim,
    passports: list[dict],
    versions_by_id: dict[str, dict],
) -> list[tuple[dict, dict]]:

    matches = []

    for passport in passports:
        if passport.get("status") not in {
            "active",
            "review_due",
        }:
            continue

        # A model year may be appended by the extractor even when the
        # Brand Owner omitted it from the subject field. Ignore only a
        # trailing parenthesized year for identity comparison, and separately
        # reject an explicit year conflict using the source/product scope.
        claim_subject = normalize_subject(claim.subject)
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

        claim_years = subject_model_years(
            claim.subject,
            claim.product_scope,
            claim.exact_text,
        )
        passport_years = subject_model_years(
            passport.get("subject"),
            version.get("subject"),
            version.get("product_scope"),
            version.get("approved_wording"),
        )
        if claim_years and passport_years and not (claim_years & passport_years):
            continue

        if normalize_text(version.get("attribute")) != normalize_text(claim.attribute):
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

    expected_channel = normalize_text(version.get("channel_scope"))

    if not scope_is_unrestricted(expected_channel):
        if not channel:
            return (
                PassportMatchStatus.NEEDS_VERIFICATION,
                "The Passport requires a specific channel, but the draft channel was not supplied.",
                "Select the intended publication channel.",
            )

        if normalize_text(channel) != expected_channel:
            return (
                PassportMatchStatus.NEEDS_VERIFICATION,
                "The claim is being checked outside the Passport's approved channel scope.",
                "Ask the Brand Owner to verify whether the Passport applies to this channel.",
            )

    expected_market = normalize_text(version.get("market_scope"))

    if not scope_is_unrestricted(expected_market):
        if not market:
            return (
                PassportMatchStatus.NEEDS_VERIFICATION,
                "The Passport requires a specific market, but no market was supplied.",
                "Select the intended market for this content.",
            )

        if normalize_text(market) != expected_market:
            return (
                PassportMatchStatus.NEEDS_VERIFICATION,
                "The claim is outside the Passport's specified market scope.",
                "Ask the Brand Owner to verify the correct market-specific evidence.",
            )

    conflicts: list[str] = []
    uncertainties: list[str] = []

    expected_numeric = decimal_value(version.get("numeric_value"))
    actual_numeric = decimal_value(claim.numeric_value)

    # Some structured extractors populate value_text reliably but omit the
    # dedicated numeric field. A single unambiguous number in value_text is
    # safe to compare; do not infer from the whole sentence, which may contain
    # model numbers or dates.
    if actual_numeric is None and claim.value_text:
        value_numbers = re.findall(
            r"(?<![\w.])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?![\w.])",
            claim.value_text,
        )
        if len(value_numbers) == 1:
            actual_numeric = decimal_value(value_numbers[0])

    expected_text = version.get("permitted_value")

    if expected_numeric is not None:
        if actual_numeric is None:
            uncertainties.append("The numerical value could not be reliably extracted.")

        elif actual_numeric != expected_numeric:
            conflicts.append(
                f"Expected numeric value {expected_numeric}, "
                f"but the draft states {actual_numeric}."
            )

    elif expected_text is not None:
        actual_text = claim.value_text or claim.numeric_value

        if actual_text is None:
            uncertainties.append(
                "The approved value could not be compared with the draft."
            )

        elif normalize_text(actual_text) != normalize_text(expected_text):
            conflicts.append(
                f"Expected approved value '{expected_text}', "
                f"but the draft states '{actual_text}'."
            )

    else:
        uncertainties.append(
            "The Passport does not contain a comparable approved value."
        )

    expected_unit = normalize_unit(version.get("unit"))
    actual_unit = normalize_unit(claim.unit)

    if expected_unit:
        if not actual_unit:
            uncertainties.append("The draft's unit could not be reliably identified.")
        elif actual_unit != expected_unit:
            uncertainties.append(
                "The draft uses a unit that requires human verification. "
                "Automatic unit conversion is not performed."
            )

    elif actual_unit:
        uncertainties.append("The Passport does not specify a unit for comparison.")

    expected_qualifier = normalize_text(version.get("qualifier"))
    actual_qualifier = normalize_text(claim.qualifier)

    if expected_qualifier:
        if not actual_qualifier:
            uncertainties.append(
                "The approved qualifier could not be identified in the draft."
            )
        elif expected_qualifier != actual_qualifier:
            conflicts.append(
                "The draft's qualifier differs from the approved qualifier."
            )

    elif actual_qualifier:
        uncertainties.append(
            "The draft includes a qualifier that the Passport does not specify."
        )

    required_conditions = version.get("required_conditions")

    if required_conditions and not required_conditions_are_present(
        required_conditions,
        claim.conditions,
    ):
        if not claim.conditions:
            uncertainties.append("Required claim conditions could not be identified.")
        else:
            uncertainties.append(
                "The draft's extracted conditions do not establish all "
                "required Passport conditions."
            )

    if conflicts:
        return (
            PassportMatchStatus.CONFLICT,
            " ".join(conflicts),
            (
                "Review the conflicting claim fields and revise the draft "
                "using the approved wording."
            ),
        )

    if uncertainties:
        return (
            PassportMatchStatus.NEEDS_VERIFICATION,
            " ".join(uncertainties),
            "Send the claim to an authorised reviewer for evidence verification.",
        )

    return (
        PassportMatchStatus.SUPPORTED,
        (
            "The extracted claim fields match the active Passport record. "
            "This is an application-level comparison, not independent "
            "verification of the source."
        ),
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
        start_index, end_index, next_cursor = locate_exact_excerpt(
            content,
            claim.exact_text,
            search_cursor,
        )

        span_verified = start_index is not None

        if span_verified:
            search_cursor = next_cursor

        matching = find_matching_passports(
            claim,
            passports,
            versions_by_id,
        )

        if len(matching) == 0:
            assessments.append(
                create_assessment(
                    claim,
                    PassportMatchStatus.NEEDS_VERIFICATION,
                    span_verified,
                    start_index,
                    end_index,
                    (
                        "No active Claim Passport with an exact matching "
                        "subject and attribute was found."
                    ),
                    (
                        "Ask the Brand Owner to verify the claim and, "
                        "if appropriate, register an approved Claim Passport."
                    ),
                )
            )
            continue

        if len(matching) > 1:
            assessments.append(
                create_assessment(
                    claim,
                    PassportMatchStatus.NEEDS_VERIFICATION,
                    span_verified,
                    start_index,
                    end_index,
                    (
                        "Multiple active Claim Passports match this claim. "
                        "The correct evidence record is ambiguous."
                    ),
                    "Ask the Brand Owner to resolve the matching Passport records.",
                )
            )
            continue

        passport, version = matching[0]

        if not span_verified:
            assessments.append(
                create_assessment(
                    claim,
                    PassportMatchStatus.NEEDS_VERIFICATION,
                    False,
                    None,
                    None,
                    (
                        "The AI extraction did not return an exact excerpt "
                        "that could be located in the submitted draft."
                    ),
                    "Manually select the original claim text before review.",
                    passport,
                    version,
                )
            )
            continue

        result_status, explanation, action = evaluate_passport_claim(
            claim,
            passport,
            version,
            channel=channel,
            market=market,
            today=today,
        )

        assessments.append(
            create_assessment(
                claim,
                result_status,
                True,
                start_index,
                end_index,
                explanation,
                action,
                passport,
                version,
            )
        )

    return assessments
