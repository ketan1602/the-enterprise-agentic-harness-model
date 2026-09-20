"""Reconciliation agent tests — all LLM calls mocked."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.reconciliation.graph import build_reconciliation_harness
from agents.reconciliation.schemas import ReconciliationInput, ReconciliationOutput, ReconState


def _sample_input():
    return {
        "batch_id": "BATCH-001", "period": "2024-01",
        "gl_record_count": 100, "payment_record_count": 100, "bank_record_count": 100,
        "gl_total": 50000.0, "payment_total": 50000.0, "bank_total": 50000.0,
        "sample_discrepancies": [],
    }


def test_reconciliation_input_schema_valid():
    r = ReconciliationInput(**_sample_input())
    assert r.batch_id == "BATCH-001"


def test_reconciliation_output_schema_valid():
    o = ReconciliationOutput(
        batch_id="BATCH-001", status="clean", discrepancy_count=0,
        total_variance=0.0, requires_human_review=False,
        summary="All records match.", recommended_actions=["Archive batch"],
    )
    assert o.status == "clean"


def test_build_reconciliation_harness_returns_harness():
    h = build_reconciliation_harness()
    assert h is not None and h.run_count == 0


@pytest.mark.asyncio
async def test_analyze_node_parses_llm_response():
    from agents.reconciliation.nodes import analyze_node
    mock_resp = MagicMock()
    mock_resp.content = (
        '{"status":"clean","discrepancy_count":0,"total_variance":0.0,'
        '"requires_human_review":false,"analysis_notes":"All match."}'
    )
    state: ReconState = {
        **_sample_input(),
        "status": None, "discrepancy_count": None,
        "total_variance": None, "requires_human_review": None,
        "summary": None, "recommended_actions": None, "errors": [],
        "_analysis_notes": None,
    }
    with patch("agents.reconciliation.nodes.ChatAnthropic") as M:
        m = AsyncMock()
        m.ainvoke.return_value = mock_resp
        M.return_value = m
        result = await analyze_node(state)
    assert result["status"] == "clean"
    assert result["discrepancy_count"] == 0


@pytest.mark.asyncio
async def test_recommend_node_parses_llm_response():
    from agents.reconciliation.nodes import recommend_node
    mock_resp = MagicMock()
    mock_resp.content = (
        '{"summary":"Batch is clean.","recommended_actions":["Archive batch","Send confirmation"]}'
    )
    state: ReconState = {
        **_sample_input(),
        "status": "clean", "discrepancy_count": 0,
        "total_variance": 0.0, "requires_human_review": False,
        "summary": None, "recommended_actions": None, "errors": [],
        "_analysis_notes": "All match.",
    }
    with patch("agents.reconciliation.nodes.ChatAnthropic") as M:
        m = AsyncMock()
        m.ainvoke.return_value = mock_resp
        M.return_value = m
        result = await recommend_node(state)
    assert result["summary"] == "Batch is clean."
    assert len(result["recommended_actions"]) == 2


@pytest.mark.asyncio
async def test_full_harness_run_produces_result():
    harness = build_reconciliation_harness()
    analyze_resp = MagicMock()
    analyze_resp.content = (
        '{"status":"discrepancies_found","discrepancy_count":2,"total_variance":250.25,'
        '"requires_human_review":false,"analysis_notes":"Two timing differences."}'
    )
    recommend_resp = MagicMock()
    recommend_resp.content = (
        '{"summary":"Two timing discrepancies found.",'
        '"recommended_actions":["Investigate timing differences","Recheck payment dates"]}'
    )
    responses = [analyze_resp, recommend_resp]
    call_idx = [0]

    async def side_effect(messages, **kwargs):
        resp = responses[call_idx[0] % len(responses)]
        call_idx[0] += 1
        return resp

    with patch("agents.reconciliation.nodes.ChatAnthropic") as M:
        m = MagicMock()
        m.ainvoke = side_effect
        M.return_value = m
        result = await harness.run({
            **_sample_input(),
            "gl_total": 125430.50, "payment_total": 125180.25, "bank_total": 125430.50,
            "payment_record_count": 98,
            "sample_discrepancies": [{"id": "D1", "amount": 250.25, "type": "timing"}],
        })
    assert result.success
    assert result.output.status == "discrepancies_found"
