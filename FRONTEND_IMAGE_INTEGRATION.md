# Proofline frontend: Images & assets integration

This is a focused patch for the existing, lint-fixed Proofline frontend. It adds the UI for the backend image endpoints without replacing the existing text review, Brand Knowledge, Claim Passport, review queue, or team pages.

## Files included

Replace these files in the existing frontend with the versions in this patch:

- `frontend/src/App.tsx`
- `frontend/src/lib/api.ts`

Add these new files:

- `frontend/src/lib/images.ts`
- `frontend/src/features/ImagesPage.tsx`
- `frontend/src/features/ImagesPage.css`

## What the UI adds

- New sidebar route: `/images` (Images & assets).
- Brand Owners can register approved images, see active/archived assets, archive assets, and reactivate archived records.
- Workspace members can upload a static image for checking, optionally provide alt text, view the result, and revisit recent image checks.
- Results display exact approved-file matching, matched asset details, image metadata, dominant-color swatches, findings, recommended actions, and detection limitations.
- The submitted image preview is downloaded through the authenticated backend file endpoint; the frontend does not expose public Storage URLs.
- The shared API client leaves `Content-Type` unset for `FormData`, allowing the browser to generate the multipart boundary. It also includes an authenticated blob helper for private image previews.

## Backend endpoints used

- `GET /api/v1/workspaces/{workspace_id}/brand-assets`
- `POST /api/v1/workspaces/{workspace_id}/brand-assets` (`multipart/form-data`: `file`, `asset_name`, optional `description`)
- `PATCH /api/v1/workspaces/{workspace_id}/brand-assets/{asset_id}` (JSON fields: `asset_name`, `description`, `is_active`)
- `DELETE /api/v1/workspaces/{workspace_id}/brand-assets/{asset_id}`
- `GET /api/v1/workspaces/{workspace_id}/image-checks`
- `POST /api/v1/workspaces/{workspace_id}/image-checks` (`multipart/form-data`: `file`, optional `alt_text`)
- `GET /api/v1/workspaces/{workspace_id}/image-checks/{image_check_id}/file`

## Apply the patch

Extract this ZIP into the project root so the `frontend/` paths overlay the existing files. Do not replace `.env.local`, `.env`, `node_modules`, or any other project configuration.

Then, from the `frontend` directory, run:

```bash
npm run lint
npm run build
```

## API base URL note

The frontend continues to use `VITE_API_BASE_URL` from its existing `src/lib/api.ts`, defaulting to `http://127.0.0.1:8000`. If the frontend and backend are running on different computers, `127.0.0.1` points to the computer running the browser, not the backend host. In that setup, set `VITE_API_BASE_URL` in the frontend's local environment to the backend machine's reachable LAN address or deployed API URL, and ensure backend CORS allows the frontend origin.

## Detection limits shown in the UI

The UI describes the backend's current boundaries accurately: SHA-256 matching is byte-for-byte only; dominant colors are metadata and are not scored against a brand palette; alt-text presence is checked but semantic quality is not. It does not claim OCR, visual-similarity detection, or image-authenticity verification.
