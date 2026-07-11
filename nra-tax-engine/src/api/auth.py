"""API-key authentication for the QuadTax engine.

Every data endpoint requires a ``Bearer`` API key matching ``QUADTAX_API_KEY``.
The server fails closed (HTTP 503) if the key is not configured, so the tax
API never runs unprotected — a system handling SSN/ITIN PII must not be
reachable without authentication.
"""

from __future__ import annotations

import hmac
import logging
import os

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

API_KEY_HEADER_NAME = "Authorization"
_api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)

_API_KEY_ENV = "QUADTAX_API_KEY"

# The literal example value shipped in .env.example. A deployer who copies
# that file to .env and forgets to change this line would otherwise expose
# every SSN/ITIN-bearing endpoint behind a publicly-known "secret".
_PLACEHOLDER_API_KEY = "change-me-to-a-long-random-secret"


def require_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    """Validate the ``Bearer`` API key. Returns the token on success.

    Fails closed:
      * 503 if ``QUADTAX_API_KEY`` is not configured on the server, or is
        still set to the ``.env.example`` placeholder value.
      * 401 if the header is missing or the token is invalid.

    Comparison uses :func:`hmac.compare_digest` (constant-time) to avoid
    timing side-channels.
    """
    expected = os.getenv(_API_KEY_ENV)
    if not expected:
        logger.critical(
            "%s is not set — refusing all authenticated requests.", _API_KEY_ENV
        )
        raise HTTPException(
            status_code=503,
            detail="Service unavailable: authentication not configured.",
        )
    if expected == _PLACEHOLDER_API_KEY:
        logger.critical(
            "%s is still set to the .env.example placeholder value — "
            "refusing all authenticated requests.",
            _API_KEY_ENV,
        )
        raise HTTPException(
            status_code=503,
            detail="Service unavailable: authentication not configured.",
        )
    if not api_key or not api_key.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API key.")
    token = api_key[len("Bearer ") :]
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid API key.")
    return token
