#!/usr/bin/env python3
"""Measure harness overhead and adapter equivalence with a live model; write benchmark.json.

Overhead is the time a run takes outside the model call, so model latency, which varies, is
subtracted. Equivalence replays one real decision through the reference and agent-harness-core
compositions and compares the outcomes. Needs LLM_API_KEY and LLM_BASE_URL.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import platform
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scenario.cases import load_cases, run_direct, run_harnessed
from scenario.llm import config_error, model_id

OUT = ROOT / "measurements" / "benchmark.json"
LIMITS = [
    ("Overhead excludes the model call and the network. It includes the tool, the backend and the "
     "in-memory capabilities, so it excludes database and policy-service latency."),
    "A small number of live runs: read the median, treat the p95 as indicative.",
    "Single machine, single process, no concurrency.",
    ("Equivalence replays one real decision per case; it shows the compositions agree on that "
     "decision, not on every decision a model could make."),
]


def _stats(samples: list[float]) -> dict:
    ordered = sorted(samples)
    return {"median_us": round(statistics.median(ordered), 1),
            "p95_us": round(ordered[min(int(len(ordered) * 0.95), len(ordered) - 1)], 1)}


def _outside_model_us(outcome: dict) -> float:
    return (outcome["seconds"] - outcome["model_seconds"]) * 1_000_000


async def overhead(runs: int, model_name: str) -> dict:
    case = next(c for c in load_cases() if c["id"] == "normal_ticket-1")
    direct, harnessed = [], []
    for _ in range(runs):
        direct.append(_outside_model_us(await run_direct(case, model_name)))
        harnessed.append(_outside_model_us(await run_harnessed(case, model_name=model_name)))
    direct_stats, harnessed_stats = _stats(direct), _stats(harnessed)
    return {"runs": runs, "model": model_name, "direct": direct_stats, "harnessed": harnessed_stats,
            "added_median_us": round(harnessed_stats["median_us"] - direct_stats["median_us"], 1)}


def _signature(outcome: dict) -> tuple:
    return (outcome["status"], outcome["reason"], outcome["effects"], outcome["attempts"],
            outcome["verdict"]["passed"])


async def equivalence(cases: list[dict], model_name: str) -> dict:
    replayed = identical = 0
    for case in cases:
        decision = (await run_direct(case, model_name))["decision"]
        if decision is None:
            continue
        reference = await run_harnessed(case, "reference", replay=decision)
        with contextlib.redirect_stdout(io.StringIO()):
            core = await run_harnessed(case, "core", replay=decision)
        replayed += 1
        identical += _signature(reference) == _signature(core)
    return {"cases": len(cases), "decisions_replayed": replayed, "identical_outcomes": identical}


async def measure(runs: int, model_name: str) -> dict:
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(), "machine": platform.machine(),
        "overhead": await overhead(runs, model_name),
        "equivalence": await equivalence(load_cases(), model_name),
        "limits": LIMITS}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=15, help="live runs per path for overhead")
    parser.add_argument("--model", help="model id")
    args = parser.parse_args(argv)
    load_dotenv()
    if error := config_error():
        print(error, file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(asyncio.run(measure(args.runs, model_id(args.model))), indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    import truststore

    truststore.inject_into_ssl()
    sys.exit(main())
