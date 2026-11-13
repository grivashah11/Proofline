# Manual claims and tone examples API notes

## Manual claim addition

`POST /api/v1/workspaces/{workspace_id}/contents/{content_id}/analyses/{analysis_id}/manual-claims`

- Authenticated workspace member; content must be in `draft` or `changes_requested`.
- The analysis must belong to the current content revision.
- `exact_text` must be a verbatim contiguous excerpt from that revision.
- Required: `exact_text`, `subject`, `attribute`, `claim_kind` (`factual` or `promotional`).
- Optional: `value_text`, `numeric_value`, `unit`, `qualifier`, `conditions`, `product_scope`, `channel_scope`, `market_scope`.
- Returns the updated `AnalysisDetail`.
- The newly-added finding is always `needs_verification`, with a warning severity and a human-verification next step. This ensures manually entering a claim does not silently establish factual support.
- Duplicate entries for the same exact text, subject and attribute in the same analysis are rejected with HTTP 409.

Example request:

```json
{
  "exact_text": "Our bottle keeps drinks cold for 24 hours.",
  "subject": "Our bottle",
  "attribute": "cold retention",
  "claim_kind": "factual",
  "numeric_value": "24",
  "unit": "hours"
}
```

## Tone examples

Brand Rule create/update/record models now expose `tone_examples` (maximum 5,000 characters). A new `brand_voice` rule requires at least one example. Manual-review findings include the stored examples for the reviewer. These are examples for human judgement; the MVP does not compute an automatic tone score.
