# Proofline

**Evidence-led brand review before content goes live.**

Proofline is a workspace for preparing brand knowledge, checking content against approved rules and evidence, and keeping the final publication decision with an authorised human reviewer.

- **Production application:** https://proofline-kappa.vercel.app
- **Backend API:** https://proofline-api-cl80.onrender.com
- **Backend health:** https://proofline-api-cl80.onrender.com/api/v1/health
- **Source repository:** https://github.com/grivashah11/Proofline

## What the product does

1. A Brand Owner configures brand voice, messaging rules and terminology.
2. The Brand Owner creates Claim Passports containing approved wording, scope, conditions and supporting evidence.
3. Creators submit content drafts and run checks.
4. Proofline returns deterministic rule findings and evidence-linked claim findings, with advisory AI assistance where available.
5. Creators revise and resubmit content.
6. An authorised Brand Owner reviews the exact submitted revision and approves it, requests changes or rejects it.
7. The workspace retains revision and review history and surfaces governance insights.

**AI assists. People decide.** AI output is advisory; it does not verify a source or approve content.

## Main capabilities

### Workspace and brand setup
- Supabase authentication and role-based workspaces for Brand Owners and Creators.
- Brand voice and messaging rules.
- Preferred, required and restricted terminology.
- Team membership and workspace-scoped access.

### Claim Passports and evidence
- Versioned Claim Passports with approved wording, conditions, product/channel/market scope and review dates.
- PDF and DOCX source upload, secure storage and text extraction.
- Page or document-section references and selectable source excerpts.
- Human verification before a Passport version is activated.
- Expiry and re-verification tracking, with historical versions retained.

### Content review and claim matching
- Saved content drafts and immutable revisions.
- Deterministic terminology and brand-rule checks.
- Candidate factual-claim extraction using the configured OpenRouter route.
- Normalised subject, attribute, value, unit, qualifier and scope comparisons.
- Explainable comparison-confidence factors and ambiguity handling.
- A labelled claim-matching evaluation dataset with expected outcomes.
- Suggested corrections that remain under Creator control.

### Review and governance
- Human review decisions tied to the submitted revision and analysis.
- Revision-difference views.
- Finding lifecycle visibility across revisions (open, resolved and reappeared).
- Reviewer decision context and activity history.
- Recurring issue patterns and candidate guideline/evidence gaps for Brand Owner confirmation.

### Images and assets
- Approved static-image registration and checking.
- Private image storage, exact asset matching and alt-text presence checks.
- Findings explain the limits of each image check; a missing exact match is not proof that an image is unauthorised.

## Judge quick start

The application is authenticated. Judges can create their own accounts; no team member needs to operate the product on their behalf.

### A. Create a Brand Owner workspace

1. Open the production application and choose **Create account**.
2. Register with an email address and password. Complete email confirmation if prompted.
3. Choose **I'm a Brand Owner**.
4. Create a workspace with a brand name.
5. Follow the dashboard's **Your next step** checklist to configure brand voice, terminology and at least one Claim Passport.

### B. Add a Creator account

The review workflow uses separate roles. To test both sides:

1. Open a private/incognito browser window (or a second browser profile).
2. Create a second account and choose **I'm a Creator**.
3. Copy the Creator account ID shown during onboarding.
4. Return to the Brand Owner account, open **Team members**, and add that Creator ID to the workspace.
5. Return to the Creator account and choose **I've been added — refresh access**.

### C. Complete a review cycle

1. As Creator, open **Content reviews** and create a draft.
2. Add the product, channel and market context where applicable; paste the content.
3. Run checks once and inspect findings, Claim Passport evidence, confidence explanations and recommended next actions.
4. Save a new revision after editing, run checks again, and submit the exact revision for review.
5. As Brand Owner, open **Review queue**, inspect the submitted revision and evidence, and record a decision with a reviewer note where useful.
6. Explore revision differences, finding history, reviewer audit context and **Governance insights**.

To evaluate document ingestion, open **Claim Passports**, create a draft version, upload a small PDF or DOCX, inspect the extracted passages, select a source excerpt and save the draft. Extracted text is not automatically approved; the Brand Owner must verify it before activation.

## Architecture

```text
React + Vite + TypeScript (Vercel)
            |
            | HTTPS, Supabase user access token
            v
FastAPI + Pydantic (Render)
   |                    |
   |                    +--> OpenRouter (free-model route; server-side only)
   |
   +--> Supabase PostgreSQL, Auth and private Storage
```

