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
