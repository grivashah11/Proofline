# Proofline Round 3 — Improvement 1 Frontend Patch

Owner: Griva Shah

This patch extends the existing Claim Passports workflow. It does not replace the application architecture or bypass Brand Owner verification.

## Files

- `frontend/src/lib/api.ts` — adds `apiRequestFile()` for authenticated PDF/DOCX downloads while preserving JSON requests and existing image-blob support.
- `frontend/src/features/ClaimPassportsPage.tsx` — adds re-verification reminders, document-backed source fields to the existing draft-version wizard, and source provenance display for each version.
- `frontend/src/features/ClaimPassportEvidenceTools.tsx` — new source-document upload, library, extracted-segment inspection, passage selection, download, reminders and provenance components.
- `frontend/src/features/ClaimPassportEvidenceTools.css` — styles for the new components.

## Backend endpoints used

- `POST /api/v1/workspaces/{workspace_id}/source-documents` (multipart `file`, optional `title`)
- `GET /api/v1/workspaces/{workspace_id}/source-documents?limit=100`
- `GET /api/v1/workspaces/{workspace_id}/source-documents/{document_id}/segments?limit=100&offset=0`
- `GET /api/v1/workspaces/{workspace_id}/source-documents/{document_id}/file`
- `GET /api/v1/workspaces/{workspace_id}/claim-passports/reverification-reminders?within_days=30`
- `POST /api/v1/workspaces/{workspace_id}/claim-passports/{passport_id}/versions` with optional source link trio:
  - `source_document_id`
  - `source_document_segment_id`
  - `source_excerpt`
- `GET /api/v1/workspaces/{workspace_id}/claim-passports/{passport_id}/versions/{version_id}/sources`

## Behaviour

- Only the Brand Owner sees the re-verification reminders and can upload/select evidence via the existing Passport version editor.
- PDF/DOCX upload is limited client-side to 15 MB and checked server-side as well.
- Text-readable PDFs retain page references; DOCX uses section/paragraph/table references.
- Scanned/image-only PDFs are not OCR processed by this backend.
- Selecting a passage fills the existing evidence fields and adds the three source-link fields. The excerpt can be shortened but must remain an exact continuous substring of the extracted segment; the server validates it.
- The new Passport version remains a draft. Human verification and activation remain mandatory.
- Existing manual URL/document-reference evidence entry remains available. Removing the uploaded-document link clears the source IDs and returns the form to manual source entry.
- Version history displays immutable document provenance and offers download of the original private source file.

## Apply on Griva's Mac

1. Confirm GitHub Desktop has pulled Ansh's latest backend commit and the working tree is clean or backed up.
2. Extract the ZIP at the Proofline project root so the `frontend/` folder merges into the existing project.
3. Review the four changed/new frontend files before accepting replacements.
4. From `~/Desktop/Proofline/frontend`, run:

   ```bash
   npm run lint
   npm run build
   ```

5. Test in a Brand Owner workspace: upload a small text-readable PDF or DOCX, inspect a segment, select it, save a Passport draft, inspect the version provenance and verify that the re-verification reminder endpoint loads.
6. Test Creator role separately: source documents and provenance should be readable, but the Creator must not see upload controls or be able to create/activate Passport versions.

Do not deploy the frontend until lint/build and these workflow checks pass. Verify the Vercel `VITE_API_BASE_URL` is `https://proofline-api-cl80.onrender.com` (without `/api/v1`) before deployment.