- **Frontend:** React, Vite, TypeScript, React Router.
- **Backend:** Python 3.13, FastAPI, Pydantic, HTTPX.
- **Identity/data/files:** Supabase Auth, PostgreSQL, Row Level Security and private Storage buckets.
- **AI:** OpenRouter through backend HTTPX calls. Credentials never belong in frontend environment variables.
- **Hosting:** Vercel (frontend) and Render (backend).
- **API prefix:** `/api/v1`.

## Local development

### Prerequisites

- Git
- Node.js 22 or newer and npm
- Python 3.13
- `uv` (recommended for the backend environment)
- A Supabase project

### 1. Clone the repository

```bash
git clone https://github.com/grivashah11/Proofline.git
cd Proofline
```

### 2. Configure Supabase

Apply the SQL migrations in `supabase/migrations/` to your Supabase project in timestamp order. The current Round 3 migration set includes the initial workspace/review schema, image assets, source-document ingestion, and claim-matching/governance additions.

Do not disable or weaken Row Level Security. The source-document and image buckets are intended to remain private.

### 3. Configure and run the backend

Copy `backend/.env.example` to `backend/.env` and fill in your own values:

```bash
cd backend
uv sync --group dev
uv run uvicorn app.main:app --reload
```

The backend runs at `http://127.0.0.1:8000`. In development, interactive API documentation is available at `http://127.0.0.1:8000/docs`; the OpenAPI JSON is at `http://127.0.0.1:8000/api/v1/openapi.json`. Documentation routes are disabled when `APP_ENV=production`.

Run backend tests from `backend/`:

```bash
uv run python -m pytest -q
uv run python scripts/evaluate_claim_matching.py
```

The labelled evaluation script uses local fixtures and does not need live OpenRouter calls. The test suite uses mocked Supabase/HTTP boundaries and local fixtures; it must not call the live OpenRouter route. Supply valid development Supabase URL and publishable-key placeholders in `backend/.env` where configuration validation requires them. Never use production credentials for local tests.

### 4. Configure and run the frontend

Copy `frontend/.env.example` to `frontend/.env.local`, then enter your local API URL and the Supabase project URL and publishable key:

```bash
cd frontend
npm ci
npm run dev
```

The Vite development server normally runs at `http://localhost:5173`.

Run frontend checks from `frontend/`:

```bash
npm run lint
npm run build
```

### Environment variables

**Backend — `backend/.env`**

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development`, `test` or `production`; use `development` locally. |
| `API_V1_PREFIX` | API prefix; normally `/api/v1`. |
| `CORS_ORIGINS` | JSON array of allowed frontend origins, e.g. `["http://localhost:5173"]`. |
| `SUPABASE_URL` | Supabase project URL. |
| `SUPABASE_PUBLISHABLE_KEY` | Supabase publishable key used with the authenticated user's token. |
| `OPENROUTER_API_KEY` | Optional for local non-AI work; required for live AI-assisted claim extraction. Keep server-side only. |
| `OPENROUTER_MODEL` | Defaults to `openrouter/free`. |

**Frontend — `frontend/.env.local`**

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend origin only, e.g. `http://127.0.0.1:8000` (do not append `/api/v1`). |
| `VITE_SUPABASE_URL` | Supabase project URL. |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Supabase publishable key. Never put a secret/service-role key in the frontend. |

Never commit `.env`, `.env.local`, access tokens, passwords, service-role keys or OpenRouter secrets.

## Testing and reliability notes

- Run backend pytest, the labelled claim-matching evaluation, frontend lint and production build before release.
- Test both Brand Owner and Creator permissions using separate accounts.
- Test invalid/oversized uploads, unsupported formats, empty states, refresh/persistence and repeated actions.
- Use sample/test workspaces for demonstrations; do not activate fictional or unverified evidence.
- AI extraction can be unavailable or partial. Deterministic findings are retained; an incomplete AI analysis must not be represented as a complete result.
- Confidence describes the reliability of a structured comparison, not the probability that a claim is true.
- A candidate guideline gap is a recommendation only. It never automatically changes approved guidance.

## Future roadmap

1. Optional email/in-app notifications for Passport re-verification and review assignments.
2. More source connectors and controlled evidence refresh workflows.
3. Additional labelled evaluation cases from diverse industries and multilingual content.
4. Configurable governance reporting and exportable audit reports.
5. Integrations with content-management and campaign-publishing systems, while preserving human approval.

These are future directions, not claims that the current build already includes those integrations.

## Team

**We Code Coders** — Griva Shah (frontend/product workflow) and Ansh Pharate (backend/data/claim engine).
