# Proofline Round 3 — Claim Matching Evaluation

The labelled local evaluation dataset is stored at `tests/fixtures/claim_matching_evaluation.json`.
It contains synthetic cases for:

- exact and punctuation/spacing-normalized identity matches;
- hour/minute/day, metric length, mass, percentage and other supported unit aliases/conversions;
- genuine numeric and text conflicts;
- material qualifier differences (including `up to` and `approximately`);
- missing units, unsupported unit dimensions and incomplete evidence conditions;
- product, channel and market scope differences;
- model-year identity, conflicting years and year-specific claims paired with generic Passports;
- absent or ambiguous Passport candidates;
- missing exact source excerpts; and
- due/expired evidence.

## Run the evaluation

From the backend directory, with the project virtual environment active:

```powershell
python scripts/evaluate_claim_matching.py
```

Expected current result: all 32 labelled cases match their expected status. The script prints a confusion matrix and mean deterministic comparison-confidence score. The dataset uses synthetic records only and does not call OpenRouter or another external AI service.

## Confidence interpretation

`confidence_score` is a deterministic **comparison reliability** score. It describes how completely and consistently Proofline could compare the extracted claim with a unique active Passport, including exact excerpt location, identity, value/unit comparability, qualifiers, required conditions, scope and evidence currency.

It is **not** a probability that the claim is true, not an LLM self-assessment, and not an approval score. A high-confidence conflict can mean that the system is confident it identified a comparable but different value. Human review and approval remain mandatory.

Bands are `high` (>= 0.85), `moderate` (>= 0.60), and `low` (< 0.60). An unlocated exact excerpt or zero/multiple Passport candidates is capped below high confidence. Missing material unit, qualifier, condition or restricted scope evidence also caps the score at moderate.

Unit conversion is only performed for explicitly registered aliases within the same physical dimension. Unknown units are only compared when their normalized spellings are identical. Attribute and subject normalization is intentionally conservative (Unicode, case, punctuation and whitespace); it does not invent semantic synonyms.
