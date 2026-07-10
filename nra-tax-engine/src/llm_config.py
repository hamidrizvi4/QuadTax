"""Shared OpenAI-compatible client construction for the engine's LLM call sites.

Defaults reproduce today's behavior exactly (plain OpenAI() against
api.openai.com with the gpt-4o-2024-08-06 / gpt-4o-mini model pair). Setting
OPENAI_BASE_URL, OPENAI_PRIMARY_MODEL, and/or OPENAI_SECONDARY_MODEL routes
calls through an alternate OpenAI-API-compatible provider (e.g. OpenRouter at
https://openrouter.ai/api/v1, which requires vendor-prefixed model ids like
"openai/gpt-4o").
"""

from __future__ import annotations

import os
from typing import Any


def get_openai_client() -> Any:
    # Imported lazily (rather than at module load) so tests can patch
    # openai.OpenAI and so constructing this module never requires an API
    # key until a client is actually built.
    from openai import OpenAI

    base_url = os.getenv("OPENAI_BASE_URL")
    return OpenAI(base_url=base_url) if base_url else OpenAI()


PRIMARY_MODEL = os.getenv("OPENAI_PRIMARY_MODEL", "gpt-4o-2024-08-06")
SECONDARY_MODEL = os.getenv("OPENAI_SECONDARY_MODEL", "gpt-4o-mini")
