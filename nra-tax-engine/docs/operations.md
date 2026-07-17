# Operations & Deployment

This document covers running `nra-tax-engine` in production: required
configuration, secret handling, process supervision, logging/audit
persistence, output retention, TLS, and deploy mechanics. It describes only
what actually exists in this repo today — see `src/api/main.py`,
`src/api/auth.py`, `src/orchestrator/audit.py`, and `.env.example` as the
source of truth if this doc and the code ever disagree.

For local development setup, see the README's "Getting Started" section.
This document is the production-facing counterpart.

---

## 1. Required environment variables

All configuration is read from the process environment (typically via a
`.env` file loaded by whatever process manager starts the app — the engine
itself does not load `.env` automatically at import time, so make sure your
process supervisor or shell sources it before `uvicorn`/`gunicorn` starts).

| Variable | Required? | Purpose | Fail-closed behavior when missing/placeholder |
|---|---|---|---|
| `QUADTAX_API_KEY` | **Required in production** | Bearer token protecting every data endpoint (`/api/v1/submit`, `/api/v1/ocr`, `/api/v1/packet`, `/api/v1/erasure`). Checked in `src/api/auth.py::require_api_key`. | If unset, **or still equal to the literal `.env.example` placeholder value `change-me-to-a-long-random-secret`**, every authenticated request gets **HTTP 503** ("Service unavailable: authentication not configured"), not a 401. This is deliberate fail-closed behavior — a system handling SSN/ITIN PII must never run reachable-but-unauthenticated because someone forgot to change the example value. |
| `OPENAI_API_KEY` | Required for OCR/LLM-classification features only | Powers document OCR extraction (`src/intake/document_extractor.py`) and treaty income-category classification (`src/agents/l4_treaty.py`). Read directly by the `openai` SDK inside `src/llm_config.py::get_openai_client()`. | Not fail-closed at the API-auth layer — the server starts and most of the deterministic pipeline (L1, L3 non-LLM paths, L6–L9, form assembly) still works. `GET /api/v1/healthz` reports `llm_api_key_configured: false` so you can see the gap without triggering a live LLM call. If unset, the "Scan All Documents" OCR endpoint and LLM-driven treaty classification will fail at call time. |
| `ANTHROPIC_API_KEY` | Conditionally required | Used when `LLM_PROVIDER=anthropic` (see below) for reasoning agents. | Same class of failure as `OPENAI_API_KEY` — fails at the specific call site, not at startup. |
| `LLM_PROVIDER` | Optional (default in `.env.example`: `anthropic`) | Selects which provider's key/model the reasoning agents use (`anthropic` or `openai`). | N/A — just picks which of the above two keys is load-bearing. |
| `ANTHROPIC_MODEL` / `OPENAI_MODEL` | Optional | Model identifiers for the selected provider. | Defaults are set in `.env.example`; not fail-closed. |
| `OPENAI_BASE_URL` | Optional | Routes OpenAI-SDK calls (OCR + classification) through an alternate OpenAI-API-compatible provider (e.g. OpenRouter) instead of `api.openai.com`. Read in `src/llm_config.py`. | Unset = default OpenAI endpoint. |
| `OPENAI_PRIMARY_MODEL` / `OPENAI_SECONDARY_MODEL` | Optional | Override the `gpt-4o-2024-08-06` / `gpt-4o-mini` model pair used for structured-output calls (`src/llm_config.py`). Note: when pointing at OpenRouter, ids must be vendor-prefixed (e.g. `openai/gpt-4o`). | Defaults hardcoded in `llm_config.py`. |
| `QUADTAX_DUAL_EXTRACT` | Optional | Set to `true` to enable a second-model cross-check of numeric OCR fields; a mismatch routes the filing into the human-review gate instead of silently trusting one extraction. See `src/agents/_llm_safety.py`. | Unset = single-extraction path only. |
| `QUADTAX_CORS_ORIGINS` | Optional (default: `http://localhost:3000,http://127.0.0.1:3000`) | Comma-separated list of allowed CORS origins, read in `src/api/main.py`. **Must be pinned to your real frontend origin(s) in production** — the localhost defaults are dev-only and won't match a deployed frontend. | N/A — CORS just rejects browser requests from unlisted origins; it doesn't fail closed at startup. |
| `QUADTAX_AUDIT_DIR` | Optional | Directory root for persisted JSONL audit trails. See §4 below. | Unset = audit entries stay in-memory on `state.audit_trail` only, nothing written to disk. |
| `LOG_LEVEL` | Optional (default `INFO` in `.env.example`) | Not currently read by any code path found in `src/` — treat as reserved/aspirational until wired up, or set it via your process manager's own log-level flag instead. | N/A |

