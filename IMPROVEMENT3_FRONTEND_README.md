# Proofline — Improvement 3 Frontend Integration

**Owner:** Griva Shah (frontend)  
**Backend owner:** Ansh Pharate  
**Scope:** Revision-difference views, finding-resolution tracking, richer reviewer audit context, recurring issue insights and candidate guideline/evidence gaps.

## What this patch adds

1. A **Governance insights** view inside the existing Brand Owner Review Queue. It is not a new top-level route and it is only reachable after the existing Brand Owner role guard.
2. Workspace-level summaries for open, resolved and reappeared finding threads.
3. Recurring issue patterns grouped across distinct submissions.
4. Candidate guideline gaps and evidence gaps, clearly marked for Owner confirmation. The UI never changes a brand rule or Claim Passport automatically.
5. A revision comparison panel in each selected review submission. It calls the immutable revision-diff endpoint and displays inserted, deleted and replaced lines with line coordinates.
6. A finding lifecycle panel showing opened, persisted, resolved and reappeared events for the selected content submission.
7. An expandable review-decision snapshot showing the exact revision and analysis summary captured when the decision was recorded.

## Files in this patch

- `frontend/src/lib/governance.ts` — typed GET clients for the three governance endpoints.
- `frontend/src/lib/content.ts` — complete replacement, adding the optional `review_context` field to `ReviewDecisionRecord` while retaining the Improvement 2 matching types and API helpers.
- `frontend/src/features/ReviewQueuePage.tsx` — complete replacement extending the existing Improvement 2 Review Queue.
- `frontend/src/features/GovernanceInsightsPanel.tsx` — new workspace insights view.
- `frontend/src/features/GovernanceInsightsPanel.css` — new insights styles.
- `frontend/src/features/ReviewGovernancePanels.tsx` — new revision-diff, finding-lifecycle and review-context components.
- `frontend/src/features/ReviewGovernancePanels.css` — styles for the new review panels.

No `App.tsx` route change is required. Open **Review Queue** and click **Governance insights**.

## Backend contract used

All calls are read-only:

- `GET /api/v1/workspaces/{workspace_id}/contents/{content_id}/revision-diff?from_revision_id={uuid}&to_revision_id={uuid}`
- `GET /api/v1/workspaces/{workspace_id}/contents/{content_id}/finding-lifecycle?limit=200`
- `GET /api/v1/workspaces/{workspace_id}/governance/insights?window_days=90&min_distinct_submissions=3&limit=50`
- Existing `GET /api/v1/workspaces/{workspace_id}/contents/{content_id}/reviews`, which now returns `review_context` for each decision.

The insights endpoint is Brand Owner-only on the backend. Revision diff and finding lifecycle require workspace membership. The UI also keeps Governance Insights behind the existing Brand Owner guard.

## Important backend/data behaviour

- `20261119000100_claim_matching_governance.sql` must already be applied and the matching backend version must be deployed. Improvement 2's live confidence fields have already appeared in the user's testing; nevertheless, verify this migration/deployment if any Governance endpoint returns 404/500.
- Finding lifecycle tracking starts with analyses run after the migration. Historical findings are not backfilled into lifecycle threads, so an empty lifecycle panel for older content is expected.
- The insights endpoint proposes candidate guideline/evidence gaps only. Every candidate requires Owner confirmation; no rule, Passport or decision is automatically changed.
- The endpoint may return HTTP 422 when the workspace has over 5,000 lifecycle rows. Narrow the reporting window when instructed by the API.
- Historical review decisions may have an empty `review_context` if their exact revision/analysis pair could not be backfilled. The UI shows a clear fallback instead of fabricating details.
- This UI makes no OpenRouter/AI calls. It uses only GET endpoints.

## Apply on Griva's Mac

First check GitHub Desktop and preserve all uncommitted work. Do not overwrite a file if you have edited it locally since the last patch without reconciling those changes.

**Directory:** `~/Desktop/Proofline`  
**Terminal:** Existing Mac Terminal.

Download this ZIP into `~/Downloads`, then run:

```bash
cd ~/Desktop/Proofline
unzip -o ~/Downloads/Proofline-Improvement3-Frontend-Patch.zip -d .
```

The archive contains complete replacements for the two existing files and the new files listed above. It does not include `.env.local`, `node_modules`, `dist`, or backend files.

## Validate

**Directory:** `~/Desktop/Proofline/frontend`  
**Terminal:** Same Terminal.

```bash
cd ~/Desktop/Proofline/frontend
npm run lint
npm run build
```

Both commands must pass before pushing.

## Manual test plan

1. Sign in as a Brand Owner and open **Review Queue**.
2. Select a submission with at least two saved revisions. Confirm the comparison defaults to the previous revision versus the current revision.
3. Change either revision selector. Confirm the diff updates and marks added, removed and replaced text correctly.
4. Inspect **Issues across revisions**. Confirm lifecycle events, occurrence counts and reappearance counts are displayed. For older submissions, an empty-state message is expected.
5. Open **Review & activity history** for a submission with recorded decisions. Expand **Decision snapshot** and verify the revision number, analysis run and finding counts match the reviewer decision.
6. Click **Governance insights**. Check the reporting-window and minimum-submission filters, resolution summary, recurring issues, guideline-gap candidates and evidence-gap candidates.
7. Confirm candidate recommendations are marked **Owner confirmation** and no action automatically changes a guideline or Passport.
8. Switch workspace and refresh the view. Confirm the insights are scoped to the selected workspace.
9. Verify a Creator still sees the existing access-denied state for Review Queue and cannot reach Governance Insights through this UI.

## GitHub Desktop

After local lint/build and manual checks pass, review only the files in this patch, confirm `.env.local` is not staged, then commit with:

`feat: add governance insights and review audit UI`

Push through GitHub Desktop. Deploy Vercel only after the latest commit is pushed and reviewed.
