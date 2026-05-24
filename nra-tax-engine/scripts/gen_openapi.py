#!/usr/bin/env python3
"""Dump the FastAPI OpenAPI spec to ``nra-tax-client/openapi.json``.

The client then runs ``openapi-typescript openapi.json -o src/lib/api-types.ts``
in its prebuild step to generate TypeScript types matching the engine's
Pydantic models. This eliminates hand-rolled-interface drift.

Usage::

    python -m scripts.gen_openapi [--out PATH]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.api.main import app

DEFAULT_OUT = (
    Path(__file__).resolve().parent.parent.parent / "nra-tax-client" / "openapi.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    spec = app.openapi()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"Wrote OpenAPI spec to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