**Fail-closed summary:** the only variable this API actively fails closed on
is `QUADTAX_API_KEY`. A missing or placeholder value takes down every
authenticated endpoint with a 503, on every request, not just at startup —
so a bad deploy is immediately visible rather than silently insecure.
Everything else (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) fails at the point of
use, and `GET /api/v1/healthz` surfaces the gap proactively via
`checks.api_key_configured` / `checks.llm_api_key_configured` so you can
catch a missing key before a user hits it.

### Pre-deploy checklist

Before pointing real traffic at a deployment, confirm:

```bash
curl -s https://your-deployment/api/v1/healthz | python3 -m json.tool
```

returns `"status": "ok"` with every check `true`. A `503` with
`"status": "degraded"` means at least one of `api_key_configured`,
`llm_api_key_configured`, or `templates_present` is false — the response
body tells you which.

---

## 2. Secret management

- **Never commit `.env`.** `nra-tax-engine/.env.example` is the template;
  copy it to `.env` locally and to your platform's secret store
  (environment variables in your hosting provider's dashboard, a secrets
  manager, CI secrets, etc.) in production. Verify `.env` is in
  `.gitignore` before your first commit in any fork/clone.
- **Rotate `QUADTAX_API_KEY` before any real deployment.** The value
  shipped in `.env.example` (`change-me-to-a-long-random-secret`) is
  intentionally recognized and rejected by `src/api/auth.py` — the server
  will not serve authenticated traffic with that value. Generate a real
  secret, e.g.:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
  Treat this as a normal API credential: unique per environment (dev/
  staging/prod should not share one), rotated on suspected compromise or
  personnel changes, and never logged (the comparison in `auth.py` uses
  `hmac.compare_digest` and only logs that the check failed, never the
  submitted value).
- **The frontend must never hold this key client-side.** Per the README's
  auth note, the Next.js client only talks to same-origin proxy routes
  (`/api/submit`, `/api/ocr`, `/api/packet`) that hold `QUADTAX_API_KEY`
  server-side (as a non-`NEXT_PUBLIC_` env var). Confirm this convention
  is preserved in any new client route before shipping it.
- **LLM provider keys** (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) are
  standard vendor credentials — scope them with spend limits on the
  provider side where available, since a leaked key on a rate-limited but
  publicly reachable `/submit` endpoint is a cost-abuse vector even though
  `LLM_ENDPOINT_RATE_LIMIT` (20/minute per IP, see `src/api/rate_limit.py`)
  bounds it somewhat.
- **The audit trail can contain sensitive filing data.** `QUADTAX_AUDIT_DIR`
  (§4) writes JSONL to disk with SSN/ITIN/bank-detail fields redacted but
  other filing details (income amounts, treaty articles, names) present in
  plaintext previews. Restrict filesystem permissions on that directory the
  same way you would any directory holding tax PII, and include it in your
  backup/retention and access-control planning, not just your deploy
  scripts.

---

## 3. Production process: running the ASGI app

The entrypoint is the FastAPI instance `app` in `src/api/main.py`, i.e.
**`src.api.main:app`**, run from the `nra-tax-engine/` directory (module
resolution depends on `src` being importable from cwd, matching how the
dev command and test suite already invoke it).

Development uses `uvicorn --reload`, which is single-process and
unsuitable for production. For production, run without `--reload` and with
multiple workers:

**Option A — uvicorn with multiple worker processes:**
```bash
cd nra-tax-engine
uvicorn src.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4
```

