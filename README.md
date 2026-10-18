# The Enterprise Agentic Harness Model

**ENG-05 · Season 2: The Harness** · Part of the *Beyond the Model* series by
[ketan1602](https://github.com/ketan1602).

Last week's article defined a harness and ran one through a direct-versus-harnessed experiment.
This article asks the question that left open: a harness is not one thing, so **what are the
types?** The answer here is an executable specification: ten capabilities in three planes, a
contract for each, and conformance tests that decide whether an implementation behaves.

```text
Runtime plane    Execution · Knowledge · Context · Memory · Tools · Orchestration
Control plane    Policy & Governance
Assurance plane  Observability · Evaluation · Learning

Prepare -> Execute -> Observe -> Evaluate -> Improve
```

Every number in this repo is produced by a script or a test and written to `measurements/`.
None is typed into a page or a document.

## Run it

You need Python 3.11 or newer, SSH access to GitHub (the `agent-harness-core` dependency is a
private repo, pinned to its `main` branch; check with
`ssh -T git@github.com`), and an API key and base URL for
any OpenAI-compatible chat endpoint for the live steps.

### 1. Install

```bash
git clone git@github.com:ketan1602/the-enterprise-agentic-harness-model.git
cd the-enterprise-agentic-harness-model
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Prove the code works (no key, no network, no cost)

```bash
pytest
```

Everything passes. The tests stand in for the model (`tests/fake_llm.py`, which exists only
there), so they prove the harness and the wiring, not how any real model behaves. Some tests
report `xfailed`: those are **expected**, not errors. Each records a known gap in
`agent-harness-core` and is written to fail; if a gap is ever fixed, that test starts failing
loudly so the record gets updated.

```bash
ruff check .
```

### 3. Add your key

```bash
cp .env.example .env        # then set LLM_API_KEY and LLM_BASE_URL in .env (never commit it)
```

`LLM_MODEL` picks the default model (`openai/gpt-oss-120b`); `--model` overrides it per run. `.env` is gitignored.

### 4. Generate the evidence

Start with the smoke test, which makes a few model calls:

```bash
python scripts/run_live_scenario.py --category unauthorized_tool
```

Then the full set. Each model takes a few minutes; `--repeats 3` shows how much a model varies,
and results from each model are merged into one file.

```bash
python scripts/run_live_scenario.py --model openai/gpt-oss-120b --model meta-llama/Llama-3.1-70B-Instruct --repeats 3
```

```bash
python scripts/run_conformance.py        # no key needed
python scripts/run_benchmark.py          # overhead outside the model, adapter equivalence
python scripts/run_improvement_cycle.py --model openai/gpt-oss-120b --model meta-llama/Llama-3.1-70B-Instruct
```

Each prints `wrote measurements/<name>.json`. Open those files: they are the numbers the article
should quote. Results vary from run to run; quote the files you generated.

### 5. See it

```bash
uvicorn dashboard.app:app --port 8000
```

Open <http://localhost:8000>. `/demo` and `/eval` make live model calls and read your `.env`.

| Page | What to try |
|---|---|
| `/` Overview | The ten capabilities in three planes, and which were in last week's harness |
| `/demo` | Pick `unauthorized_tool-1`: the model's own decision is run with no controls, then replayed through the harness. Then pick `policy_lookup-1`, run it, tick **Withhold Knowledge**, run again |
| `/metrics` | Per-model results with and without the harness, conformance, the known `agent-harness-core` gaps, overhead, and the Evaluation and Learning result |
| `/eval` | Run every case on both paths |

Stop the server with Ctrl+C.

### If something goes wrong

| Symptom | Fix |
|---|---|
| `pip install` fails fetching `agent-harness-core` | SSH access to GitHub is missing or the key is not loaded: run `ssh -T git@github.com` |
| `python` is too old | Use `python3.11` (or newer) to create the venv |
| A script says `LLM_API_KEY` or `LLM_BASE_URL` `must be set` | Step 3: put both in `.env` |
| A model returns a 404 | Your endpoint does not serve that model id. Use one it lists |
| "every run failed in the model step" | Check the key, the model id and the network; nothing is written in that case |
| Port 8000 is busy | `uvicorn dashboard.app:app --port 8001` |
| `/metrics` says "No measurements yet" | Run the scripts in step 4 |

## What's here

The model itself lives in **`agent-harness-core`** (`harness_core.capabilities`, 1.4.0 and later),
so every article's repo can import it. This repo is the article's evidence layer.

| Path | Purpose |
|---|---|
| `scenario/` | The running support-agent scenario: backend, live model, 16 cases, the human-approval step |
| `scripts/` | `run_conformance.py`, `run_live_scenario.py`, `run_benchmark.py`, `run_improvement_cycle.py`; all but conformance need a key |
| `measurements/` | Generated evidence: `conformance.json`, `live_scenario.json`, `benchmark.json`, `improvement.json` |
| `dashboard/` | Four pages that render those measurements and run the scenario live |
| `tests/` | The scenario, the scripts and the dashboard, with no API calls |
| `tests/fake_llm.py` | Test-only stand-in for the model client |
| `docs/` | Model, conformance method, scenario, series roadmap, article outline |

What `agent-harness-core` provides, and this repo imports: the ten-capability model, one async
`Protocol` per capability, in-memory reference implementations, bridges onto the existing classes,
`CapabilityHarness` (Tool pre-flight check, budgets, human-in-the-loop approval) and a conformance
kit.

## The kinds of evidence

1. **Conformance.** The kit's checks run against the reference implementations and the bridges
   onto the existing `agent-harness-core` classes. No model involved.
2. **Live scenario, with and without the harness.** Every case runs on a live model with no
   controls, then through the harness. Downstream controls (tool, budget, approval, suspension)
   judge the *same real decision* the model made, replayed; upstream controls (context, memory,
   knowledge) ask the model on each path. The report counts the harness's interventions per
   scenario and per model.
3. **Overhead.** The time a run takes outside the model call, with and without the harness.
4. **Evaluation and Learning cycle.** Withhold Knowledge, let Evaluation catch the regression, let
   Learning propose a change that needs an approver. Run on two models.

Live results vary from run to run and come from a few models, so they are never presented as
general.

## agent-harness-core

The repo pins the `main` branch of `agent-harness-core` (switch the pin to a release tag once one is cut). Bridges pass the library's behaviour through faithfully, so the
conformance report shows where it conforms and where it does not. See
[`docs/enterprise-agentic-harness-model.md`](docs/enterprise-agentic-harness-model.md).

## Limits

- The reference implementations are in-memory. Overhead excludes the model call, the network and
  any real backend.
- The 16 cases were authored to exercise each control. Preventing all of them shows each control
  works, not that unanticipated failures are caught.
- Live results come from five models and a few repeats; they vary run to run and say nothing about
  other models. If a model resists an attack, that case tested nothing for it.
- Pending approvals are in memory and do not expire; the dashboard does not offer interactive
  approve and reject buttons.
- Knowledge, Context and Memory have no article in this season.
- No claim is made about productivity, lines of code or total cost.

## Docs

[Model](docs/enterprise-agentic-harness-model.md) ·
[Conformance](docs/conformance-model.md) ·
[Scenario](docs/scenario.md) ·
[Series roadmap](docs/series-roadmap.md) ·
[Article outline](docs/article-outline.md)
