# Proofline: Approved Brand Assets and Static Image Checks

This backend update is additive. It does not change the existing text rule-check, claim extraction, content revision, analysis, or review endpoints.

## Requirements and configuration

- No new Python dependency is required. The backend already declares `Pillow` and `python-multipart`.
- No service-role key is used. Storage requests use the authenticated user's JWT plus the Supabase publishable key, just like the existing REST gateway.
- The private Storage bucket is created by the new migration: `proofline-workspace-images`.
- Supported uploads: JPEG, PNG, and WebP; static images only; maximum 8 MiB; maximum 8,000 pixels per dimension and 20 million total pixels.

## Apply the database migration

Apply `supabase/migrations/20261113000700_image_assets_and_checks.sql` to the same Supabase project after the existing migrations. It creates:

- `public.brand_assets`
- `public.image_checks`
- the private `proofline-workspace-images` bucket
- RLS policies and the required authenticated table privileges

The migration assumes the existing Proofline foundation is already applied, including `public.is_workspace_member`, `public.has_workspace_role`, and `public.set_updated_at`.

## API endpoints

All endpoints are under `/api/v1` and require `Authorization: Bearer <Supabase user access token>`.

### Approved brand assets

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/workspaces/{workspace_id}/brand-assets` | Workspace member | List visible approved assets (Brand Owners also see archived records) |
| POST | `/workspaces/{workspace_id}/brand-assets` | Brand Owner | Register and upload an approved image |
| PATCH | `/workspaces/{workspace_id}/brand-assets/{asset_id}` | Brand Owner | Rename, edit description, or activate/archive using `is_active` |
| DELETE | `/workspaces/{workspace_id}/brand-assets/{asset_id}` | Brand Owner | Soft-archive an asset; the original file and historical references are retained |
| GET | `/workspaces/{workspace_id}/brand-assets/{asset_id}/file` | Workspace member | Download/preview the private image; inactive records are visible only to Brand Owners |

`POST brand-assets` is `multipart/form-data`:

- `file`: JPEG, PNG, or WebP image
- `asset_name`: required, 2–120 characters
- `description`: optional, up to 2,000 characters

A second upload with the same SHA-256 hash in the same workspace is rejected with HTTP 409. If an identical asset was archived, reactivate its existing record through PATCH instead of creating a duplicate.

PATCH uses JSON, for example:

```json
{
  "asset_name": "Primary product logo",
  "description": "Approved logo for product pages",
  "is_active": true
}
```

Only supplied fields are updated. `is_active: false` archives the asset; `is_active: true` reactivates it.

### Static image checks

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/workspaces/{workspace_id}/image-checks` | Workspace member | Upload and check a static image |
| GET | `/workspaces/{workspace_id}/image-checks` | Workspace member | List recent image checks |
| GET | `/workspaces/{workspace_id}/image-checks/{image_check_id}` | Workspace member | Retrieve one saved check |
| GET | `/workspaces/{workspace_id}/image-checks/{image_check_id}/file` | Workspace member | Download/preview the submitted image |

`POST image-checks` is `multipart/form-data`:

- `file`: required JPEG, PNG, or WebP image
- `alt_text`: optional, up to 1,000 characters

The endpoint saves the submitted image privately and persists the result. `analysis` contains:

- `asset_match_status`: `exact_match` or `no_exact_match`
- `matched_asset`: the matched approved asset summary, or `null`
- `dominant_colors`: up to five measured colors with percentages
- `alt_text_status`: `provided` or `missing`
- `findings`: human-readable result cards with `code`, `severity`, `title`, `message`, and `recommended_action`
- `limitations`: explicit statements about what this version does not verify

## Detection boundaries

- Asset matching is exact SHA-256 byte-for-byte matching only. Resized, recompressed, cropped, or visually similar images will not match.
- No exact match is a request for review, not proof that an image is unauthorised.
- Dominant colors are measured and reported as metadata. This version does not compare them against a configured brand palette or produce a brand-color compliance score.
- The backend checks whether alt text was supplied. It does not automatically judge whether that text is accurate or useful.
- The backend does not perform OCR, detect text embedded in images, or prove ownership/authenticity.

## Storage security model

The bucket is private. Storage RLS scopes object reads to workspace members. Approved brand-asset uploads are limited to Brand Owners. Image-check uploads are limited to workspace members and are placed under the authenticated user's folder. The backend never exposes a public bucket URL.

## Frontend contract

Griva can use the OpenAPI document generated alongside this update (`openapi-image-assets.json`) to integrate the routes. Image upload forms must use `multipart/form-data`; do not JSON-encode the image bytes.

## Local verification

From the backend directory:

```powershell
uv run python -m pytest
uv run python -m compileall -q app tests
```

The current test suite constructs the Supabase gateway for some invalid-request tests, so local test runs need `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` set in `.env` (the values only need to be syntactically valid for those validation-only tests). Never use a service-role key for this feature.
