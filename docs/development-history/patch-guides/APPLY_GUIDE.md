# Proofline — Judge usability pass

This patch is a focused usability enhancement for the already-integrated Round 3 frontend. It does not change API contracts, Supabase configuration, backend behaviour, review decisions, or feature permissions.

## Files

Replace/add these files relative to the repository root:

- `frontend/src/App.tsx` — role-aware dashboard primary action and a collapsed-by-default workflow explainer.
- `frontend/src/JudgeUsability.css` — consolidated readability, spacing, form-control, focus-state and responsive overrides across authentication, onboarding, dashboard, content reviews, Claim Passports, governance, and assets.

## Before applying

1. Open GitHub Desktop and inspect the current working tree.
2. Commit or back up any work you do not want overwritten.
3. This replacement `App.tsx` assumes the Round 3 UX patch has already been applied, including grouped navigation and the current imports/features.
4. Do not overwrite `.env`, `.env.local`, or any secret file.

## Apply on macOS

From `~/Desktop/Proofline`:

```bash
unzip -o ~/Downloads/Proofline-Judge-Usability-Pass.zip -d .
```

## Validate after applying

From `~/Desktop/Proofline/frontend`:

```bash
npm run lint
npm run build
```

Then start the local UI:

```bash
npm run dev
```

## UX changes

- Brand Owners get a direct “Open review queue” primary action; Creators get “Submit content”.
- The three-step “How Proofline works” explainer is collapsed by default to reduce dashboard congestion while remaining available.
- Sidebar, dashboard, forms, findings, confidence explanations, governance, onboarding and help text have larger readable type.
- Form controls and frequently used icon controls have larger targets.
- Focus indicators and mobile layouts are strengthened.
- Existing workflow steps, APIs, data models and permission checks remain unchanged.

The patch does not itself establish functional correctness. Run the consolidated judge-style regression plan after all UX updates have been applied.
