# Proofline frontend integration

This package updates the existing `frontend/` source. It does not include `node_modules`, build output, or environment files.

## Implemented

- Replaced the Content Reviews placeholder with a real API-backed workflow:
  - create and list submissions
  - save immutable revisions
  - analyse the current revision
  - show deterministic and Claim Passport findings, source excerpts and evidence links
  - submit the analysed revision for review
  - show comments and decision history
- Replaced the Review Queue placeholder with a Brand Owner review workflow:
  - load items awaiting review
  - inspect the exact submitted revision and its matching analysis
  - view findings, evidence, comments and activity history
  - add revision-scoped comments
  - record approve / changes requested / reject decisions
- Added a Team Members screen:
  - show the current account UUID
  - add an already registered account as a Creator using the backend's UUID-based membership endpoint
  - list workspace members and remove a member
- Added a Creator onboarding path for accounts with no workspace yet:
  - copy the new account UUID
  - ask the Brand Owner to add the account
  - refresh workspace access without creating a second workspace
- Updated the dashboard's recent submissions panel to load actual content records.

## API contract used

The screens use the request and response schemas in the supplied OpenAPI document. In particular:

- `POST /contents` uses `ContentCreate`.
- `POST /contents/{content_id}/revisions` uses `{ "content_text": "..." }`.
- `POST /contents/{content_id}/analyses` has no request body.
- `POST /contents/{content_id}/submit-for-review` has no request body.
- `POST /contents/{content_id}/revisions/{revision_id}/comments` uses `{ "body": "..." }`.
- `POST /contents/{content_id}/reviews` uses `{ "decision": "approved | changes_requested | rejected", "reviewer_comment": "..." }`.
- `POST /members` uses `{ "user_id": "<registered user UUID>", "role": "creator" }`.

## Remaining backend dependency

The supplied OpenAPI contract does not expose an approved-asset registration, image upload, or image-analysis endpoint. The Round 2 static-image check therefore remains pending backend support. This package does not fake that feature in the browser.

## Validation performed in the packaging environment

- TypeScript/TSX syntax transpilation passed for all changed TS/TSX files.
- Strict type-check of the new content, review, team components and API types passed using temporary external-module declarations because this packaging environment could not download the npm dependencies.
- CSS parsing passed for the changed stylesheets.
- A full `npm run lint` and `npm run build` has **not** been run against the real installed package dependencies in this environment.

## Final local checks

From the project root, enter `frontend/` and run:

```bash
npm run lint
npm run build
```

Keep the existing `.env.local` in place. No environment values are required to change for these frontend additions.
