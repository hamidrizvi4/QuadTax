# NRA Tax Engine

A hybrid tax preparation engine built for **Nonresident Alien (F-1/J-1) international students**.

## Architecture

This system uses a **Hybrid Execution Architecture** with a strict firewall between two zones, managed by a Governing Orchestrator:

| Zone | Directory | Purpose | Rules |
|------|-----------|---------|-------|
| **Reasoning Zone** | `src/agents/` | LLM-powered classification, ambiguity resolution, edge-case handling | May call LLMs via `anthropic` / `openai` SDKs |
| **Deterministic Zone** | `src/functions/` | Pure math, lookups, bracket calculations | **NO LLM calls allowed** — only pure Python |
| **Orchestrator** | `src/orchestrator/` | Manages the mutable `ReturnStateObject`, enforces execution order | Controls which zone handles each step |

### Execution Flow

```
Intake (OCR / MCQ)
    ↓
Orchestrator (engine.py)
    ├── L1: Residency Agent  →  SPT Calculator (deterministic)
    ├── L3: Income Agent     →  Code Mapper (deterministic)
    ├── L6: Tax Calc Agent   →  Tax Math (deterministic)
    └── L8: FICA Agent       →  FICA Math (deterministic)
    ↓
Assembly (form_populator.py)
    ↓
1040-NR / IT-203 Output
```

## Quick Start

```bash
# 1. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 4. Run tests
pytest
```

## Required Environment Variables

**CRITICAL: These must be set before starting the engine**

```
QUADTAX_API_KEY=sk-...        # REQUIRED for engine authentication (see .env.example)
OPENAI_API_KEY=sk-...          # REQUIRED for OCR/classification (https://platform.openai.com/api-keys)
```

These are injected at container startup via `startup_helper.sh` (see below).

## Project Structure

```
src/
├── intake/          # Mobile OCR and MCQ processing
├── agents/          # Reasoning Zone — LLM wrappers
├── functions/       # Deterministic Zone — Pure Python math
├── database/        # Hardcoded JSON lookups (treaties, brackets)
├── orchestrator/    # Governing engine + Pydantic state
└── assembly/        # Final form population (1040-NR, IT-203)
```

## Tech Stack

- **Python 3.11+**
- **Pydantic** — Strictly typed mutable state
- **Anthropic / OpenAI** — Reasoning agents
- **Pytest** — Deterministic math coverage
- **Black + Ruff** — Code formatting & linting

## Startup Helper (for production containers)

```bash
# startup_helper.sh
#!/usr/bin/env bash
set -euo pipefail

# Validates required env vars and injects them
if [[ -z "${QUADTAX_API_KEY:-}" ]]; then
    echo "ERROR: QUADTAX_API_KEY is not set"
    exit 1
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: OPENAI_API_KEY is not set"
    exit 1
fi

# Start the engine
exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

## Security & Compliance Features

### 🔒 Security Hardening

1. **API Key Validation**
   - Server fails closed if `QUADTAX_API_KEY` is missing
   - Environment validation at startup prevents unsecured operation
   - API key verification uses constant-time comparison to prevent timing attacks

2. **Rate Limiting**
   - `/api/submit` endpoint limited to 30 requests/minute per IP
   - Protection against DoS attacks and cost explosion

3. **Path Traversal Protection**
   - `/api/v1/packet` endpoint uses `os.path.commonpath` for secure file access
   - Prevents directory traversal attacks (e.g., `../../../etc/passwd`)

4. **Security Headers**
   - All responses include:
     - `X-Content-Type-Options: nosniff`
     - `X-Frame-Options: DENY`
     - `Referrer-Policy: no-referrer`
     - `Permissions-Policy: geolocation=(), microphone=(), camera=()`

### 📋 Compliance Features

1. **Audit Trail**
   - Complete decision trace stored in `ReturnStateObject.audit_trail`
   - Includes inputs/outputs hashes, rationale, and timestamps
   - Enables "Why this number?" UI and IRS-notice response workflow

2. **Human Review Gates**
   - Automatic detection of edge cases requiring CPA review
   - Engine refuses assembly until reviewer acknowledges each flag
   - Explicit audit entry for each review requirement

3. **Data Retention**
   - Files automatically purged after 30 days (configurable)
   - Secure deletion of temporary files

4. **GDPR/CCPA Support**
   - `/api/v1/erase-user` endpoint for data subject requests
   - All PII flows through encrypted channels only

## Known Limitations

- IRS PDF templates are not vendored (see docs/templates/README.md)
- Landing-page testimonials are illustrative personas from verified test cases