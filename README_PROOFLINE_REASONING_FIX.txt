PROOFLINE REASONING-PARAMETER FIX
================================

The prior request set reasoning.enabled=false. The latest OpenRouter response
said the selected provider requires reasoning and rejects disabling it. This
update keeps reasoning enabled at the documented minimal effort level:

    "reasoning": {"effort": "minimal"}

The change is deliberately limited to the AI request payload and its mocked
request assertion. It preserves the existing free router, structured schema,
output token budget, diagnostics, extraction logic, and analysis fallback.

INSTALL
-------
1. Stop Uvicorn (Ctrl+C).
2. From the Proofline project root, back up these files:

   cp backend/app/services/ai/openai_client.py backend/app/services/ai/openai_client.py.pre-minimal-reasoning
   cp backend/tests/test_ai_client.py backend/tests/test_ai_client.py.pre-minimal-reasoning

3. Extract this ZIP into the Proofline project root, preserving paths.
4. From ~/Desktop/Proofline/backend run:

   python -m pytest -q

5. Restart Uvicorn and perform one controlled live extraction. Do not assume
   live provider compatibility from mocked tests alone.

VALIDATION
----------
The isolated uploaded-source backend suite passed 128 tests with 2 existing
Starlette deprecation warnings. No live OpenRouter requests were made during
testing.
