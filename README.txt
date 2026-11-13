PROOFLINE WORKSPACE ONBOARDING FIX

What this patch changes
- Replaces backend/app/api/v1/endpoints/workspaces.py.
- Restores backend/app/core/supabase_gateway.py to its non-diagnostic implementation.
- No SQL migration or RLS policy changes are required for this fix.

Why
Workspace creation previously requested return=representation. The workspaces SELECT policy exposes a row only to workspace members, while the AFTER INSERT trigger creates the initial Brand Owner membership. The insert response therefore attempted to return the new row on the same request that created the owner membership. The revised endpoint uses return=minimal, waits for the insert/trigger request to complete, then reads the workspace using the same authenticated user's access token. Existing RLS and ownership checks remain enabled.

Apply
Extract this ZIP over the project root ~/Desktop/Proofline. It contains only the two replacement files above. Do not replace .env, .env.local, node_modules, or virtual environments.

Then in Mac Terminal:
cd ~/Desktop/Proofline/backend
python -m compileall -q app
python -m pytest -q

Restart/reload Uvicorn if it does not reload automatically, sign out of Proofline, sign back in, and create a workspace with a NEW slug (the previous attempted slug may be available because the failed statement rolled back).

After successful creation, verify in Supabase:
SELECT w.id, w.name, w.slug, w.created_by, wm.user_id, wm.role
FROM public.workspaces AS w
JOIN public.workspace_members AS wm ON wm.workspace_id = w.id
WHERE w.slug = 'apple-product-verification';

Expected: one row where created_by = user_id and role = brand_owner.

Cleanup temporary diagnostic SQL function after successful test:
DROP FUNCTION IF EXISTS public.proofline_debug_auth_context();

No RLS policies are disabled, no service-role key is used, and the workspace owner membership trigger is retained.
