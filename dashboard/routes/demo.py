from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Form
from fastapi.responses import FileResponse, JSONResponse

from agents.reconciliation.graph import build_reconciliation_harness
from agents.triage.graph import build_triage_harness

router = APIRouter()


@router.get("/demo")
async def demo_page():
    return FileResponse("dashboard/static/demo.html")


@router.post("/api/demo/triage")
async def demo_triage(
    ticket_id: str = Form(default="TKT-DEMO"),
    subject: str = Form(...),
    body: str = Form(...),
    reporter_email: str = Form(default="user@company.com"),
):
    harness = build_triage_harness()
    result = await harness.run({
        "ticket_id": ticket_id,
        "subject": subject,
        "body": body,
        "reporter_email": reporter_email,
        "submitted_at": datetime.now(UTC).isoformat(),
    })
    out = result.output
    return JSONResponse({
        "success": result.success,
        "run_id": result.run_id,
        "cost_usd": result.cost_usd,
        "duration_ms": result.duration_ms,
        "token_usage": result.token_usage,
        "error": result.error,
        "output": {
            "ticket_id": out.ticket_id,
            "severity": out.severity.value,
            "affected_system": out.affected_system,
            "routing_queue": out.routing_queue,
            "confidence": out.confidence,
            "classification_reasoning": out.classification_reasoning,
            "draft_subject": out.draft_subject,
            "draft_body": out.draft_body,
            "estimated_resolution_hours": out.estimated_resolution_hours,
        } if result.success and out else None,
    })


@router.post("/api/demo/reconciliation")
async def demo_reconciliation(
    batch_id: str = Form(default="BATCH-001"),
    period: str = Form(default="2024-01"),
    gl_total: float = Form(default=125430.50),
    payment_total: float = Form(default=125180.25),
    bank_total: float = Form(default=125430.50),
    gl_record_count: int = Form(default=342),
    payment_record_count: int = Form(default=339),
    bank_record_count: int = Form(default=342),
):
    harness = build_reconciliation_harness()
    result = await harness.run({
        "batch_id": batch_id,
        "period": period,
        "gl_record_count": gl_record_count,
        "payment_record_count": payment_record_count,
        "bank_record_count": bank_record_count,
        "gl_total": gl_total,
        "payment_total": payment_total,
        "bank_total": bank_total,
        "sample_discrepancies": [{"id": "D001", "amount": 250.25, "type": "timing"}],
    })
    out = result.output
    return JSONResponse({
        "success": result.success,
        "run_id": result.run_id,
        "cost_usd": result.cost_usd,
        "duration_ms": result.duration_ms,
        "token_usage": result.token_usage,
        "error": result.error,
        "output": {
            "batch_id": out.batch_id,
            "status": out.status,
            "discrepancy_count": out.discrepancy_count,
            "total_variance": out.total_variance,
            "requires_human_review": out.requires_human_review,
            "summary": out.summary,
            "recommended_actions": out.recommended_actions,
        } if result.success and out else None,
    })
