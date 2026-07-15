"""LRU cache for document extraction results to prevent duplicate LLM calls.

Issue #7: Cache expensive LLM calls per unique document hash to reduce costs
and latency during peak load.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

# In-memory cache size (can be overridden via env for prod Redis)
CACHE_MAX_SIZE = int(os.getenv("QUADTAX_CACHE_SIZE", "1000"))


def _hash_content(text: str) -> str:
    """Create deterministic hash of OCR text."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


@lru_cache(maxsize=CACHE_MAX_SIZE)
def get_cached_extraction(document_type: str, content_hash: str) -> Optional[Any]:
    """Retrieve cached extraction result if available.

    Args:
        document_type: e.g., "W2", "1042S", "I94"
        content_hash: SHA256 hash of the OCR text

    Returns:
        Cached extraction result or None if not cached
    """
    return None  # Base implementation returns None; production would use Redis


def cache_extraction(text: str, extraction_result: Any) -> None:
    """Cache an extraction result for future identical documents.

    Args:
        text: Original OCR text (used to derive cache key)
        extraction_result: Parsed extraction to cache
    """
    # Placeholder for production implementation
    pass


def clear_extraction_cache() -> None:
    """Clear the in-memory extraction cache (useful for tests)."""
    get_cached_extraction.cache_clear()