# Proofline Round 3 — Claim Matching Evaluation

The labelled local evaluation dataset is stored at `tests/fixtures/claim_matching_evaluation.json`. It contains synthetic cases for exact and normalized identity matching, registered product variants, conservative attribute aliases, supported unit conversions, genuine numeric/text conflicts, qualifiers, missing conditions, product/channel/market scope, ambiguous or absent Passport candidates, exact excerpt validation, and evidence review dates.

## Run the evaluation

From the backend directory, with the project virtual environment active:

```bash
python -m pytest -q tests/test_claim_matcher.py tests/test_claim_matching_evaluation.py
python scripts/evaluate_claim_matching.py
python -m pytest -q
```

Expected results for this patch's source snapshot:

- Focused matcher/evaluation tests: **71 passed**
- Labelled deterministic cases: **40/40 outcomes matched**
- Full backend suite: **210 passed**

These tests use synthetic records and do not call OpenRouter or another external AI service.

## Conservative identity rules

- A claim subject may match a Passport's base subject exactly.
- If extraction appends a model variant to the subject, it is accepted only when the complete normalized claim subject exactly equals that Passport version's explicitly registered `product_scope`, and the Passport/version base subjects agree. This prevents a Standard Model claim from matching a Pro Model Passport.
- The generic extracted scope labels `variant`/`model` are not accepted on their own. They are accepted only when the full named variant is explicitly present in the extracted subject and exactly equals the registered Passport product scope.
- The exact attribute phrases `wireless audio playback duration` and `continuous wireless audio playback hours` are normalized to the registered `wireless audio playback battery life` attribute. Existing `wireless playback battery life` alias remains. No fuzzy or token-overlap matching is used.
- Numeric values, units, qualifiers, required conditions, channel/market scope, evidence validity and the exact source excerpt remain independently checked.

## Confidence interpretation

`confidence_score` is deterministic comparison reliability, not a probability that a claim is true and not an approval score. A Passport can now be correctly linked while the claim remains **Needs Verification** because material test conditions are missing. A numeric mismatch remains a **Conflict**. Human review and approval remain mandatory.


## Northstar live-extraction regression

The Northstar fixtures now use the exact attribute label observed from the live
extractor: `continuous wireless audio playback hours`. The deterministic
normalizer maps this phrase to the Passport's canonical attribute
`wireless audio playback battery life`. Regression cases verify that the
Standard Model Passport is selected, a 40-hour claim remains a conflict,
the Pro Model is rejected, and incomplete required conditions still produce
Needs Verification. A full-condition 30-hour claim is supported.

The confidence breakdown also reports subject identity and attribute
normalization independently. An attribute miss no longer incorrectly makes a
successfully matched subject appear to have failed identity matching.
