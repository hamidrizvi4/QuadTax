"""Pytest session setup.

Sets a test API key so endpoint tests that exercise protected routes
(/submit, /ocr, /packet) succeed without auth failures. The dedicated auth
tests in ``tests/test_api/test_auth.py`` override this via
``unittest.mock.patch.dict`` to exercise the locked-down paths.
"""

import os

os.environ.setdefault("QUADTAX_API_KEY", "test-key-not-a-secret")
