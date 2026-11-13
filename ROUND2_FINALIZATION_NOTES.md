# Proofline Round 2 finalization patch

This patch closes two documented Round 2 gaps:

1. **Manual missed-claim addition** in Content Reviews. A Creator or Brand Owner can add a verbatim excerpt from the current revision when extraction misses it. The API verifies the exact excerpt exists in the current revision and saves the finding to that analysis. The status is always `needs_verification`; manual entry cannot mark a claim as supported or approve it.
2. **Manual Brand Voice examples.** Brand Voice rules now carry a dedicated `tone_examples` field. New Brand Voice rules must include examples. The deterministic analysis result includes them in the human-review finding; Proofline does not pretend to assign an automatic tone score.

The change is additive. It preserves existing content, analysis, review, and image endpoints. Apply the SQL migration once before running the new code.

## Apply the patch

Extract the ZIP into the project root (`C:\Games\Proofline` on Ansh's Windows machine, `~/Desktop/Proofline` on Griva's Mac). It contains complete replacements only for the listed application files plus the new migration and documentation. It does not include `.env`, `.env.local`, `node_modules`, or `.venv`.

Apply `supabase/migrations/20261113000800_manual_claims_and_tone_examples.sql` in the same Supabase project, after migration 007. Do not run it twice.

## API addition

`POST /api/v1/workspaces/{workspace_id}/contents/{content_id}/analyses/{analysis_id}/manual-claims`

Request JSON contains `exact_text`, `subject`, `attribute`, `claim_kind`, and optional value/unit/qualifier/condition fields. `exact_text` must be a verbatim contiguous excerpt from the current saved revision. The response is the updated `AnalysisDetail` with a new finding marked `needs_verification` and an incremented `claim_needs_verification_count`.

The database function checks workspace membership, editable content status, current revision, analysis/revision relationship, excerpt presence, and duplicates. It always persists the finding as `needs_verification`, even if callers attempt to submit different status values.

## Mac frontend ↔ Windows backend

Both computers must be on the same trusted LAN/Wi-Fi for this simple setup.

On Ansh's Windows machine, from `C:\Games\Proofline\backend`:

```powershell
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
ipconfig
```

Find the Windows machine's IPv4 address for the active Wi-Fi/Ethernet adapter (for example `192.168.1.25`). If Windows Firewall blocks the connection, open PowerShell as Administrator and add a private-network rule:

```powershell
New-NetFirewallRule -DisplayName "Proofline API 8000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private
```

On Griva's Mac, create/update `frontend/.env.local` (do not commit this local file):

```dotenv
VITE_API_BASE_URL=http://192.168.1.25:8000
```

Replace `192.168.1.25` with Ansh's actual Windows IPv4 address. Keep Vite running on `http://localhost:5173` so the backend's default CORS origin matches. Restart Vite after changing `.env.local`.

From the Mac browser, verify `http://192.168.1.25:8000/api/v1/health` opens. Then sign in to Proofline and check the content and Images & assets pages.

## Validation performed in the patch workspace

- Backend `compileall`: passed.
- Backend pytest: **103 passed**, 2 deprecation warnings.
- TypeScript/TSX transpilation syntax check: 15 files, 0 syntax errors.
- A full frontend `tsc -b`/Vite build could not be rerun in this patch workspace because dependency installation timed out and the local `node_modules` directory was left incomplete. Griva should run `npm run lint` and `npm run build` from `frontend` after overlaying the patch.

The SQL migration was reviewed but not executed against a live PostgreSQL instance from this patch workspace. Apply it in Supabase and complete the two-account end-to-end test before declaring Round 2 fully verified.
