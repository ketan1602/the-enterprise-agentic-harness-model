from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()


@router.get("/")
async def overview_page():
    return FileResponse("dashboard/static/index.html")


@router.get("/api/overview")
async def overview_data():
    return JSONResponse({
        "article_number": "02",
        "article_title": "Beyond the Model: Agent Harness Foundations",
        "central_claim": (
            "The harness absorbs operational complexity so agent authors write only business logic."
        ),
        "key_finding": (
            "Harness adoption reduced agent code from 312 to 47 lines — 85% reduction."
        ),
        "use_case": "IT Triage + Financial Reconciliation — two agents, one harness, same guarantees",
        "repo_name": "repo-02-agent-harness-foundations",
        "series_position": "Demonstrates harness value: before/after complexity comparison",
        "next_repo": "repo-03-framework-swap-experiment",
    })
