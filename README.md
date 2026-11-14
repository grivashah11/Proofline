# Proofline Getting Started ESLint fix

## Replace
- `frontend/src/features/GettingStarted.tsx`

## Cause
The previous lint fix still called a state-updating loader from `useEffect`. The React Hooks `set-state-in-effect` rule follows that call and flags the effect.

## Fix
- Move workspace API retrieval into a module-level `fetchSetupSnapshot()` function that returns data and never updates React state.
- The initial effect starts that fetch and updates state only in the promise settlement callback.
- The manual Refresh button performs loading-state updates directly in its user-interaction handler.
- Ignore late initial-load responses after unmount or workspace/role change.

No changes to API routes, backend, authentication, RLS, role permissions or data model.