**Option B — gunicorn managing uvicorn workers (more production process
control: graceful worker restarts, PID file, logging config):**
```bash
cd nra-tax-engine
pip install gunicorn   # not currently in pyproject.toml — add it before using this path
gunicorn src.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

Pick a worker count proportionate to available CPU cores (a common starting
point is `2 * cores + 1`); this is a single FastAPI service with no shared
in-process state across the endpoints that matters for correctness (rate
limiting is per-IP via `slowapi` and does not require cross-worker
coordination for this app's traffic scale), so scaling workers horizontally
is safe.

Run under a process supervisor (systemd unit, Docker `restart: unless-stopped`,
or your platform's process manager) so a crashed worker is restarted
automatically. A minimal systemd unit:

```ini
[Unit]
Description=QuadTax NRA Tax Engine API
After=network.target

[Service]
WorkingDirectory=/opt/quadtax/nra-tax-engine
EnvironmentFile=/opt/quadtax/nra-tax-engine/.env
ExecStart=/opt/quadtax/nra-tax-engine/.venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 4. Log rotation / audit trail

The engine's audit mechanism (`src/orchestrator/audit.py::record`) is
distinct from ordinary application logs:

- Every state-mutating pipeline step appends a structured entry (layer,
  function, input/output hashes, a plain-English rationale, and small
  redacted previews) to `state.audit_trail` in memory. This always happens,
  regardless of configuration, and is what powers the "Why this number?"
  narrative and the human-review gate.
- **If and only if `QUADTAX_AUDIT_DIR` is set**, each entry is *additionally*
  persisted as one JSON line appended to
  `<QUADTAX_AUDIT_DIR>/<filing_id or "default">/audit.jsonl`. The directory
  is created on demand (`Path.mkdir(parents=True, exist_ok=True)`), and a
  write failure is logged as a warning rather than raised (it never breaks
  the request).
- **Known gap:** `POST /api/v1/submit` never assigns a `filing_id` today, so
  in the current HTTP API every submission's persisted audit entries land in
  the shared file `<QUADTAX_AUDIT_DIR>/default/audit.jsonl` — there's no
  per-filer separation unless a caller drives `TaxEngine`/
  `ReturnStateObject` directly and sets `filing_id` itself. Keep this in
  mind before relying on `QUADTAX_AUDIT_DIR` for per-filer audit isolation
  or GDPR erasure by `filing_id` in a multi-tenant deployment — see the
  `POST /api/v1/erasure` docstring in `src/api/main.py` for the same
  caveat from the erasure side.
- **PII redaction:** fields like SSN, ITIN, passport number, and bank/routing
  numbers are replaced with `"[REDACTED]"` in the human-readable preview
  before it's written (`_PII_KEYS` in `audit.py`), though the full values
  are still hashed (SHA-256, truncated) for tamper-detection. Treat
  `audit.jsonl` files as sensitive regardless — other filing details are
  not redacted.
- **This module does not rotate or cap file size itself** — it only appends.
  If you set `QUADTAX_AUDIT_DIR` in production, put it under your platform's
  log rotation (`logrotate` on a VM, your log-shipping sidecar's rotation
  policy in a container platform, etc.) or point it at a volume you monitor
  for growth. There is no built-in cap.
- **Ordinary application logs** (the `logging` module calls scattered through
  `src/`, e.g. the `logger.critical`/`logger.exception` calls in
  `auth.py`/`main.py`) go to stdout/stderr by default under uvicorn/gunicorn
  — route those through your platform's standard log collection rather than
  a file this app manages.

---

## 5. Output-file retention

`POST /api/v1/submit` writes per-form PDFs/field-map JSONs and merged mailing
packets to disk under `output_dir` (default `outputs/`), and none of that is
automatically cleaned up by the API itself — `GET /api/v1/erasure` deletes a
specific filer's files on request, but nothing purges stale output on a
schedule.

