from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from dashboard.charts import horizontal_bar_chart, progress_bar, two_stat_comparison

router = APIRouter()


@router.get("/metrics")
async def metrics_page():
    return FileResponse("dashboard/static/metrics.html")


@router.get("/api/metrics")
async def metrics_data():
    path = Path("measurements/complexity.json")
    if not path.exists():
        return JSONResponse({"no_data": True, "seed_command": "python scripts/measure_complexity.py"})
    with open(path) as f:  # noqa: ASYNC230
        data = json.load(f)

    loc_comparison = two_stat_comparison(
        left_value=str(data.get("original_agent_loc", "?")),
        left_label="Before harness (lines)",
        right_value=str(data.get("refactored_agent_loc", "?")),
        right_label="After harness (lines)",
    )
    retry_chart = horizontal_bar_chart(
        categories=["Auto-recovered", "Required human"],
        values=[
            data.get("retry_effectiveness_pct", 0),
            100 - data.get("retry_effectiveness_pct", 0),
        ],
        max_value=100,
        title="Retry Effectiveness (%)",
        color="#22c55e",
    )
    audit_bar = progress_bar(
        value=data.get("audit_completeness_pct", 0) / 100,
        label="Audit completeness",
        color="#6366f1",
    )
    reduction_pct = data.get("complexity_reduction_pct", 0)
    key_finding = (
        f"Agent code reduced from {data.get('original_agent_loc', '?')} to "
        f"{data.get('refactored_agent_loc', '?')} lines. "
        f"The harness absorbed all operational complexity ({reduction_pct:.0f}% reduction)."
    )
    return JSONResponse({
        "no_data": False,
        "data": data,
        "key_finding": key_finding,
        "charts": {
            "loc_comparison": loc_comparison,
            "retry": retry_chart,
            "audit": audit_bar,
        },
    })
