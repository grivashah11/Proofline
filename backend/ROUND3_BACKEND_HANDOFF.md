# Proofline Round 3 — Consolidated Backend Handoff

**Backend owner:** Ansh Pharate  
**Frontend owner:** Griva Shah  
**Scope:** Improvements 1, 2 and 3.  
**Compatibility:** Additive extension of the existing Round 2 FastAPI/Supabase application. Existing human approval remains mandatory.

> This contract was authored against the uploaded Round 2 source archive plus the supplied Improvement 1 backend patch. Before replacing files, compare them with the latest local Windows working tree and preserve any subsequent local changes.

## Improvement 1 — Evidence ingestion and Claim Passport lifecycle

The full detail remains in `SOURCE_DOCUMENTS_API.md`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/workspaces/{workspace_id}/source-documents` | Brand Owner uploads PDF/DOCX as multipart form data (`file`, optional `title`). |
| `GET` | `/api/v1/workspaces/{workspace_id}/source-documents` | List registered documents. |
| `GET` | `/api/v1/workspaces/{workspace_id}/source-documents/{document_id}` | Read document metadata. |
| `GET` | `/api/v1/workspaces/{workspace_id}/source-documents/{document_id}/segments?limit=50&offset=0` | Read extracted passages with PDF page or DOCX section/paragraph locations. |
| `GET` | `/api/v1/workspaces/{workspace_id}/source-documents/{document_id}/file` | Download the original private file. |
| `POST` | `/api/v1/workspaces/{workspace_id}/claim-passports/{passport_id}/versions` | Create draft Passport version, optionally with the source-document link fields described below. |
| `GET` | `/api/v1/workspaces/{workspace_id}/claim-passports/{passport_id}/versions/{version_id}/sources` | Read immutable source provenance links. |
| `GET` | `/api/v1/workspaces/{workspace_id}/claim-passports/reverification-reminders?within_days=30` | List due/overdue/expired active Passport versions (Brand Owner). |

For a document-backed Passport version, add all three fields together to the existing version request:

```json
{
  "source_document_id": "<source-document-uuid>",
  "source_document_segment_id": "<source-segment-uuid>",
  "source_excerpt": "The exact excerpt selected from that extracted segment."
}
```

The backend requires the excerpt to be an exact substring of the selected segment. The resulting Passport version is a **draft** and still requires Brand Owner source verification and activation. PDF page numbers are retained; DOCX uses heading/paragraph/table references, not fabricated pagination. Image-only PDFs are not OCR-processed.

## Improvement 2 — Higher-reliability claim matching

### Existing endpoint extended

`POST /api/v1/workspaces/{workspace_id}/claim-extraction`

The existing request is unchanged. Each item in `assessments[]` now includes:

```json
{
  "confidence_score": 0.93,
  "confidence_band": "high",
  "confidence_factors": [
    {
      "name": "source_excerpt",
      "label": "Exact draft excerpt",
      "weight": 0.1,
      "applicable": true,
      "matched": true,
      "explanation": "The extracted passage was located exactly in the saved draft."
    }
  ],
  "normalized_claim": {
    "subject": "hydralite bottle",
    "attribute": "cold temperature retention",
    "claim_kind": "promotional",
    "value_text": "up to 24 hours",
    "numeric_value": "86400",
    "unit": "second",
    "unit_dimension": "time",
    "model_years": [],
    "qualifier": "up to",
    "conditions": null,
    "product_scope": "hydralite bottle",
    "channel_scope": null,
    "market_scope": null
  }
}
```

The example is illustrative. Actual scores and normalized fields depend on the claim and unique Passport candidate.

The same metadata is persisted on `analysis_findings` and returned in analysis detail responses as `match_confidence`, `match_confidence_band`, `match_confidence_factors`, and `normalized_claim`. Existing historical findings may return `null` for those new fields because they predate the migration.

### Matching behaviour and interpretation

- Subject, attribute and scope normalize Unicode, case, punctuation and whitespace conservatively; semantic synonyms are not guessed.
- Model years are retained separately; conflicting years, or a year specified on only one side, prevent an automatic Passport match and route the claim for verification.
- Unit aliases are converted only within explicit, known dimensions (for example hours/minutes/seconds, mm/cm/m/km, mg/g/kg, mL/L). Unknown units are only compared for identical normalized spellings.
- Material qualifiers such as `up to` and `approximately` remain distinct.
- Missing/incomparable unit, condition or configured scope, ambiguous Passport candidates, or an exact excerpt that cannot be located route to human verification.
- The existing result statuses are unchanged: `supported`, `conflict`, `review_due`, `needs_verification`.

**Confidence is deterministic comparison reliability, not truth probability, model confidence or approval.** It may be high for a confidently detected conflict. UI should show the band and factor explanations and retain the human-review boundary.

### Evaluation

Dataset: `tests/fixtures/claim_matching_evaluation.json` (32 synthetic labelled cases). Run from `backend/`:

```powershell
python scripts/evaluate_claim_matching.py
```

Expected current result: 32/32 expected outcomes. This evaluation uses no live OpenRouter requests.

## Improvement 3 — Governance insights and review audit

### Endpoints

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/contents/{content_id}/revision-diff?from_revision_id={uuid}&to_revision_id={uuid}` | Workspace member | Compare two immutable saved revisions. |
| `GET` | `/api/v1/workspaces/{workspace_id}/contents/{content_id}/finding-lifecycle` | Workspace member | Return open/resolved finding threads and their `opened`, `persisted`, `resolved`, `reappeared` event history. |
| `GET` | `/api/v1/workspaces/{workspace_id}/governance/insights?window_days=90&min_distinct_submissions=3&limit=50` | Brand Owner | Return recurring patterns, candidate guideline gaps, evidence gaps and resolution summary. |
| `GET` | `/api/v1/workspaces/{workspace_id}/contents/{content_id}/reviews` | Workspace member | Existing endpoint now includes `review_context` captured when each review decision is recorded. |

