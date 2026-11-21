# Proofline — Frontend UX fixes and member display names

This patch applies the requested usability changes to the current Round 3 source snapshot.

## What this changes

1. **Account switching:** after a different account signs in, Proofline navigates to that account's Overview instead of retaining the previous account's route.
2. **Readable text and controls:** improves common workflow form text, field sizes, helper text and member labels. The earlier judge-readability layer remains in place.
3. **Next-step navigation:** adds a consistent next-step card after Brand Rules, Terminology, Claim Passports and Team Members. The Creator Overview has role-specific beginner guidance. Content Reviews keeps its existing explicit Run checks / Submit for review actions; no redundant self-link is added.
4. **Evidence upload alignment:** fixes the file picker and document title field to share the same label/input row height, with a single-column layout on narrow screens.
5. **Creator onboarding buttons:** explicitly styles Copy ID and Back to Sign in / Create Account with a dark background and readable text.
6. **Member display names:** Brand Owners can assign a 2–80 character display name to each workspace member. The name is used in the team list, content comments, reviewer labels and activity history. Account UUIDs remain unchanged and are still available as identifiers.
7. **Creator Overview:** keeps the existing Creator Overview and makes its next action and onboarding guidance clearer.
8. **Content types:** keeps the five values the backend currently supports (Social post, Advertisement, Email, Document and Other). Adds examples under Other rather than sending unsupported content-type values to the API.

## Important: display-name database migration

The display-name feature includes a new Supabase migration:

`supabase/migrations/20261121000100_workspace_member_display_names.sql`

It also includes the matching backend schema and Brand-Owner-only endpoint. The existing workspace-member RLS policy already limits row updates to Brand Owners; this patch does not loosen workspace permissions.

**Do not run `supabase db push` as part of the local frontend check.** The linked Supabase project was previously identified as `proofline-dev · production`. Pushing the migration changes that remote database. Apply it only during the planned deployment sequence, after confirming the linked project is the intended target. The safe deployment order is:

1. Apply and verify the Supabase migration.
2. Deploy the backend changes to Render.
3. Deploy the frontend changes to Vercel.

Until those first two steps are complete, the display-name editor stays hidden and the Team Members page explains that the matching backend/database update is still pending. The other UI fixes can be checked locally without using AI analysis tokens.

## Apply the patch on Griva's Mac

**Project root:** `~/Desktop/Proofline`  
**Terminal:** use the existing Mac Terminal window.

1. Download `Proofline-Frontend-UX-Fixes-Patch.zip` into `~/Downloads`.
2. Open GitHub Desktop and make sure your current work is visible. Do not discard unrelated changes.
3. Back up the files that this patch replaces, then extract the ZIP:

```bash
cd ~/Desktop/Proofline

BACKUP="$HOME/Desktop/Proofline-UX-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"

while IFS= read -r file; do
  if [ -f "$file" ]; then
    mkdir -p "$BACKUP/$(dirname "$file")"
    cp -p "$file" "$BACKUP/$file"
  fi
done <<'FILES'
frontend/src/App.tsx
frontend/src/Auth.css
frontend/src/features/BrandKnowledgePage.tsx
frontend/src/features/ClaimPassportEvidenceTools.css
frontend/src/features/ClaimPassportsPage.tsx
frontend/src/features/ContentReviewsPage.tsx
frontend/src/features/GettingStarted.tsx
frontend/src/features/ReviewQueuePage.tsx
frontend/src/features/TeamPage.tsx
frontend/src/features/WorkflowPages.css
frontend/src/lib/content.ts
backend/app/api/v1/endpoints/workspaces.py
backend/app/schemas/workspaces.py
FILES

unzip -o ~/Downloads/Proofline-Frontend-UX-Fixes-Patch.zip -d .
```

The archive also adds `frontend/src/features/WorkflowNextStep.tsx` and the new Supabase migration. It does not replace `.env`, `.env.local`, package manifests, lockfiles, storage credentials or API keys.

## One consolidated local validation

Do this after all files are applied; no need to run checks after each small edit.

Frontend — **directory:** `~/Desktop/Proofline/frontend`, existing Terminal:

```bash
cd ~/Desktop/Proofline/frontend
npm run lint && npm run build
```

Backend — **directory:** `~/Desktop/Proofline/backend`, existing Terminal:

```bash
cd ~/Desktop/Proofline/backend
source .venv/bin/activate
python -m pytest -q
```

These commands are local validation only. They do not deploy or apply the Supabase migration.

## Quick browser checks (no AI calls required)

- Sign out from one account, sign in to the other account and confirm it opens Overview.
- Open Brand Rules, Terminology, Claim Passports and Team Members; use each page's next-step card.
- Open Claim Passport → version wizard → Evidence; confirm Supporting document and Document title inputs line up.
- Open Creator onboarding in a private window; confirm Copy ID and Back to Sign in buttons have readable text.
- Open Creator Overview; confirm the Getting Started card gives Creator-specific guidance.
- Open New submission; confirm the five supported content types remain and Other explains which additional formats it covers.
- After the migration and backend endpoint are deployed, as Brand Owner set display names for both accounts and confirm those names appear in the Team Members list and review activity.

Do not use `supabase db push` until the linked remote project has been checked and you are intentionally performing the database deployment.
