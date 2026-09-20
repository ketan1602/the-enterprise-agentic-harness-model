from __future__ import annotations

import json
from dataclasses import dataclass

from agents.reconciliation.graph import build_reconciliation_harness


@dataclass
class EvalResult:
    total: int
    passed: int
    failed: int
    pass_rate: float
    failures: list[dict]
    total_cost_usd: float
    total_tokens: int
    avg_cost_per_run_usd: float


async def run_eval(fixtures_path: str = "eval/fixtures/reconciliation_cases.json") -> EvalResult:
    with open(fixtures_path) as f:  # noqa: ASYNC230
        cases = json.load(f)
    harness = build_reconciliation_harness()
    passed = 0
    failures: list[dict] = []
    total_cost = 0.0
    total_tokens = 0
    for case in cases:
        result = await harness.run(case["input"])
        total_cost += result.cost_usd
        total_tokens += result.token_usage.get("total_tokens", 0)
        if result.success and result.output:
            status_ok = result.output.status == case["expected"]["status"]
            review_ok = result.output.requires_human_review == case["expected"]["requires_human_review"]
            if status_ok and review_ok:
                passed += 1
            else:
                failures.append({
                    "batch_id": case["input"]["batch_id"],
                    "expected": case["expected"],
                    "actual": {
                        "status": result.output.status,
                        "requires_human_review": result.output.requires_human_review,
                    },
                })
        else:
            failures.append({"batch_id": case["input"]["batch_id"], "error": result.error})
    total = len(cases)
    return EvalResult(
        total=total,
        passed=passed,
        failed=total - passed,
        pass_rate=passed / total if total > 0 else 0.0,
        failures=failures,
        total_cost_usd=total_cost,
        total_tokens=total_tokens,
        avg_cost_per_run_usd=total_cost / total if total > 0 else 0.0,
    )
