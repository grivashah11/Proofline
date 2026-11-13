from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.rule_engine import RuleCheckRequest
from app.services.rule_engine import run_rule_engine

WORKSPACE_ID = uuid4()


def terminology(
    term_type: str,
    term: str,
    *,
    case_sensitive: bool = False,
    whole_word: bool = True,
    replacement: str | None = None,
) -> dict:
    return {
        "id": str(uuid4()),
        "term_type": term_type,
        "term": term,
        "preferred_replacement": replacement,
        "case_sensitive": case_sensitive,
        "match_whole_word": whole_word,
    }


def brand_rule(
    check_type: str,
    check_value: str | None,
    *,
    rule_kind: str = "messaging",
    channel: str | None = None,
) -> dict:
    return {
        "id": str(uuid4()),
        "rule_kind": rule_kind,
        "title": "Test brand rule",
        "rule_text": "Test brand guidance.",
        "channel": channel,
        "check_type": check_type,
        "check_value": check_value,
    }


def run_check(
    content: str,
    terms: list[dict] | None = None,
    rules: list[dict] | None = None,
    channel: str | None = None,
):
    return run_rule_engine(
        workspace_id=WORKSPACE_ID,
        content=content,
        channel=channel,
        terminology_entries=terms or [],
        brand_rules=rules or [],
    )


def test_required_term_missing():
    term = terminology("required", "Terms and conditions apply")
    result = run_check("Shop today.", terms=[term])

    assert result.conflict_count == 1
    assert result.findings[0].outcome.value == "conflict"
    assert str(result.findings[0].source_id) == term["id"]


def test_required_term_present():
    term = terminology("required", "Terms and conditions apply")
    result = run_check("Terms and conditions apply.", terms=[term])

    assert result.conflict_count == 0
    assert result.passed_checks == 1


def test_restricted_term_detected():
    term = terminology(
        "restricted",
        "guaranteed results",
        replacement="results under stated conditions",
    )

    result = run_check(
        "We provide guaranteed results today.",
        terms=[term],
    )

    assert result.conflict_count == 1
    assert result.findings[0].matched_text == "guaranteed results"
    assert result.findings[0].start_index == 11
    assert result.findings[0].end_index == 29


def test_restricted_term_case_insensitive():
    result = run_check(
        "GUARANTEED RESULTS are not permitted.",
        terms=[terminology("restricted", "guaranteed results")],
    )

    assert result.conflict_count == 1


def test_term_whole_word_matching():
    result = run_check(
        "This product is outstanding.",
        terms=[terminology("restricted", "standing")],
    )

    assert result.conflict_count == 0
    assert result.passed_checks == 1


def test_term_partial_matching():
    result = run_check(
        "This product is outstanding.",
        terms=[
            terminology(
                "restricted",
                "standing",
                whole_word=False,
            )
        ],
    )

    assert result.conflict_count == 1


def test_case_sensitive_term():
    result = run_check(
        "HYDRALITE BOTTLE",
        terms=[
            terminology(
                "restricted",
                "HydraLite Bottle",
                case_sensitive=True,
            )
        ],
    )

    assert result.conflict_count == 0


def test_preferred_term_is_recognized():
    result = run_check(
        "Meet the HydraLite Bottle.",
        terms=[terminology("preferred", "HydraLite Bottle")],
    )

    assert result.recognized_preferred_terms == ["HydraLite Bottle"]
    assert result.conflict_count == 0


def test_missing_preferred_term_is_not_assumed_wrong():
    result = run_check(
        "Welcome to our store.",
        terms=[terminology("preferred", "HydraLite Bottle")],
    )

    assert result.findings == []
    assert result.conflict_count == 0


def test_required_messaging_phrase_missing():
    rule = brand_rule("contains_phrase", "Terms and conditions apply")
    result = run_check("Shop now.", rules=[rule])

    assert result.conflict_count == 1
    assert result.findings[0].source.value == "brand_rule"


def test_required_messaging_phrase_present():
    result = run_check(
        "Terms and conditions apply.",
        rules=[
            brand_rule(
                "contains_phrase",
                "Terms and conditions apply",
            )
        ],
    )

    assert result.passed_checks == 1
    assert result.conflict_count == 0


def test_prohibited_messaging_phrase():
    result = run_check(
        "Guaranteed for everyone.",
        rules=[brand_rule("does_not_contain_phrase", "Guaranteed")],
    )

    assert result.conflict_count == 1
    assert result.findings[0].matched_text == "Guaranteed"


def test_minimum_character_rule():
    result = run_check(
        "Hi",
        rules=[brand_rule("min_characters", "10")],
    )

    assert result.conflict_count == 1


def test_maximum_character_rule():
    result = run_check(
        "This content is too long.",
        rules=[brand_rule("max_characters", "10")],
    )

    assert result.conflict_count == 1


def test_character_rule_passes():
    result = run_check(
        "Hello",
        rules=[
            brand_rule("min_characters", "3"),
            brand_rule("max_characters", "10"),
        ],
    )

    assert result.passed_checks == 2
    assert result.conflict_count == 0


def test_channel_specific_rule_is_skipped_for_other_channel():
    result = run_check(
        "Hello",
        rules=[
            brand_rule(
                "min_characters",
                "10",
                channel="social",
            )
        ],
        channel="email",
    )

    assert result.checks_run == 0


def test_channel_specific_rule_runs_for_matching_channel():
    result = run_check(
        "Hello",
        rules=[
            brand_rule(
                "min_characters",
                "10",
                channel="social",
            )
        ],
        channel="SOCIAL",
    )

    assert result.checks_run == 1
    assert result.conflict_count == 1


def test_manual_review_rule_is_not_automatically_rejected():
    result = run_check(
        "A draft for review.",
        rules=[
            brand_rule(
                "manual_review",
                None,
                rule_kind="brand_voice",
            )
        ],
    )

    assert result.needs_review_count == 1
    assert result.conflict_count == 0
    assert result.findings[0].outcome.value == "needs_review"


def test_empty_content_is_rejected():
    with pytest.raises(ValidationError):
        RuleCheckRequest(content="   ")


def test_unknown_request_fields_are_rejected():
    with pytest.raises(ValidationError):
        RuleCheckRequest(
            content="Test content",
            unknown_field="not allowed",
        )


def test_workspace_rule_check_requires_authentication():
    workspace_id = uuid4()

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/rule-checks",
            json={
                "content": "Test content",
                "channel": "social",
            },
        )

    assert response.status_code == 401


def test_offsets_match_javascript_utf16_indices():
    draft = "😀 guaranteed results"

    result = run_check(
        draft,
        terms=[terminology("restricted", "guaranteed results")],
    )

    finding = result.findings[0]

    highlighted_text = draft.encode("utf-16-le")[
        finding.start_index * 2 : finding.end_index * 2
    ].decode("utf-16-le")

    assert highlighted_text == "guaranteed results"
    assert finding.start_index == 3
