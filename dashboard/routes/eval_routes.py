from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()


@router.get("/eval")
async def eval_page():
    return FileResponse("dashboard/static/eval.html")


@router.get("/api/eval/fixtures")
async def eval_fixtures():
    path = Path("eval/fixtures/reconciliation_cases.json")
    with open(path) as f:  # noqa: ASYNC230
        return JSONResponse(json.load(f))
