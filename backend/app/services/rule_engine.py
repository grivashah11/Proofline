import re
from collections.abc import Sequence
from uuid import UUID

from fastapi import HTTPException, status

from app.schemas.rule_engine import (
    FindingCategory,
    FindingOutcome,
    FindingSeverity,
    FindingSource,
    RuleCheckResponse,
    RuleFinding,
)

MAX_ENTRIES = 500
MAX_FINDINGS = 1000
MAX_MATCHES_PER_ENTRY = 50


def _build_utf16_offsets(content: str) -> list[int]:
    offsets = [0]

    for character in content:
        width = 2 if ord(character) > 0xFFFF else 1
        offsets.append(offsets[-1] + width)

    return offsets


def _find_matches(
    content: str,
    phrase: str,
    *,
    case_sensitive: bool,
    whole_word: bool,
) -> list[re.Match[str]]:
    if not phrase:
        return []

    escaped = re.escape(phrase)

    if whole_word:
        escaped = rf"(?<!\w){escaped}(?!\w)"

    flags = 0 if case_sensitive else re.IGNORECASE

    return list(re.finditer(escaped, content, flags=flags))[:MAX_MATCHES_PER_ENTRY]


def _append_finding(
    findings: list[RuleFinding],
    *,
    source: FindingSource,
    source_id: str,
    category: FindingCategory,
    outcome: FindingOutcome,
    severity: FindingSeverity,
    title: str,
    message: str,
    recommended_action: str,
    start_index: int | None = None,
    end_index: int | None = None,
    matched_text: str | None = None,
) -> None:
    if len(findings) >= MAX_FINDINGS:
        return

    findings.append(
        RuleFinding(
            source=source,
            source_id=UUID(str(source_id)),
            category=category,
            outcome=outcome,
            severity=severity,
            title=title,
            message=message,
            recommended_action=recommended_action,
            start_index=start_index,
            end_index=end_index,
            matched_text=matched_text,
        )
    )


def _channel_applies(
    configured_channel: str | None,
    selected_channel: str | None,
) -> bool:
    if not configured_channel:
        return True

    if not selected_channel:
        return False

    return configured_channel.casefold() == selected_channel.casefold()


