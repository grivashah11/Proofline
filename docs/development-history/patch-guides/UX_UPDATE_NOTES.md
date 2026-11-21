# Proofline – First-time UX update

This patch overlays the current frontend source. It does not change backend endpoints, database schema, Supabase settings, authentication, workspace roles, or approval permissions.

## Included changes

1. **Dashboard onboarding guide**
   - Adds a Getting Started checklist to the dashboard.
   - Progress is calculated from live workspace records (brand voice rules, active terminology, active Claim Passports, workspace membership, and a completed review decision).
   - The checklist links directly to the relevant screens and can be refreshed.

2. **Brand Knowledge explanations**
   - Brand Rules page explains what rules and tone examples are for.
   - Terminology page explains Preferred, Required, and Restricted terms and why restricted terms need a suggested replacement.

3. **Claim Passport guided experience**
   - After creating a Passport identity, the user is guided into the first version instead of being left to discover the next action.
   - Version creation is split into three steps: Approved claim, Scope & dates, and Evidence.
   - Help text explains subject/attribute matching, `All` scope, evidence excerpts, review dates, and why versions are retained.
   - The Passport subject is read-only in the version wizard so it stays aligned with the parent Passport identity.
   - A source title, exact excerpt, review-by date, and either a URL or a document reference are required before saving the version draft. The version still requires authorised verification/activation through the existing workflow.

4. **Content review explanations**
   - Adds a simple explanation of the three-stage submission workflow.
   - Finding cards identify what Proofline found, the extracted claim details, the Passport version/evidence used (when available), and the recommended next action.
   - Explicitly explains that “no evidence matched” is not the same as “the claim is false”.
   - Clarifies that an empty findings list is not automatic approval.

## Files in this patch

- `frontend/src/App.tsx`
- `frontend/src/features/GettingStarted.tsx` (new)
- `frontend/src/features/GettingStarted.css` (new)
- `frontend/src/features/BrandKnowledgePage.tsx`
- `frontend/src/features/BrandKnowledge.css`
- `frontend/src/features/ClaimPassportsPage.tsx`
- `frontend/src/features/ClaimPassports.css`
- `frontend/src/features/ContentReviewsPage.tsx`
- `frontend/src/features/WorkflowPages.css`

## Apply on macOS

From the project root (`~/Desktop/Proofline`), first back up the affected files, then extract this ZIP into the root so the `frontend/` folder overlays the existing frontend.

```bash
cd ~/Desktop/Proofline
BACKUP="$HOME/Desktop/Proofline-ux-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for file in \
  frontend/src/App.tsx \
  frontend/src/features/BrandKnowledgePage.tsx \
  frontend/src/features/BrandKnowledge.css \
  frontend/src/features/ClaimPassportsPage.tsx \
  frontend/src/features/ClaimPassports.css \
  frontend/src/features/ContentReviewsPage.tsx \
  frontend/src/features/WorkflowPages.css
 do
  mkdir -p "$BACKUP/$(dirname "$file")"
  cp -p "$file" "$BACKUP/$file"
 done
unzip -o ~/Downloads/proofline-first-time-ux-update.zip -d .
```

Then, from `frontend/`, run:

```bash
npm run lint
npm run build
```

## Validation note

All 16 TypeScript/TSX source files passed a syntax-transpile check in the patching environment. A full `npm run lint` / `npm run build` could not be run here: two `npm ci` attempts timed out and the dependency tree was not available. Run both commands in the existing local project after applying the patch.

## Behaviour to verify manually

- Dashboard checklist statuses change based on actual workspace records; use Refresh after setup changes.
- Create a new Passport: saving its identity should open the first-version wizard.
- Complete the three wizard steps and save a draft version; it should remain a draft until the existing Verify & activate action succeeds.
- Open a content review with a claim that has a matching Passport and one with no matching Passport; findings should distinguish source-backed evidence from missing evidence.
- Verify creator and Brand Owner access still follows the existing role permissions.
