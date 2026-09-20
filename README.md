# Article 02 — Beyond the Model: Agent Harness Foundations

Part of the [Beyond the Model](https://github.com/ketan1602) series — a Platform Engineering perspective on Agentic AI.

## What This Demonstrates

Before/after complexity analysis: same triage agent, measured with and without harness. Plus a second agent (Financial Reconciliation) built from scratch using the harness — showing the pattern generalises across use cases.

**Key finding:** Agent code reduced by 85%. The harness absorbed all operational complexity.

## Quickstart

```bash
git clone https://github.com/ketan1602/repo-02-agent-harness-foundations
cd repo-02-agent-harness-foundations
pip install -e ".[dev]"
cp .env.example .env   # add your AIREFINERY_API_KEY
uvicorn dashboard.app:app --reload
# Open http://localhost:8000
```

## LLM Backend

Uses [AI Refinery SDK](https://sdk.airefinery.accenture.com/distiller/model_catalog/) (`airefinery-sdk`).
Model is selected at runtime via `AIR_MODEL` env var (default: `openai/gpt-oss-120b`).

```python
from air import AsyncAIRefinery
client = AsyncAIRefinery(api_key=os.environ["AIREFINERY_API_KEY"])
response = await client.chat.completions.create(
    model=os.environ.get("AIR_MODEL", "openai/gpt-oss-120b"),
    messages=[{"role": "system", "content": SYSTEM_PROMPT}, ...],
    temperature=0.1,
)
```

## Framework Architecture

### Design Patterns Used

This repo implements four interlocking patterns from `agent-harness-core`:

| Pattern | Component | Purpose |
|---|---|---|
| **Wrapper / Decorator** | `AgentHarness` | Wraps any `CompiledGraph` — adds all operational capabilities without touching graph code |
| **Strategy** | `RetryPolicy` | Dispatch table `{"linear": fn, "exponential": fn, "jittered": fn}` — swap strategies via config, no `if/elif` |
| **State Machine** | `LifecycleManager` | `VALID_TRANSITIONS` dict as sole authority — `INITIALISING → READY → RUNNING → COMPLETED/FAILED` |
| **Facade** | `AgentHarness.run()` | Single entry point hides lifecycle, retry, validation, audit, cost from callers |

### Harness Lifecycle (per run)

```
validate_input()
  → lifecycle.READY
  → lifecycle.RUNNING
  → graph.ainvoke(config={"callbacks": [metrics_cb]})
  → cost.record(cb.prompt_tokens, cb.completion_tokens)
  → validate_output()
  → lifecycle.COMPLETED
  → HarnessResult(success=True, ...)
```

On any exception: `lifecycle.FAILED` → `HarnessResult(success=False, error=..., ...)` — never raises.

### Retry Strategy

`RetryPolicy` uses an OCP-compliant dispatch table. Three strategies configurable via `config/config.yaml`:

```
linear:      delay = base_delay × attempt
exponential: delay = base_delay × 2^attempt
jittered:    delay = exponential + random(0, base_delay)
```

`RateLimitError`, `APITimeoutError`, `APIConnectionError` are retryable by default.
`with_retry()` returns `(result, attempts_taken)` — the harness records `retry_attempts` in `HarnessResult`.

### Cost Tracking

`_HarnessMetricsCallback(BaseCallbackHandler)` hooks into LangChain's callback system.
Injected via `config={"callbacks": [cb]}` in `graph.ainvoke()`.
Captures `prompt_tokens` and `completion_tokens` from all LLM calls in the graph automatically.
`CostTracker.record()` computes USD cost using configurable per-million-token prices.

### Audit Trail

`AuditEmitter` writes structured events with SHA256 content hashes:
- `run_start` — input hash + schema name
- `run_complete` — output hash + cost
- `run_failed` — error type + message

All events are returned in `HarnessResult.audit_events` and logged via structlog.

## Agents and Scenarios

### Agent 1: IT Service Desk Triage (`agents/triage/`)

**Use case:** Incoming IT support tickets. Classify severity P1–P4, route to correct team, draft first response.

**LangGraph:** `classify_node → draft_node → END`

| Node | Calls LLM | Output fields |
|---|---|---|
| `classify_node` | Yes | severity, affected_system, routing_queue, confidence, classification_reasoning |
| `draft_node` | Yes | draft_subject, draft_body, estimated_resolution_hours |

**Input schema:** `TicketInput(ticket_id, subject, body, reporter_email, submitted_at)`
**Output schema:** `TriageOutput(ticket_id, severity, affected_system, routing_queue, confidence, classification_reasoning, draft_subject, draft_body, estimated_resolution_hours)`

**Before/After:** This is the "refactored" version. The original (repo-01's `agent/nodes.py`) included error handling, retry scaffolding, and operational boilerplate inline. Here, nodes contain only business logic — the harness handles everything else. Run `python scripts/measure_complexity.py` to generate the numbers.

### Agent 2: Financial Reconciliation (`agents/reconciliation/`)

**Use case:** End-of-period GL/payment/bank reconciliation. Classify batch status, identify discrepancies, recommend actions.

**LangGraph:** `analyze_node → recommend_node → END`

| Node | Calls LLM | Output fields |
|---|---|---|
| `analyze_node` | Yes | status, discrepancy_count, total_variance, requires_human_review |
| `recommend_node` | Yes | summary, recommended_actions |

**Input schema:** `ReconciliationInput(batch_id, period, gl_record_count, payment_record_count, bank_record_count, gl_total, payment_total, bank_total, sample_discrepancies)`

**Output schema:** `ReconciliationOutput(batch_id, status, discrepancy_count, total_variance, requires_human_review, summary, recommended_actions)`

**Status values:**
- `clean` — all totals match within $0.01
- `discrepancies_found` — variance ≤ $1000 and ≤ 5 items
- `requires_review` — variance > $1000 or > 5 discrepancy items → triggers human escalation

## Measurements

### `scripts/measure_complexity.py`

Uses `radon` to compute cyclomatic complexity and LOC of:
- `../repo-01-agentic-enterprise-primer/agent/nodes.py` (original — with operational boilerplate)
- `agents/triage/nodes.py` (refactored — business logic only)
- `../agent-harness-core/src/harness_core/` (the harness itself)

Writes `measurements/complexity.json`.

### `scripts/inject_failures.py`

Runs the triage agent 50 times with 30% simulated `RateLimitError` (monkey-patched).
Records: total_runs, first_attempt_success, retry_recovered, ultimately_failed.
Writes retry_effectiveness_pct to `measurements/complexity.json`.

```bash
python scripts/inject_failures.py --failure-rate 0.3
```

## Run Tests

```bash
pytest tests/ -v   # 20 tests, zero API calls
```

## Run Measurements

```bash
python scripts/measure_complexity.py
python scripts/inject_failures.py
# Then open http://localhost:8000/metrics
```

## File Structure

```
repo-02-agent-harness-foundations/
├── agents/
│   ├── triage/          # IT triage: classify → draft
│   └── reconciliation/  # Financial: analyze → recommend
├── dashboard/
│   ├── app.py           # FastAPI — 4 routes
│   ├── charts.py        # SVG chart generators
│   └── static/          # Vanilla JS + dark-theme CSS
├── eval/fixtures/       # 10 reconciliation test cases
├── measurements/        # complexity.json (generated)
├── scripts/
│   ├── measure_complexity.py
│   └── inject_failures.py
└── tests/               # 20 tests, all mocked
```
