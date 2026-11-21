# Proofline — final Claim Passport matching fix

This is a backend-only correction for the exact failure observed in the Northstar Pulse test.

## Why the match failed

The extraction shown in the UI represented the same product/property in a different structure from the saved Passport:

- Passport subject: `Northstar Pulse Wireless Headphones`
- Passport product scope: `Northstar Pulse Wireless Headphones — Standard Model`
- Passport attribute: `wireless audio playback battery life`
- Extracted subject: `Northstar Pulse Wireless Headphones — Standard Model`
- Extracted product scope: `variant`
- Extracted attribute: `wireless audio playback duration`

The previous candidate lookup required an exact base-subject/attribute match, so it never selected the Passport.

## What this patch changes

1. Allows a claim whose subject exactly equals the Passport version's registered full product scope to match the base Passport subject. It first checks the Passport and version base subjects agree. It does not use fuzzy matching and does not merge different variants.
2. Adds one explicit attribute alias: `wireless audio playback duration` → `wireless audio playback battery life`.
3. Updates extraction instructions to keep the base product in `subject`, the exact model in `product_scope`, and use a stable battery-life attribute.
4. Adds deterministic regression tests for the exact extraction shape, numeric conflict, incomplete conditions, and wrong-variant rejection.

This patch does **not** loosen numeric, unit, qualifier, condition, channel, market, evidence expiry, exact-excerpt or human-approval checks. No database migration is required.

## Apply on macOS

Keep your Vite terminal running. Open a **new Terminal window**.

**Working directory: project root `~/Desktop/Proofline`.** First make backups, then extract the ZIP:

```bash
cd ~/Desktop/Proofline
cp backend/app/services/claim_matcher.py /tmp/proofline-claim-matcher.before-final-fix.py
cp backend/app/services/ai/openai_client.py /tmp/proofline-openai-client.before-final-fix.py
cp backend/tests/test_claim_matcher.py /tmp/proofline-test-claim-matcher.before-final-fix.py
cp backend/tests/fixtures/claim_matching_evaluation.json /tmp/proofline-claim-evaluation.before-final-fix.json
cp backend/CLAIM_MATCHING_EVALUATION.md /tmp/proofline-claim-evaluation-doc.before-final-fix.md
unzip -o ~/Downloads/Proofline-Claim-Matching-Final-Fix.zip -d .
```

**Working directory: `~/Desktop/Proofline/backend`.** Run all deterministic tests:

```bash
cd ~/Desktop/Proofline/backend
source .venv/bin/activate
python -m pytest -q tests/test_claim_matcher.py tests/test_claim_matching_evaluation.py
python scripts/evaluate_claim_matching.py
python -m pytest -q
```

Expected results on the supplied source snapshot: **69 focused tests passed**, **39/39 evaluation cases**, and **208 backend tests passed**. Two pre-existing FastAPI deprecation warnings may appear. These tests do not call OpenRouter and use no model tokens.

## Deployment and one live confirmation

Do not deploy unless the three commands above pass on your Mac. Review the five changed files in GitHub Desktop, commit and push the backend changes there, and wait for Render to report the new commit as Live.

Then run **one** fresh analysis in the isolated `Proofline Round 3 Test` workspace using the existing Northstar Pulse verification submission. The intended result is that the finding links to `NSA-PULSE-BATT-001` rather than saying no active Passport was found.

Important: the current draft says only `under the stated demo test conditions`, while the Passport requires specific test conditions (AAC codec, 50% volume, ANC off, standard firmware, 23 ± 2°C, and a fully charged battery). Therefore, after matching is fixed, that draft should remain **Needs Verification** unless the draft/extracted conditions actually establish those requirements. This is correct safety behaviour, not a matching failure. A 40-hour claim should be reported as **Conflict** against the 30-hour Passport.

Do not create another Passport and do not change or loosen the existing Passport conditions to force a Supported outcome.
