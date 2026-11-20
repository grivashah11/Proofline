# Proofline — narrow Claim Passport attribute-alias fix

## What this fixes

The matcher previously required exact normalized attribute strings. It therefore treated these two descriptions as different:

- Passport: `wireless audio playback battery life`
- Extracted claim: `wireless playback battery life`

The patch adds one explicit, phrase-specific alias so both resolve to the same canonical attribute. It does **not** use fuzzy matching or broad token similarity. It does not change subject identity, numeric comparison, unit conversion, qualifiers, conditions, product/channel/market scope, source excerpt validation, evidence validity, or human approval.

## Files in this patch

- `backend/app/services/claim_matcher.py`
- `backend/tests/test_claim_matcher.py`
- `backend/tests/fixtures/claim_matching_evaluation.json`
- `backend/CLAIM_MATCHING_EVALUATION.md`

No database migration, frontend change, environment file, API key, or production configuration is included.

## Apply on macOS

Open a **new Terminal window** so the Vite frontend terminal can remain running.

Working directory: project root `~/Desktop/Proofline`.

1. Back up the matcher outside the repository:

```bash
cp ~/Desktop/Proofline/backend/app/services/claim_matcher.py /tmp/claim_matcher.py.before-alias-fix
```

2. Extract this ZIP into the project root:

```bash
cd ~/Desktop/Proofline
unzip -o ~/Downloads/Proofline-Claim-Matching-Alias-Fix.zip -d .
```

3. Run backend tests. Working directory: `~/Desktop/Proofline/backend`.

```bash
cd ~/Desktop/Proofline/backend
source .venv/bin/activate
python -m pytest -q tests/test_claim_matcher.py tests/test_claim_matching_evaluation.py
python scripts/evaluate_claim_matching.py
python -m pytest -q
```

These tests are deterministic and do not call OpenRouter or consume the daily model-request quota.

## Expected validation

Validated against the supplied backend source snapshot:

- Full backend test suite: **200 passed**
- Focused matcher/evaluation tests: **61 passed**
- Labelled matcher evaluation: **35/35 outcomes matched**

Two existing FastAPI deprecation warnings remain unrelated to this patch.

## After applying

Review the changed files in GitHub Desktop. Commit and push the backend changes using GitHub Desktop, then wait for the Render deployment to report Live. Do not test against the hosted app until the new backend commit is deployed.

Then run two AI-assisted smoke tests in the isolated Proofline Round 3 Test workspace:

1. `up to 30 hours` — must link to the active Passport. It should return **Supported** only when the extracted qualifier, conditions, scope and evidence validity also match. If the test copy only says “under the stated demo test conditions” while the Passport requires more specific conditions, **Needs Verification** is the safe result; the important fix is that the unique Passport is now linked rather than reported as missing.
2. `up to 40 hours` — must link to the same Passport and return **Conflict**, explicitly identifying the 40-hour vs 30-hour difference.

Do not weaken condition/scope/expiry checks just to force a Supported result.
