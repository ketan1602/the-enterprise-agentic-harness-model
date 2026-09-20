"""Dashboard route tests — all agent calls mocked."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from dashboard.app import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_overview_returns_200(client):
    async with client as c:
        resp = await c.get("/")
    assert resp.status_code == 200
    assert "Beyond the Model" in resp.text


@pytest.mark.asyncio
async def test_demo_get_returns_200(client):
    async with client as c:
        resp = await c.get("/demo")
    assert resp.status_code == 200
    assert "Triage" in resp.text


@pytest.mark.asyncio
async def test_metrics_returns_200(client):
    async with client as c:
        resp = await c.get("/metrics")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_eval_get_returns_200(client):
    async with client as c:
        resp = await c.get("/eval")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_overview_returns_json(client):
    async with client as c:
        resp = await c.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["article_number"] == "02"


@pytest.mark.asyncio
async def test_api_eval_fixtures_returns_10_cases(client):
    async with client as c:
        resp = await c.get("/api/eval/fixtures")
    assert resp.status_code == 200
    assert len(resp.json()) == 10


@pytest.mark.asyncio
async def test_demo_triage_post_returns_200_with_mocked_harness(client):
    mock_output = MagicMock()
    mock_output.ticket_id = "TKT-DEMO"
    mock_output.severity.value = "P2"
    mock_output.affected_system = "VPN"
    mock_output.routing_queue = "infrastructure"
    mock_output.confidence = 0.9
    mock_output.classification_reasoning = "VPN issue."
    mock_output.draft_subject = "Re: VPN"
    mock_output.draft_body = "Investigating."
    mock_output.estimated_resolution_hours = 4
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.output = mock_output
    mock_result.cost_usd = 0.001
    mock_result.duration_ms = 1200
    mock_result.run_id = "test-run-id"
    mock_result.token_usage = {"total_tokens": 500}
    mock_result.error = None
    mock_harness = AsyncMock()
    mock_harness.run.return_value = mock_result
    with patch("dashboard.routes.demo.build_triage_harness", return_value=mock_harness):
        async with client as c:
            resp = await c.post("/api/demo/triage", data={
                "subject": "VPN not connecting",
                "body": "Cannot connect, error 619.",
            })
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_demo_recon_post_returns_200_with_mocked_harness(client):
    mock_output = MagicMock()
    mock_output.batch_id = "BATCH-001"
    mock_output.status = "clean"
    mock_output.discrepancy_count = 0
    mock_output.total_variance = 0.0
    mock_output.requires_human_review = False
    mock_output.summary = "All match."
    mock_output.recommended_actions = ["Archive batch"]
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.output = mock_output
    mock_result.cost_usd = 0.002
    mock_result.duration_ms = 1500
    mock_result.run_id = "test-run-id-2"
    mock_result.token_usage = {"total_tokens": 600}
    mock_result.error = None
    mock_harness = AsyncMock()
    mock_harness.run.return_value = mock_result
    with patch("dashboard.routes.demo.build_reconciliation_harness", return_value=mock_harness):
        async with client as c:
            resp = await c.post("/api/demo/reconciliation", data={
                "batch_id": "BATCH-001",
                "period": "2024-01",
                "gl_total": "50000.00",
                "payment_total": "50000.00",
                "bank_total": "50000.00",
                "gl_record_count": "100",
                "payment_record_count": "100",
                "bank_record_count": "100",
            })
    assert resp.status_code == 200
    assert resp.json()["success"] is True
