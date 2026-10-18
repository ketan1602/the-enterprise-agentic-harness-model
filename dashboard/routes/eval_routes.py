from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from dashboard.live import require_key
from dashboard.paths import STATIC
from scenario.cases import expected_label, load_cases, run_case
from scenario.llm import model_id

router = APIRouter()


@router.get("/eval")
async def eval_page():
    return FileResponse(STATIC / "eval.html")


@router.get("/api/eval/cases")
async def eval_cases():
    return JSONResponse(load_cases())


@router.post("/api/eval/run")
async def eval_run():
    require_key()
    rows = []
    for case in load_cases():
        result = await run_case(case)
        direct, harnessed = result["direct"], result["harnessed"]
        rows.append({"id": case["id"], "category": case["category"], "paired": result["paired"],
                     "expected": expected_label(case), "actual": harnessed["status"],
                     "passed": harnessed["verdict"]["passed"],
                     "direct_violated": direct["violated"],
                     "harnessed_violated": harnessed["violated"],
                     "vetoed": harnessed["interventions"]["vetoed"]})
    return JSONResponse({"model": model_id(), "total": len(rows),
                         "passed": sum(r["passed"] for r in rows), "rows": rows})
