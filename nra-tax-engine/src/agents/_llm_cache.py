"""In-process cache for deterministic LLM/OCR extraction calls.

Every layer that calls out to an LLM to parse raw OCR/free-text input (L1
I-94 day counts, L3 W-2/1042-S/1099 box values, L4 treaty-category
classification) routes through :func:`src.agents._llm_safety.safe_parse`,
which is pinned to ``temperature=0.0``. For a fixed set of inputs the call
is therefore deterministic, so re-running the extraction against the exact
same document text (plus any other parameter that affects the result, e.g.
``tax_year``) is pure wasted LLM/OCR cost -- most commonly triggered by a
filer re-uploading the same document (browser retry, "start over" flow,
etc.).

This module provides a tiny dict-based memo, keyed on a SHA-256 hash of the
call's deterministic inputs, that each call site can wrap its
``safe_parse`` invocation with. It is intentionally simple:

    * In-process only -- state lives in a plain Python dict for the
      lifetime of the process. It is NOT shared across worker processes and
      does NOT survive a restart.
    * No eviction/TTL -- fine for a single-process dev/early-stage
      deployment; a long-lived high-traffic process would want bounding.

The natural upgrade path for a multi-process/production deployment (e.g.
several uvicorn/gunicorn workers behind a load balancer) is a shared,
out-of-process cache such as Redis, keyed the same way (SHA-256 of the
deterministic inputs) so a cache hit in one worker is visible to the
others. That is intentionally out of scope here.
"""

from __future__ import annotations

import hashlib
import threading
from typing import Any, Callable, Dict, TypeVar

T = TypeVar("T")

_SEP = b"\x00"


class LLMExtractionCache:
    """A small dict-based memo scoped to a single LLM call site.

    Callers should create one module-level instance per distinct call site
    (e.g. one for I-94 extraction, one for W-2/1042-S/1099 extraction, one
    for treaty classification) rather than sharing a single instance across
    semantically different calls -- that keeps a hash collision between two
    unrelated call sites from ever being possible, even if the raw text
    inputs happened to coincide.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}
        self._lock = threading.Lock()

    @staticmethod
    def make_key(*parts: Any) -> str:
        """Hash ``parts`` (order- and value-sensitive) into one SHA-256 hex digest.

        Each part is stringified and separated by a NUL byte so that, e.g.,
        ``("ab", "c")`` and ``("a", "bc")`` never collide.
        """
        digest = hashlib.sha256()
        for part in parts:
            digest.update(str(part).encode("utf-8"))
            digest.update(_SEP)
        return digest.hexdigest()

    def get_or_call(self, key: str, compute: Callable[[], T]) -> T:
        """Return the cached value for ``key``, computing it via ``compute`` on a miss.

        ``compute`` runs outside the lock so a slow LLM call never blocks
        other lookups; a rare duplicate in-flight call under a race is an
        acceptable trade-off for a single-process dev/early-stage
        deployment (see module docstring for the Redis upgrade path that
        would remove this caveat).
        """
        with self._lock:
            if key in self._store:
                return self._store[key]
        value = compute()
        with self._lock:
            self._store[key] = value
        return value

    def clear(self) -> None:
        """Drop every cached entry. Primarily useful for test isolation."""
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