A retention script is provided at `scripts/purge_old_outputs.py` — run it
with `--help` for the current set of options (age threshold, target
directory, dry-run, etc.). Wire it into a periodic job (cron, systemd timer,
or your platform's scheduled-task equivalent) appropriate to your retention
policy, e.g.:

```bash
cd nra-tax-engine
python -m scripts.purge_old_outputs --help
```

Since `outputs/` (and any custom `output_dir`) can contain filer PII in the
generated PDFs/JSONs, treat retention as a compliance control, not just disk
hygiene — align the purge interval with whatever data-retention commitment
you've made to filers, and confirm the script's dry-run output before
pointing it at a real output directory for the first time.

---

## 6. TLS / SSL

This application does not manage certificates or terminate TLS itself —
`uvicorn`/`gunicorn` in the configurations above serve plain HTTP. In
production, put it behind:

- A reverse proxy (nginx, Caddy, or your platform's managed ingress) doing
  TLS termination and forwarding to `http://127.0.0.1:8000`, or
- A platform that manages TLS for you at the edge (e.g. the frontend on
  Vercel gets TLS automatically; a container platform / PaaS hosting the
  engine typically offers managed TLS on its ingress).

If you do terminate TLS with your own nginx/Caddy in front of this app, also
forward `X-Forwarded-For`/`X-Forwarded-Proto` and revisit the rate limiter's
`key_func` (`src/api/rate_limit.py` currently uses `get_remote_address`,
which reads the direct peer IP — this is correct for a single reverse-proxy
hop today, but would need to become proxy-aware, e.g. parsing
`X-Forwarded-For`, if you add another hop such as a CDN in front of the
proxy).

---

## 7. Deploy notes (zero-downtime-ish)

This is a small, stateless FastAPI service — no database migrations, no
distributed coordination — so a full blue-green or canary setup is more
infrastructure than this app currently warrants. A proportionate approach:

- **Multiple workers, rolling restart.** With `--workers N > 1` (uvicorn) or
  gunicorn's worker model, you can send `SIGHUP` (gunicorn) or restart the
  service under your process supervisor; gunicorn supports graceful worker
  reload (`kill -HUP <master pid>`) so in-flight requests on other workers
  aren't dropped mid-restart. Plain `uvicorn --workers N` does not support
  graceful reload the way gunicorn's master process does — prefer the
  gunicorn+uvicorn-worker setup (§3, Option B) if rolling restarts without
  dropped connections matter to you.
- **Health check before flipping traffic.** Whatever deploys the new
  version, gate it on `GET /api/v1/healthz` returning 200 before routing
  production traffic to it (this is cheap and network-free by design — see
  the docstring in `main.py` — so it's safe to poll aggressively during a
  deploy).
- **No in-memory state to preserve across restarts** beyond a single
  in-flight request's `state.audit_trail` (which is also persisted to disk
  immediately per-entry when `QUADTAX_AUDIT_DIR` is set, so a mid-request
  restart loses at most the not-yet-persisted entries of that one request,
  not history). There's no session store or cache to warm.
- **If deploying behind a load balancer with 2+ instances**, this is
  sufficient for true zero-downtime deploys today: deploy to one instance,
  wait for its `/api/v1/healthz` to go green, then move to the next. A
  single-instance deployment will have a brief gap during process restart —
  acceptable for this app's current traffic profile, but worth knowing
  going in.
- **CI gate before any deploy.** `.github/workflows/ci.yml` runs on every
  push and pull request: the backend pytest suite, a frontend typecheck +
  `next build`, and an OpenAPI schema-drift check (regenerates
  `openapi.json` / `api-types.ts` and fails if they differ from what's
  committed). Treat a green CI run as a deploy precondition — don't deploy
  a commit that hasn't passed it.

---

## 8. Continuous integration

`.github/workflows/ci.yml` runs three jobs on every push and pull request
(any branch):

1. **Backend (pytest)** — installs `nra-tax-engine` with dev extras and runs
   the full test suite (`python3 -m pytest -q`).
2. **Frontend (typecheck + build)** — `npx tsc --noEmit` and `npx next build`
   against `nra-tax-client/`.
3. **OpenAPI schema drift check** — regenerates `openapi.json` from the live
   FastAPI schema (`python -m scripts.gen_openapi`) and `api-types.ts` from
   that schema (`npx openapi-typescript`), then fails the build if either
   generated file differs from what's committed. This is what keeps the
   client's generated TypeScript types honest against the actual API
   contract — see the README's "Contract sync" note; run
   `npm run sync-api` locally before committing an API change instead of
   letting CI catch the drift after the fact.

There is currently no CD step in this workflow — it verifies the commit is
deployable, it does not itself deploy. Deployment is a manual/external step
per the process guidance above.
