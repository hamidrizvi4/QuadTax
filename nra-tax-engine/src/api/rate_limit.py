"""Shared ``slowapi`` rate limiter for the QuadTax API.

A single module-level :class:`Limiter` is imported by both ``main.py`` and
``ocr_endpoint.py`` so every LLM-calling POST endpoint shares one limiter
instance. This module exists separately from ``main.py`` (rather than
defining the limiter there) purely to avoid a circular import: ``main.py``
imports the OCR router from ``ocr_endpoint.py``, and ``ocr_endpoint.py``
needs the same limiter instance to decorate its own route.

``slowapi``'s built-in exception handler (``_rate_limit_exceeded_handler``)
looks up the limiter via ``request.app.state.limiter``, so ``main.py`` also
assigns this same instance to ``app.state.limiter``.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Keyed by remote address (``request.client.host``). This is the right
# default for this service: it sits behind a single reverse proxy / load
# balancer today, not a multi-hop CDN, so there is no ``X-Forwarded-For``
# chain to parse. If that changes, swap ``get_remote_address`` for a
# proxy-aware key function here (one place) rather than per-route.
limiter = Limiter(key_func=get_remote_address)

# Applied to endpoints that trigger expensive LLM calls (POST /api/v1/submit,
# POST /api/v1/ocr). Bounds per-IP request volume so a single caller cannot
# drive unbounded LLM API cost or DoS the pipeline. GET /api/v1/healthz is
# deliberately never decorated with this — it must stay usable for
# liveness/readiness probes regardless of traffic elsewhere.
LLM_ENDPOINT_RATE_LIMIT = "20/minute"
