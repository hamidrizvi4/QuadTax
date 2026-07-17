"""Pytest session setup.

Sets a test API key so endpoint tests that exercise protected routes
(/submit, /ocr, /packet) succeed without auth failures. The dedicated auth
tests in ``tests/test_api/test_auth.py`` override this via
``unittest.mock.patch.dict`` to exercise the locked-down paths.

Also sets a dummy OPENAI_API_KEY so GET /api/v1/healthz reports healthy by
default across the suite (the check only verifies the env var is non-empty;
it never makes a live call). ``tests/test_api/test_healthz.py`` overrides
this via ``unittest.mock.patch.dict`` to exercise the degraded paths.
"""

import os

import pytest

os.environ.setdefault("QUADTAX_API_KEY", "test-key-not-a-secret")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-a-real-key")


@pytest.fixture(autouse=True)
def _reset_llm_extraction_caches():
    """Clear the module-level LLM extraction caches around every test.

    L1/L3/L4 (src/agents/_llm_cache.py) memoize LLM calls in process-lifetime
    module-level dicts so that a duplicate document upload anywhere in the
    process reuses a prior extraction. Left uncleared, that same
    process-wide scope would let one test's mocked LLM response leak into
    another test that happens to reuse the same placeholder OCR text (e.g.
    "x", "FAKE RECORD") with a different mock, silently masking a call that
    should have happened. Resetting before and after each test keeps the
    suite's tests independent while still exercising the real cache.
    """
    from src.agents.l1_residency import _i94_extraction_cache
    from src.agents.l3_income import _extraction_cache
    from src.agents.l4_treaty import _treaty_classification_cache

    caches = (_i94_extraction_cache, _extraction_cache, _treaty_classification_cache)
    for cache in caches:
        cache.clear()
    yield
    for cache in caches:
        cache.clear()
