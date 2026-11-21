# Proofline frontend lint fix

This package replaces the frontend source with the React effect-loading fixes applied.

## Updated files
- `frontend/src/App.tsx`
- `frontend/src/features/ContentReviewsPage.tsx`
- `frontend/src/features/ReviewQueuePage.tsx`
- `frontend/src/features/TeamPage.tsx`

## What changed
- Loading indicators are derived from the workspace/resource whose data has finished loading, instead of setting loading state synchronously at the start of an effect.
- Content and review detail loading is keyed to the selected submission and an explicit reload counter.
- Saving a revision and recording a review decision trigger a fresh detail load.
- Stale workspace data is cleared when a new workspace request fails.
- Existing API calls, routes, and the Claim Passport route are retained.

## Validation
- Parsed all four updated TSX files with the TypeScript parser: passed.
- Full `npm run lint` and `npm run build` have not been run in this packaging environment because the package registry could not complete dependency installation. Run both locally after applying this package.
