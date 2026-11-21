PROOFLINE AI SCHEMA-ALIGNMENT HOTFIX
===================================

WHY THIS UPDATE EXISTS
----------------------
The latest runtime log shows that OpenRouter selected a free model and
returned a response, but Pydantic rejected the generated claims. The current
log only said `error_type=ValidationError`; it did not identify the failing
field.

This update makes two targeted changes:

1. The provider JSON Schema now mirrors the application model's relevant
   constraints: claim count, string lengths, and the decimal-only pattern for
   numeric_value. This reduces avoidable mismatches between provider output
   and Pydantic validation.
2. Pydantic failures now log only safe field paths and error types, e.g.
   `claims.0.numeric_value:value_error`. It does not log the submitted draft,
   generated claim text, API key, or rejected input values.

It preserves the current OpenRouter free router, Responses API request,
reasoning-disabled setting, 8192 output-token setting, extraction instructions,
claim schema fields, and graceful partial-analysis handling.

FILES
-----
backend/app/services/ai/openai_client.py
backend/tests/test_ai_client.py

INSTALL
-------
1. Stop Uvicorn with Ctrl+C.
2. From the Proofline project root, back up the two files:

   cp backend/app/services/ai/openai_client.py backend/app/services/ai/openai_client.py.pre-schema-hotfix
   cp backend/tests/test_ai_client.py backend/tests/test_ai_client.py.pre-schema-hotfix

3. Extract this ZIP into the Proofline project root, preserving paths.
4. From backend, run:

   python -m pytest -q

The included isolated-source suite passed 128 tests with two existing
deprecation warnings. These tests mock OpenRouter; they do not guarantee an
external free provider will always return schema-valid responses.

5. Restart Uvicorn and run the test draft once. Check the backend log for
   `validation_issues=` if a provider response still fails application
   validation. The field path will identify the specific mismatch without
   exposing content.
