# Proofline — exact live-extraction Claim Passport matching fix

This patch corrects the specific gap left by the previous Claim Matching Final Fix.

## Root cause confirmed from the latest UI evidence

The live AI extraction used:

- Subject: `Northstar Pulse Wireless Headphones — Standard Model`
- Product scope: `variant`
- Attribute: `continuous wireless audio playback hours`

The active Passport uses:

- Subject: `Northstar Pulse Wireless Headphones`
- Product scope: `Northstar Pulse Wireless Headphones — Standard Model`
- Attribute: `wireless audio playback battery life`

The previous patch tested `wireless audio playback duration`, not the exact
attribute string emitted by the live extractor. Because the actual phrase was
not in the deterministic alias table, candidate selection rejected the
otherwise matching Passport before numeric comparison.

## What this patch changes

1. Adds the exact observed phrase `continuous wireless audio playback hours`
   as a phrase-specific alias to the Passport's canonical battery-life
   attribute. It does not add fuzzy or token-overlap matching.
2. Keeps the exact registered-variant subject check and all existing numeric,
   unit, qualifier, conditions, product/channel/market scope, evidence-date,
   and source-excerpt checks.
3. Makes the confidence breakdown report subject identity and attribute
   matching independently. A correct subject will no longer be shown as a
   failed subject merely because the attribute label did not match.
4. Replaces the Northstar evaluation fixture wording with the exact live
   extraction wording and adds a full-condition 30-hour supported case.

No database migration is required. No frontend files are changed.

## Apply on macOS

Keep the frontend terminal running. Use a **new Terminal window** for this patch.

**Working directory: project root `~/Desktop/Proofline`.** Back up the current
post-Final-Fix files, then extract the ZIP:

```bash
cd ~/Desktop/Proofline
cp backend/app/services/claim_matcher.py /tmp/proofline-claim-matcher.before-exact-extraction-fix.py
cp backend/app/services/ai/openai_client.py /tmp/proofline-openai-client.before-exact-extraction-fix.py
cp backend/tests/test_claim_matcher.py /tmp/proofline-test-claim-matcher.before-exact-extraction-fix.py
cp backend/tests/fixtures/claim_matching_evaluation.json /tmp/proofline-claim-evaluation.before-exact-extraction-fix.json
cp backend/CLAIM_MATCHING_EVALUATION.md /tmp/proofline-claim-evaluation-doc.before-exact-extraction-fix.md
unzip -o ~/Downloads/Proofline-Claim-Matching-Exact-Extraction-Fix.zip -d .
```

**Working directory: backend `~/Desktop/Proofline/backend`.** In a **new
Terminal window**, run the deterministic test suite:

```bash
cd ~/Desktop/Proofline/backend
source .venv/bin/activate
python -m pytest -q tests/test_claim_matcher.py tests/test_claim_matching_evaluation.py
python scripts/evaluate_claim_matching.py
python -m pytest -q
```

Expected on the included source state:

- 71 focused tests passed
- 40/40 labelled evaluation cases matched
- 210 backend tests passed

Two existing FastAPI/Starlette deprecation warnings may still appear. These
tests do not call OpenRouter.

## Local UI confirmation — no new draft revision

After tests pass:

1. Restart the local backend so it loads the new Python code. In the existing
   backend Terminal, press `Control + C`, then from `~/Desktop/Proofline/backend`
   with `.venv` active, run `uvicorn app.main:app --reload`.
2. Keep the same saved revision of `Northstar Pulse — Matching Fix Verification`.
   Do not edit it and do not create a new revision.
3. Return to that same submission as the Creator and click **Run checks** once.
4. Confirm the finding is linked to Passport `NSA-PULSE-BATT-001`, and the
   comparison factors show the unique candidate, subject and attribute as
   matched. It must no longer say that no Passport candidate was found.
5. Confirm the 30-hour value is compared against the Passport's 30-hour value.
   If every required test condition is present, the claim should be Supported.
   If any required condition is missing, it must remain Needs Verification.
   A 40-hour claim must remain a Conflict.

The backend has a cache for completed extraction on the same saved content
revision and model profile. Re-running checks on that unchanged revision should
reuse the saved extraction and recalculate matching without another AI request.
If a new revision is created or the extraction profile changes, that cache
cannot be assumed to apply.

## Deployment gate

Do not deploy merely because the unit tests pass. First verify the local UI
shows the active Passport is selected in the exact same revision. Only then
review/commit/push the backend changes through GitHub Desktop and deploy the
new backend commit to Render. No Supabase migration is needed.
