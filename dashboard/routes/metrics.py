"""Metrics are rendered only from measurements/*.json. No number is defined in this file."""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from dashboard import paths
from dashboard.charts import progress_bar, stat_card, two_stat_comparison
from dashboard.paths import STATIC

router = APIRouter()

COMMANDS = ["python scripts/run_conformance.py", "python scripts/run_live_scenario.py",
            "python scripts/run_benchmark.py", "python scripts/run_improvement_cycle.py"]


def _load(name: str) -> dict | None:
    path = paths.MEASUREMENTS / name
    return json.loads(path.read_text()) if path.exists() else None


def _plane_bars(planes: dict) -> list[str]:
    bars = []
    for plane, impls in planes.items():
        for impl, cell in impls.items():
            label = (f"{plane} / {impl}: {cell['passed']}/{cell['total']} tests "
                     f"({cell['capabilities_tested']}/{cell['capabilities_in_plane']} capabilities)")
            bars.append(progress_bar(cell["passed"] / cell["total"], label, width=520))
    return bars


def _sum(summaries: list[dict], *path: str) -> int:
    total = 0
    for summary in summaries:
        value = summary
        for key in path:
            value = value[key]
        total += value
    return total


def _live_totals(live: dict) -> dict:
    summaries = [m["summary"] for m in live["models"].values()]
    return {"models": len(summaries), "runs": _sum(summaries, "runs"),
            "real_bad": _sum(summaries, "downstream", "real_bad_decisions"),
            "stopped": _sum(summaries, "downstream", "stopped_same_decision"),
            "benign": _sum(summaries, "downstream", "benign_decisions"),
            "harnessed_violations": _sum(summaries, "harnessed_violations"),
            "legitimate_runs": _sum(summaries, "legitimate_runs"),
            "legitimate_passed": _sum(summaries, "legitimate_passed")}


def _key_finding(totals: dict, bench: dict) -> str:
    return (f"Across {totals['models']} live model(s): {totals['stopped']} of {totals['real_bad']} "
            f"real bad decisions stopped by the harness, {totals['harnessed_violations']} violations "
            f"got through, {totals['legitimate_passed']} of {totals['legitimate_runs']} legitimate "
            f"runs unaffected. Harness overhead {bench['overhead']['added_median_us']} microseconds "
            "at the median, model time excluded.")


@router.get("/metrics")
async def metrics_page():
    return FileResponse(STATIC / "metrics.html")


@router.get("/api/metrics")
async def metrics_data():
    conformance, bench, live = _load("conformance.json"), _load("benchmark.json"), _load("live_scenario.json")
    if conformance is None or bench is None or live is None:
        return JSONResponse({"no_data": True, "commands": COMMANDS})
    totals, over = _live_totals(live), bench["overhead"]
    return JSONResponse({
        "no_data": False, "key_finding": _key_finding(totals, bench), "totals": totals,
        "conformance": conformance, "benchmark": bench, "live": live,
        "improvement": _load("improvement.json"),
        "charts": {
            "planes": _plane_bars(conformance["planes"]),
            "overhead": two_stat_comparison(
                f"{over['direct']['median_us']} us", "Direct, outside the model",
                f"{over['harnessed']['median_us']} us", "Harnessed, outside the model"),
            "effectiveness": stat_card(
                f"{totals['stopped']}/{totals['real_bad']}", "Real bad decisions stopped",
                f"{totals['harnessed_violations']} got through, {totals['benign']} decisions benign"),
        },
    })