def run_rule_engine(
    *,
    workspace_id: UUID,
    content: str,
    channel: str | None,
    terminology_entries: Sequence[dict],
    brand_rules: Sequence[dict],
) -> RuleCheckResponse:

    if len(terminology_entries) > MAX_ENTRIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Too many terminology entries. Reduce the active entries.",
        )

    if len(brand_rules) > MAX_ENTRIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Too many brand rules. Reduce the active rules.",
        )

    utf16_offsets = _build_utf16_offsets(content)

    findings: list[RuleFinding] = []
    recognized_preferred_terms: list[str] = []

    checks_run = 0
    passed_checks = 0
    conflict_count = 0
    needs_review_count = 0

    # ========================================================
    # TERMINOLOGY CHECKS
    # ========================================================

    for entry in terminology_entries:
        term_type = entry.get("term_type")
        term = entry.get("term", "").strip()

        if not term:
            continue

        matches = _find_matches(
            content,
            term,
            case_sensitive=bool(entry.get("case_sensitive", False)),
            whole_word=bool(entry.get("match_whole_word", True)),
        )

        source_id = entry["id"]

        if term_type == "preferred":
            if matches:
                recognized_preferred_terms.append(term)

            continue

        checks_run += 1

        if term_type == "required":
            if not matches:
                conflict_count += 1

                _append_finding(
                    findings,
                    source=FindingSource.TERMINOLOGY,
                    source_id=source_id,
                    category=FindingCategory.TERMINOLOGY,
                    outcome=FindingOutcome.CONFLICT,
                    severity=FindingSeverity.WARNING,
                    title=f"Missing required terminology: {term}",
                    message=(
                        f"The required phrase '{term}' was not found "
                        "in the submitted content."
                    ),
                    recommended_action=(
                        f"Include the approved phrase '{term}' where relevant."
                    ),
                )
            else:
                passed_checks += 1

        elif term_type == "restricted":
            if matches:
                for match in matches:
                    conflict_count += 1

                    replacement = (
                        entry.get("preferred_replacement")
                        or "approved brand terminology"
                    )

                    _append_finding(
                        findings,
                        source=FindingSource.TERMINOLOGY,
                        source_id=source_id,
                        category=FindingCategory.TERMINOLOGY,
                        outcome=FindingOutcome.CONFLICT,
                        severity=FindingSeverity.ERROR,
                        title=f"Restricted terminology: {term}",
                        message=(
                            f"The restricted phrase '{match.group()}' "
                            "appears in the submitted content."
                        ),
                        recommended_action=(
                            f"Consider replacing it with '{replacement}' "
                            "and review the surrounding sentence."
                        ),
                        start_index=utf16_offsets[match.start()],
                        end_index=utf16_offsets[match.end()],
                        matched_text=match.group(),
                    )
            else:
                passed_checks += 1

    # ========================================================
    # STRUCTURED BRAND RULE CHECKS
    # ========================================================

    for rule in brand_rules:
        rule_id = rule["id"]
        rule_kind = rule.get("rule_kind", "other")
        check_type = rule.get("check_type", "manual_review")
        check_value = rule.get("check_value")
        title = rule.get("title", "Brand rule")
        explanation = rule.get("rule_text", "")

        if not _channel_applies(rule.get("channel"), channel):
            continue

        category = (
            FindingCategory.BRAND_VOICE
            if rule_kind == "brand_voice"
            else FindingCategory.CHANNEL_GUIDANCE
            if rule_kind == "channel_guidance"
            else FindingCategory.MESSAGING
        )

        checks_run += 1

        if check_type == "manual_review":
            needs_review_count += 1
            tone_examples = (rule.get("tone_examples") or "").strip()
            message = f"This brand rule requires human review. Guidance: {explanation}"
            if tone_examples:
                message += f" Tone examples supplied by the Brand Owner: {tone_examples}"
            if len(message) > 4800:
                message = message[:4797].rstrip() + "..."

            _append_finding(
                findings,
                source=FindingSource.BRAND_RULE,
                source_id=rule_id,
                category=category,
                outcome=FindingOutcome.NEEDS_REVIEW,
                severity=FindingSeverity.INFO,
                title=title,
                message=message,
                recommended_action=(
                    "Compare the draft with the approved guidance and examples. "
                    "These examples are references for human review, not an automatic tone score."
                ),
            )
            continue

        if check_type in {
            "contains_phrase",
            "does_not_contain_phrase",
        }:
            if not check_value:
                continue

            matches = _find_matches(
                content,
                check_value,
                case_sensitive=False,
                whole_word=False,
            )

            should_exist = check_type == "contains_phrase"

            if should_exist and not matches:
                conflict_count += 1

                _append_finding(
                    findings,
                    source=FindingSource.BRAND_RULE,
                    source_id=rule_id,
                    category=category,
                    outcome=FindingOutcome.CONFLICT,
                    severity=FindingSeverity.WARNING,
                    title=title,
                    message=(f"The required phrase '{check_value}' was not found."),
                    recommended_action=(
                        f"Add the required phrase '{check_value}' where appropriate."
                    ),
                )

            elif not should_exist and matches:
                for match in matches:
                    conflict_count += 1

                    _append_finding(
                        findings,
                        source=FindingSource.BRAND_RULE,
                        source_id=rule_id,
                        category=category,
                        outcome=FindingOutcome.CONFLICT,
                        severity=FindingSeverity.ERROR,
                        title=title,
                        message=(
                            f"The prohibited phrase '{match.group()}' "
                            "appears in the submitted content."
                        ),
                        recommended_action=(
                            "Remove the prohibited phrase or replace it "
                            "with wording consistent with the rule."
                        ),
                        start_index=utf16_offsets[match.start()],
                        end_index=utf16_offsets[match.end()],
                        matched_text=match.group(),
                    )
            else:
                passed_checks += 1

        elif check_type in {"min_characters", "max_characters"}:
            limit = int(check_value)
            actual = len(content.strip())

            failed = (
                actual < limit if check_type == "min_characters" else actual > limit
            )

            if failed:
                conflict_count += 1

                comparison = "at least" if check_type == "min_characters" else "at most"

                _append_finding(
                    findings,
                    source=FindingSource.BRAND_RULE,
                    source_id=rule_id,
                    category=category,
                    outcome=FindingOutcome.CONFLICT,
                    severity=FindingSeverity.WARNING,
                    title=title,
                    message=(
                        f"The content contains {actual} characters; "
                        f"the rule requires {comparison} {limit}."
                    ),
                    recommended_action=(
                        f"Adjust the content to satisfy the {limit}-character rule."
                    ),
                )
            else:
                passed_checks += 1

    return RuleCheckResponse(
        workspace_id=workspace_id,
        content_length=len(content),
        channel=channel,
        checks_run=checks_run,
        passed_checks=passed_checks,
        conflict_count=conflict_count,
        needs_review_count=needs_review_count,
        recognized_preferred_terms=recognized_preferred_terms,
        findings=findings,
    )
