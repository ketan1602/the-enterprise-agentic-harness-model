from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from harness_core.capabilities.model import CAPABILITIES, LOOP, PLANES

from dashboard.paths import STATIC

router = APIRouter()

PREVIOUSLY_COVERED = frozenset({"execution", "tools", "governance", "observability"})
ROADMAP = [
    ("ENG-06", "Why Agent Frameworks Will Become Commodities But Harnesses Won't",
     "Execution, Tools, Orchestration"),
    ("ENG-07", "The Cost of an Agent Is NOT Tokens", "Observability, Policy & Governance"),
    ("ENG-08", "The Agent Control Plane: The Next Service Mesh", "Policy & Governance at fleet scale"),
    ("ENG-09", "Harness Engineering: The Missing Discipline", "Evaluation"),
    ("ENG-10", "Agent Factories: Industrialising Agent Delivery", "Prepare phase, golden path"),
    ("ENG-11", "Harness as a Cognitive Load Reduction Platform", "The whole model"),
    ("ENG-12", "AgentOps: The Day-2 Challenge Nobody Talks About",
     "Observability, Evaluation, Learning"),
]


@router.get("/")
async def overview_page():
    return FileResponse(STATIC / "index.html")


@router.get("/api/overview")
async def overview_data():
    planes = [{"name": plane, "capabilities": [
        {"number": c.number, "key": c.key, "name": c.name, "phase": c.phase,
         "previously_covered": c.key in PREVIOUSLY_COVERED}
        for c in CAPABILITIES if c.plane == plane]} for plane in PLANES]
    return JSONResponse({
        "series_id": "ENG-05", "season": "S2 - The Harness",
        "title": "The Enterprise Agentic Harness Model",
        "central_claim": ("A harness is not one thing. It is ten capabilities in three planes, "
                          "each defined by a contract and proven by conformance tests."),
        "previous": "Beyond the Model: Building the Agentic Enterprise",
        "planes": planes, "loop": list(LOOP),
        "roadmap": [{"id": i, "title": t, "deepens": d} for i, t, d in ROADMAP],
    })
