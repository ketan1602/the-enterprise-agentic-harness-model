from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from dashboard.live import require_key
from dashboard.paths import STATIC
from scenario.cases import expected_label, load_cases, run_case
from scenario.llm import model_id

router = APIRouter()


class RunBody(BaseModel):
    case_id: str
    knowledge: bool = True


@router.get("/demo")
async def demo_page():
    return FileResponse(STATIC / "demo.html")


@router.get("/api/demo/cases")
async def demo_cases():
    return JSONResponse([{"id": c["id"], "category": c["category"], "utterance": c["utterance"],
                          "expected": expected_label(c), "control": c["control"]}
                         for c in load_cases()])


@router.post("/api/demo/run")
async def demo_run(body: RunBody):
    case = next((c for c in load_cases() if c["id"] == body.case_id), None)
    if case is None:
        raise HTTPException(status_code=404, detail=f"unknown case: {body.case_id}")
    require_key()
    result = await run_case(case, with_knowledge=body.knowledge)
    return JSONResponse({"model": model_id(), **result})
