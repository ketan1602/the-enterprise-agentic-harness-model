"""Triage agent tests — all LLM calls mocked."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.triage.graph import build_triage_harness
from agents.triage.schemas import AgentState, Severity, TicketInput, TriageOutput


def test_ticket_input_schema_valid():
    t = TicketInput(
        ticket_id="TKT-001",
        subject="VPN down",
        body="Cannot connect.",
        reporter_email="user@test.com",
        submitted_at=datetime.now(UTC),
    )
    assert t.ticket_id == "TKT-001"


def test_triage_output_schema_valid():
    o = TriageOutput(
        ticket_id="TKT-001",
        severity=Severity.P2,
        affected_system="VPN",
        routing_queue="infrastructure",
        confidence=0.85,
        classification_reasoning="VPN issue.",
        draft_subject="Re: VPN down",
        draft_body="We are investigating.",
        estimated_resolution_hours=4,
    )
    assert o.severity == Severity.P2


def test_triage_output_confidence_bounds():
    with pytest.raises(ValueError):
        TriageOutput(
            ticket_id="X",
            severity=Severity.P3,
            affected_system="A",
            routing_queue="general",
            confidence=1.5,
            classification_reasoning="x",
            draft_subject="x",
            draft_body="x",
            estimated_resolution_hours=1,
        )


def test_build_triage_harness_returns_harness():
    h = build_triage_harness()
    assert h is not None and h.run_count == 0


@pytest.mark.asyncio
async def test_classify_node_parses_llm_response():
    from agents.triage.nodes import classify_node
    mock_resp = MagicMock()
    mock_resp.content = (
        '{"severity":"P2","affected_system":"VPN","routing_queue":"infrastructure",'
        '"confidence":0.9,"classification_reasoning":"VPN issue."}'
    )
    state: AgentState = {
        "ticket_id": "TKT-001", "subject": "VPN", "body": "down", "reporter_email": "x@y.com",
        "severity": None, "affected_system": None, "routing_queue": None, "confidence": None,
        "classification_reasoning": None, "draft_subject": None, "draft_body": None,
        "estimated_resolution_hours": None, "errors": [], "run_id": "test",
    }
    with patch("agents.triage.nodes.ChatAnthropic") as M:
        m = AsyncMock()
        m.ainvoke.return_value = mock_resp
        M.return_value = m
        result = await classify_node(state)
    assert result["severity"] == "P2"
    assert result["routing_queue"] == "infrastructure"


@pytest.mark.asyncio
async def test_draft_node_parses_llm_response():
    from agents.triage.nodes import draft_node
    mock_resp = MagicMock()
    mock_resp.content = (
        '{"draft_subject":"Re: VPN","draft_body":"We are investigating.","estimated_resolution_hours":4}'
    )
    state: AgentState = {
        "ticket_id": "TKT-001", "subject": "VPN", "body": "down", "reporter_email": "x@y.com",
        "severity": "P2", "affected_system": "VPN", "routing_queue": "infrastructure",
        "confidence": 0.9, "classification_reasoning": "ok", "draft_subject": None,
        "draft_body": None, "estimated_resolution_hours": None, "errors": [], "run_id": "test",
    }
    with patch("agents.triage.nodes.ChatAnthropic") as M:
        m = AsyncMock()
        m.ainvoke.return_value = mock_resp
        M.return_value = m
        result = await draft_node(state)
    assert result["draft_subject"] == "Re: VPN"
    assert result["estimated_resolution_hours"] == 4
