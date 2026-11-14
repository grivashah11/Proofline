PROOFLINE RELIABILITY UPDATE
=============================

This update contains four complete replacement files:

1. backend/app/services/ai/openai_client.py
2. backend/tests/test_ai_client.py
3. backend/app/api/v1/endpoints/analyses.py
4. backend/tests/test_analyses.py

WHAT CHANGES
------------

AI request reliability
- Explicitly disables model reasoning for the claim-extraction request.
- Sets max_output_tokens to 8192 for the currently selected free model's
  documented output capacity.
- Logs response status, incomplete reason, output-token count and reasoning
  tokens without logging the submitted draft, generated claim text or API key.

Analysis graceful degradation
- AI HTTP errors including 422, 429, 502 and 503 no longer discard the whole
  content analysis.
- Unexpected exceptions inside the AI extraction call are logged by exception
  type and the run is saved as PARTIAL.
- Deterministic terminology and brand-rule checks are still saved.
- Claim matching remains outside the provider exception handler, so a bug in
  deterministic matching is not hidden as an AI outage.
- The existing frontend already displays the PARTIAL state, an AI-unavailable
  warning and the manual-claim panel; no frontend replacement is required.

Persistent extraction cache
- A successful AI extraction is cached in the existing analysis_runs and
  analysis_findings records; no database migration or new table is required.
- Cache identity is scoped to workspace, content, immutable revision, requested
  model route and extraction profile version.
- Repeated analysis runs on the same revision reuse candidate claims from the
  database, then rerun deterministic rules and Passport matching using the
  current workspace data.
- A new revision causes a fresh AI extraction.
- Manually added claims are not mistaken for provider-generated cached claims.
- A failed cache read falls back to a live AI request.
- If extraction instructions or the JSON schema change, increment
  AI_EXTRACTION_CACHE_VERSION in analyses.py to invalidate old cached results.

IMPORTANT LIMITATION
--------------------

No application can guarantee that an external free AI provider is always
available. Free-model services can be rate-limited or temporarily unavailable.
This update makes the content-analysis endpoint fail safely: it persists a
PARTIAL analysis with deterministic checks and tells the user AI extraction
was unavailable, instead of returning a generic analysis failure. It does not
claim that missing AI findings are successful verification.

TEST VALIDATION
---------------

The four files above were installed in an isolated copy of the uploaded source
tree and the full backend test suite completed with:

    126 passed, 2 deprecation warnings

The tests use mocked provider responses; they do not make real OpenRouter
requests. Run the test suite in your own environment before deployment.

INSTALLATION
------------

From the Proofline project root:

1. Back up the four current files.
2. Extract this ZIP into the project root, preserving folder paths.
3. Run from the backend directory:

    python -m pytest -q

4. Restart the backend and test the content-review flow.

The OPENROUTER_MODEL setting remains openrouter/free. No paid model or paid
fallback is added.
