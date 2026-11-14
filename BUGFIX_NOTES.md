# Proofline Round 2 bug-fix patch

This is an additive overlay for the existing Proofline repository. It contains complete replacement files only; it does not include or replace `.env`, `.env.local`, Supabase credentials, dependency folders, migrations, authentication code, RLS policies, or visual redesign files.

## Fixes included

1. **Claim Passport subject matching**
   - Allows an extracted subject with a trailing parenthesized model year (for example, `(2025)`) to match the same subject when the Passport subject omits that suffix.
   - Checks explicit model years in the claim text/product scope against the Passport subject/version/product scope. A detected conflicting year remains `needs_verification`.
   - Does not use broad fuzzy/semantic subject matching.

2. **Channel and market scope**
   - Treats `All`, `Any`, `*`, `All channels`, `Any channel`, `All markets`, and `Any market` as unrestricted scope values.
   - Specific scopes still require the supplied submission context to match.

3. **Numeric conflict detection**
   - Preserves deterministic numeric comparison: if the active Passport permits 18 hours and the draft states 30 hours, the result is `conflict` once the claim matches the Passport.
   - If the model omits `numeric_value` but `value_text` contains exactly one unambiguous number, the matcher can compare that value. It does not parse ambiguous numbers from the full sentence.

4. **Condition extraction and comparison**
   - Extraction instructions now tell the model to associate nearby, clearly relevant test conditions/disclaimers with a claim while keeping `exact_text` limited to the claim itself.
   - Conditions are requested verbatim, not paraphrased.
   - Comparison tolerates punctuation/separator differences but requires every configured condition clause to be present. Missing or incomplete conditions remain `needs_verification`.
   - `ExtractedClaim.conditions` is raised to 3000 characters to match the Claim Passport condition limit and the OpenAPI snapshots.

5. **Consistent claim classification**
   - Extraction instructions distinguish objective product specifications from marketing context. Measurable/testable specifications are classified as factual even when they appear in promotional copy.

6. **Terminology form validation**
   - The UI now labels the replacement field as required when term type is Restricted, sets the browser `required` attribute, and provides a clear inline validation message before submitting.
   - Preferred and Required terminology entries continue to treat replacement as optional. The backend's existing validation/security invariant is preserved.

7. **Test isolation**
   - Invalid claim-extraction request tests now override Supabase/AI dependencies, so request-schema validation tests do not require real local credentials or external services.

## Files to overlay

- `backend/app/services/claim_matcher.py`
- `backend/app/services/ai/openai_client.py`
- `backend/app/schemas/claim_extraction.py`
- `backend/tests/test_claim_matcher.py`
- `backend/tests/test_ai_client.py`
- `backend/tests/test_claim_extraction.py`
- `backend/openapi-round2-final.json`
- `backend/openapi-image-assets.json`
- `frontend/src/features/BrandKnowledgePage.tsx`

No Supabase migration is required for this patch.

## Validation performed

- Backend `python -m compileall -q app tests`: passed.
- Backend `python -m pytest -q`: **115 passed**, 2 deprecation warnings.
- Modified `BrandKnowledgePage.tsx` TypeScript/JSX transpilation syntax check: passed.
- Full frontend `npm run lint` / `npm run build`: not completed in the patch environment because `npm ci` could not complete (the offline cache lacked a package and the online install timed out). Run both from the local `frontend` folder after applying the patch.

## Important boundaries

- Claim matching remains conservative and deterministic. It tolerates a trailing model-year suffix, but it does not implement general semantic product matching.
- A claim is not marked supported if the Passport requires conditions that the extractor does not identify in full.
- `needs_verification` is the safe outcome for missing/ambiguous evidence; it is not treated as a pass.
- Human review and revision-specific approval remain required.
