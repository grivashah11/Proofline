# Proofline — Round 3 implementation finish patch

This is a focused patch for the latest source snapshot supplied on 20 November 2026. It does not replace the whole repository.

## Included changes

- Makes claim-value and unit factors say **Comparable** rather than **Matched**. This prevents a value such as 700 nits from appearing to agree with an approved 500 nits merely because the values can be compared.
- Adds an explicit conflict explanation to the backend's value-comparison factor while preserving the existing confidence calculation and API fields.
- Adds a Retry action to the Claim Passport re-verification reminder panel when the reminder request fails.
- Increases readability for evidence ingestion, re-verification, and claim-confidence details.
- Adds safe `.env.example` templates referenced by the root setup guide. They contain placeholders, not credentials.
- Replaces the default Vite frontend README with Proofline-specific setup instructions.
- Adds a backend regression test for the comparable-versus-agreement distinction.

## Apply the patch

1. In GitHub Desktop, make sure your latest local changes are visible and backed up before applying the patch. Do not discard unrelated changes.
2. Open the existing Mac Terminal.
3. Run this from the **project root**:

```bash
cd ~/Desktop/Proofline
unzip -o ~/Downloads/Proofline-Round3-Implementation-Patch.zip -d .
```

The patch writes only the listed files. It does not touch `.env`, `.env.local`, production URLs, Supabase credentials, database contents, or backend deployment settings.

## Environment files

The new `.env.example` files use placeholders. If valid `backend/.env` and `frontend/.env.local` files already exist, keep them; do not replace them with the examples. Never put a Supabase secret/service-role key or OpenRouter API key in a `VITE_` variable.

## Consolidated validation after applying

Backend — run in the **backend directory**:

```bash
cd ~/Desktop/Proofline/backend
uv run python -m pytest -q
uv run python scripts/evaluate_claim_matching.py
uv lock --check
```

Frontend — run in the **frontend directory**:

```bash
cd ~/Desktop/Proofline/frontend
npm ci
npm run lint
npm run build
```

The backend tests and labelled evaluation were run against the supplied source plus this patch in the preparation environment. The frontend dependency install/build could not be completed there because package-network access was unavailable; run the frontend commands on the Mac before deployment.

## After applying

Review the changed files in GitHub Desktop. Commit and push through GitHub Desktop only after the consolidated checks pass. This patch changes both frontend and backend code, so deploy the frontend through the connected Vercel project and deploy the backend through Render. Verify that both deployments use the commit you pushed.
