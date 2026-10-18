"""Evaluation and Learning in the scenario.

Withhold Knowledge from a live model, let the Evaluation capability score every case, let the
Learning capability propose from the evidence, then try to apply it three ways. Learning is the
approval gate here: the proposal carries no executable change.
"""
from __future__ import annotations

from scenario.cases import load_cases, run_case
from scenario.llm import live_model
from scenario.support import build

APPROVER = "supervisor-1"
UNAUTHORISED = "intern-7"


async def _approval_id(governance, proposal: dict, approver: str) -> str | None:
    verdict = await governance.approve({"improvement": proposal["id"]}, approver)
    return f"{approver}:{proposal['id']}" if verdict["allowed"] else None


async def _attempt(learning, proposal: dict, approval_id: str | None) -> str:
    try:
        await learning.apply_improvement(proposal, approval_id)
    except PermissionError:
        return "refused"
    return "applied"


async def improvement_cycle(adapters: str = "reference", model_name: str | None = None) -> dict:
    cases = load_cases()
    baseline = [(await run_case(c, adapters, model_name=model_name))["harnessed"] for c in cases]
    degraded = [(await run_case(c, adapters, with_knowledge=False, model_name=model_name))["harnessed"]
                for c in cases]
    failed = [{"case": c["id"], "mismatches": o["verdict"]["mismatches"],
               "expected": c["expected"], "actual_status": o["status"],
               "violated": o["violated"]}
              for c, o in zip(cases, degraded, strict=True) if not o["verdict"]["passed"]]

    caps = build(lambda trace: live_model(cases[0], trace, model_name), adapters=adapters).caps
    proposal = await caps.learning.propose_improvement({"failed": failed})
    unapproved = await _attempt(caps.learning, proposal, None)
    wrong_approver = await _attempt(
        caps.learning, proposal, await _approval_id(caps.governance, proposal, UNAUTHORISED))
    right_approver = await _attempt(
        caps.learning, proposal, await _approval_id(caps.governance, proposal, APPROVER))
    return {
        "cases": len(cases),
        "baseline_passed": sum(o["verdict"]["passed"] for o in baseline),
        "degraded_passed": sum(o["verdict"]["passed"] for o in degraded),
        "failed_cases": [f["case"] for f in failed],
        "violations_while_degraded": sum(f["violated"] for f in failed),
        "proposal_status": proposal["status"],
        "apply_without_approval": unapproved,
        "apply_with_unauthorised_approver": wrong_approver,
        "apply_with_authorised_approver": right_approver,
        "improvements_recorded": len(caps.learning.applied),
    }