### Revision diff response

`summary` contains `inserted_lines`, `deleted_lines`, `unchanged_lines` and `changed_blocks`. `operations[]` contains `equal`, `insert`, `delete` or `replace` blocks with 1-based line coordinates and original/new line arrays. It does not mutate revisions.

### Finding lifecycle

Each lifecycle thread is keyed per workspace/content/finding fingerprint. Repeated findings remain open and increment occurrence counts; a finding absent from a complete analysis can resolve; a later occurrence becomes `reappeared`. A partial analysis with AI extraction unavailable does **not** resolve missing AI-claim threads. A supported result resolves a previous issue for that fingerprint. Events retain revision and analysis references.

Lifecycle tracking begins with analyses executed after the migration; historical analysis findings are not backfilled into lifecycle threads. Existing Round 2 review decisions remain intact, and the migration backfills `review_context` for historical decisions where the exact stored revision/analysis pair can be resolved. New decisions capture the same snapshot automatically.

### Governance insights

The owner-only insights endpoint groups lifecycle rows across distinct content submissions. It proposes candidate guideline gaps only for recurring configured brand-rule categories (`messaging`, `brand_voice`, `channel_guidance`) that repeatedly produce `needs_review`. Recurring unverified AI claims can become evidence-gap candidates. All candidates include `requires_owner_confirmation: true`; **no brand rule or Passport is automatically changed**.

The endpoint currently caps the workspace source scan at 5,000 lifecycle rows and returns `422` with a narrowing instruction if that cap is exceeded.

## Database migration

New additive migration:

`supabase/migrations/20261119000100_claim_matching_governance.sql`

It adds the claim comparison metadata columns, finding fingerprints/lifecycle/event tables and read-only member RLS, a deferred analysis-run lifecycle reconciliation trigger, and a `review_context` snapshot on review decisions. It replaces the existing `save_content_analysis` RPC with the same signature/validation/permissions plus persistence of the new match metadata.

The previous migrations `20261113000100` through `20261113000800` and `20261118000100` must already be applied/reconciled before applying this migration. Do not use `db reset`. Preview using `npx supabase db push --dry-run --remote`; apply only if the correct Proofline project is selected and exactly this migration is pending. Back up production data first.

## Security and compatibility

- Existing workspace member/owner authorization checks remain on routes.
- Existing Supabase RLS on content, findings, reviews and Passport tables is retained.
- Lifecycle tables grant authenticated users SELECT only, protected by workspace membership RLS; writes happen through a security-definer deferred trigger.
- Review context is captured from the exact revision and analysis linked to the decision.
- Existing approval RPC and decision states are unchanged.
- No live OpenRouter call is added by the evaluation, governance aggregation, diff or document extraction paths.
- Historical analysis finding rows may have null confidence fields; clients must treat them as unavailable rather than as zero confidence.

## Validation completed in the isolated development copy

- Backend complete test suite: **190 passed**, 2 existing deprecation warnings.
- Labelled matching evaluation: target 30 cases (see command above; must run after the script-path fix in this patch).
- FastAPI OpenAPI inspection: new source-document, Passport reminder, claim-extraction, revision-diff, finding-lifecycle and governance-insights routes register.
- Python `compileall`: should be rerun after applying the patch.

This is local validation of the supplied source snapshot plus the known Improvement 1 patch. It is not proof that the user's latest Windows tree, live Supabase migration, production Render deployment or Vercel integration has passed. Perform the local Windows tests and Supabase dry-run before deployment.
