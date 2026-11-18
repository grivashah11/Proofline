# Proofline Round 3 — Source Documents API

This API is the backend contract for Improvement 1. All routes require a valid Supabase bearer token and workspace membership. Upload and Claim Passport version creation require the `brand_owner` role. Creators and other workspace members can inspect and download registered source material.

## Upload a source document

`POST /api/v1/workspaces/{workspace_id}/source-documents`

Content type: `multipart/form-data`

Fields:
- `file` — PDF or DOCX, maximum 15 MB.
- `title` — optional display title, maximum 300 characters.

The API validates the extension, declared MIME type and file contents; calculates SHA-256; extracts selectable text; stores the original in the private `proofline-source-documents` bucket; and atomically registers the document and extracted segments. Exact duplicate files within the same workspace return `409`.

PDF segments refer to individual PDF page numbers. DOCX segments refer to heading paths, paragraph numbers or table rows. Page numbers are not inferred for DOCX files. Image-only/scanned PDFs are rejected with an explanation because OCR is not part of this implementation.

The response includes `id`, `title`, `original_filename`, `mime_type`, `document_format`, `file_size_bytes`, `sha256_hash`, `page_count`, `segment_count` and `extraction_warnings`.

## Inspect source documents

- `GET /api/v1/workspaces/{workspace_id}/source-documents`
- `GET /api/v1/workspaces/{workspace_id}/source-documents/{document_id}`
- `GET /api/v1/workspaces/{workspace_id}/source-documents/{document_id}/segments?limit=50&offset=0`
- `GET /api/v1/workspaces/{workspace_id}/source-documents/{document_id}/file`

The segments endpoint returns the extracted passage, `location_type`, `location_label`, `page_number` where applicable, `section_path`, `paragraph_number` and SHA-256 for each passage. The file endpoint returns the original file as a private attachment with `X-Content-Type-Options: nosniff`.

## Create a document-backed Claim Passport version

`POST /api/v1/workspaces/{workspace_id}/claim-passports/{passport_id}/versions`

The existing Passport version payload remains supported. To link an excerpt from an uploaded source document, add all three fields:

```json
{
  "source_document_id": "<source-document-uuid>",
  "source_document_segment_id": "<source-segment-uuid>",
  "source_excerpt": "The exact excerpt selected from that extracted segment."
}
```

The three fields must be supplied together. The database RPC verifies that the document and segment belong to the same workspace and that the excerpt is an exact substring of the selected segment. It then creates the draft Passport version and provenance link in one transaction. The source title, location reference, excerpt and source SHA-256 are copied into the Passport version as evidence fields. A source link can be inspected with:

`GET /api/v1/workspaces/{workspace_id}/claim-passports/{passport_id}/versions/{version_id}/sources`

The new version remains a draft. It is not approved or activated by upload or extraction. The existing Brand Owner verification/activation workflow remains mandatory.

## Re-verification and expiry reminders

`GET /api/v1/workspaces/{workspace_id}/claim-passports/reverification-reminders?within_days=30`

Brand Owners receive active Passport versions whose `review_by` or `valid_until` date falls within the requested window (0–365 days), including overdue and expired records. The API reports `due_soon`, `overdue` or `expired` and the number of days until the earliest action date. It does not silently alter the Passport or activate a replacement version.

## Security and data handling

- Source-document storage is private and separate from the existing image bucket.
- Only Brand Owners can upload source documents.
- Workspace members can read document metadata, extracted passages and originals.
- Source metadata and extracted segments have no direct authenticated insert/update/delete grants; registration is performed through a permission-checked RPC.
- Registered source objects cannot be deleted through the authenticated Storage API; the narrow delete policy only permits rollback of an object that has no registered document row.
- Passport source links are immutable and retain title, location and hash snapshots.
- The document-backed version RPC creates drafts only. Human source verification remains mandatory.
- This feature does not invoke OpenRouter.
