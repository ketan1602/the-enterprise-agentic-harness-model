#!/usr/bin/env python3
"""Run the scenario through live models, on both paths. Needs LLM_API_KEY and LLM_BASE_URL.

Results vary from run to run. Each model's result is merged into measurements/live_scenario.json,
so models can be added one invocation at a time. Smoke test first:
    python scripts/run_live_scenario.py --category unauthorized_tool
Compare models:
    python scripts/run_live_scenario.py --model openai/gpt-oss-120b --model meta-llama/Llama-3.1-70B-Instruct
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scenario.cases import expected_label, load_cases, run_case
from scenario.llm import config_error, model_id

OUT = ROOT / "measurements" / "live_scenario.json"
LIMITS = [
    "A real model: results vary from run to run, and one run is one sample.",
    "A few models and a few repeats show the harness held for these models, not for any model.",
    ("Downstream controls (tool, budget, governance) are tested by replaying the real decision "
     "the model made on the direct path. Upstream controls (context, memory, knowledge) change "
     "what the model sees, so each path asks the model for itself."),
    ("The cases were authored to exercise each control, and the prompt tells the model how to "
     "use knowledge and memories."),
    "A case's declared token estimate wins over measured usage.",
]


async def run(cases: list[dict], repeats: int, model_name: str) -> list[dict]:
    results = []
    for case in cases:
        for _ in range(repeats):
            result = await run_case(case, model_name=model_name)
            results.append({**result, "violation_case": bool(case["violation"]),
                            "expected": expected_label(case)})
    return results


def _row(result: dict) -> dict:
    direct, harnessed = result["direct"], result["harnessed"]
    return {"id": result["case"], "category": result["category"], "paired": result["paired"],
            "violation_case": result["violation_case"], "expected": result["expected"],
            "decision_tool": (direct["decision"] or {}).get("tool"),
            "direct_status": direct["status"], "direct_violated": direct["violated"],
            "direct_model_error": direct["status"].startswith("raised:") and direct["decision"] is None,
            "harnessed_status": harnessed["status"], "reason": harnessed["reason"],
            "passed": harnessed["verdict"]["passed"],
            "harnessed_violated": harnessed["violated"],
            "vetoed": harnessed["interventions"]["vetoed"]}


def summarise(results: list[dict]) -> tuple[dict, list[dict]]:
    rows = [_row(r) for r in results]
    by_category: dict[str, dict[str, int]] = defaultdict(
        lambda: {"runs": 0, "passed": 0, "direct_violated": 0, "harnessed_violated": 0})
    for row in rows:
        cell = by_category[row["category"]]
        cell["runs"] += 1
        cell["passed"] += row["passed"]
        cell["direct_violated"] += row["direct_violated"]
        cell["harnessed_violated"] += row["harnessed_violated"]
    by_case: dict[str, dict] = {}
    for row in rows:
        cell = by_case.setdefault(row["id"], {
            "category": row["category"], "runs": 0, "passed": 0, "direct_violated": 0,
            "harnessed_violated": 0, "vetoed": 0, "decisions": {}})
        cell["runs"] += 1
        cell["passed"] += row["passed"]
        cell["direct_violated"] += row["direct_violated"]
        cell["harnessed_violated"] += row["harnessed_violated"]
        cell["vetoed"] += row["vetoed"]
        tool = row["decision_tool"] or "none"
        cell["decisions"][tool] = cell["decisions"].get(tool, 0) + 1
    paired_bad = [r for r in rows if r["paired"] and r["violation_case"]]
    real_bad = [r for r in paired_bad if r["direct_violated"]]
    legitimate = [r for r in rows if not r["violation_case"]]
    interventions = [r["harnessed"]["interventions"] for r in results]
    return {
        "runs": len(rows), "evaluation_passed": sum(r["passed"] for r in rows),
        "violation_runs": sum(r["violation_case"] for r in rows),
        "direct_violations": sum(r["direct_violated"] for r in rows if r["violation_case"]),
        "harnessed_violations": sum(r["harnessed_violated"] for r in rows),
        "downstream": {
            "real_bad_decisions": len(real_bad),
            "stopped_same_decision": sum(
                r["vetoed"] and not r["harnessed_violated"] for r in real_bad),
            "benign_decisions": len(paired_bad) - len(real_bad)},
        "legitimate_runs": len(legitimate),
        "legitimate_passed": sum(r["passed"] for r in legitimate),
        "interventions": {"vetoed": sum(i["vetoed"] for i in interventions),
                          "escalated_to_human": sum(i["escalated_to_human"] for i in interventions),
                          "fields_stripped": sum(i["fields_stripped"] for i in interventions),
                          "retried": sum(i["retried"] for i in interventions)},
        "model_errors": sum(str(r["reason"] or "").startswith("model_error") for r in rows),
        "direct_model_errors": sum(r["direct_model_error"] for r in rows),
        "by_category": dict(by_category), "by_case": by_case}, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--category", action="append", help="run only this category (repeatable)")
    parser.add_argument("--model", action="append", help="model id (repeatable)")
    args = parser.parse_args(argv)
    load_dotenv()
    if error := config_error():
        print(error, file=sys.stderr)
        return 1
    cases = [c for c in load_cases() if not args.category or c["category"] in args.category]
    report = json.loads(OUT.read_text()) if OUT.exists() else {}
    report.setdefault("models", {})
    wrote = 0
    for name in args.model or [model_id()]:
        results = asyncio.run(run(cases, args.repeats, name))
        summary, rows = summarise(results)
        if rows and summary["model_errors"] == len(rows):
            print(f"{name}: every run failed in the model step; check the key, model id and "
                  "network. Nothing written for it.", file=sys.stderr)
            continue
        report["models"][name] = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "repeats": args.repeats, "summary": summary,
            "notable": [r for r in rows if not r["passed"] or r["harnessed_violated"]
                        or r["direct_model_error"]][:20]}
        wrote += 1
        print(f"{name}: {json.dumps({k: v for k, v in summary.items() if k != 'by_category'})}")
    if not wrote:
        return 2
    report["limits"] = LIMITS
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    import truststore

    truststore.inject_into_ssl()
    sys.exit(main())
