# Article 02 — Beyond the Model: Agent Harness Foundations

Part of the [Beyond the Model](https://github.com/ketan1602) series — a Platform Engineering perspective on Agentic AI.

## What This Demonstrates

Before/after complexity analysis: same triage agent code, measured with and without harness. Plus a second agent (Financial Reconciliation) built from scratch using the harness — showing the pattern generalises.

**Key finding:** Agent code reduced from ~312 to ~47 lines. The harness absorbed all operational complexity.

## Quickstart

```bash
git clone https://github.com/ketan1602/repo-02-agent-harness-foundations
cd repo-02-agent-harness-foundations
pip install -e ".[dev]"
cp .env.example .env   # add your ANTHROPIC_API_KEY
uvicorn dashboard.app:app --reload
# Open http://localhost:8000
```

## Run Measurements

```bash
python scripts/measure_complexity.py   # LOC + complexity comparison
python scripts/inject_failures.py      # retry effectiveness (30% failure rate)
```

Then refresh http://localhost:8000/metrics to see results.

## Run Tests

```bash
pytest tests/ -v   # zero API calls required
```

## Agents

| Agent | Use Case | Nodes |
|---|---|---|
| `agents/triage/` | IT ticket classification | classify -> draft |
| `agents/reconciliation/` | Financial batch reconciliation | analyze -> recommend |

Both agents are wrapped by `agent-harness-core` — lifecycle, retry, cost tracking, audit logging come for free.
