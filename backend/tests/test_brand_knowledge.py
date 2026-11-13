import pytest
from pydantic import ValidationError

from app.schemas.brand_knowledge import (
    BrandRuleCreate,
    BrandRuleKind,
    BrandRuleUpdate,
    TermEntryCreate,
    TermEntryKind,
    TermEntryUpdate,
)


def test_brand_rule_normalizes_text():
    rule = BrandRuleCreate(
        rule_kind=BrandRuleKind.BRAND_VOICE,
        title="  Brand Voice  ",
        rule_text="  Use warm language.  ",
        tone_examples="  Do: friendly and direct.  ",
    )

    assert rule.title == "Brand Voice"
    assert rule.rule_text == "Use warm language."
    assert rule.tone_examples == "Do: friendly and direct."


def test_brand_rule_rejects_blank_title():
    with pytest.raises(ValidationError):
        BrandRuleCreate(
            rule_kind=BrandRuleKind.MESSAGING,
            title="  ",
            rule_text="Use approved claims.",
        )


def test_brand_rule_rejects_invalid_kind():
    with pytest.raises(ValidationError):
        BrandRuleCreate(
            rule_kind="invalid",
            title="Test Rule",
            rule_text="Test rule text.",
        )


def test_brand_rule_update_rejects_empty_payload():
    update = BrandRuleUpdate()

    assert not update.model_dump(exclude_unset=True)


def test_preferred_term_accepts_missing_replacement():
    term = TermEntryCreate(
        term_type=TermEntryKind.PREFERRED,
        term="HydraLite Bottle",
    )

    assert term.term == "HydraLite Bottle"


def test_restricted_term_requires_replacement():
    with pytest.raises(ValidationError):
        TermEntryCreate(
            term_type=TermEntryKind.RESTRICTED,
            term="guaranteed results",
        )


def test_restricted_term_accepts_replacement():
    term = TermEntryCreate(
        term_type=TermEntryKind.RESTRICTED,
        term="guaranteed results",
        preferred_replacement="results under stated test conditions",
    )

    assert term.preferred_replacement is not None


def test_terminology_normalizes_text():
    term = TermEntryCreate(
        term_type=TermEntryKind.REQUIRED,
        term="  Terms and conditions apply  ",
    )

    assert term.term == "Terms and conditions apply"


def test_terminology_rejects_empty_term():
    with pytest.raises(ValidationError):
        TermEntryCreate(
            term_type=TermEntryKind.REQUIRED,
            term="   ",
        )


def test_terminology_update_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        TermEntryUpdate(
            term="approved term",
            unknown_field="not allowed",
        )


def test_brand_voice_requires_tone_examples():
    with pytest.raises(ValidationError):
        BrandRuleCreate(
            rule_kind=BrandRuleKind.BRAND_VOICE,
            title="Friendly voice",
            rule_text="Use warm, direct language.",
        )
