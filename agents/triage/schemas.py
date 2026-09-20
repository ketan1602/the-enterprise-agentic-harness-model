from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TypedDict

from pydantic import BaseModel, Field


class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class TicketInput(BaseModel):
    ticket_id: str
    subject: str
    body: str
    reporter_email: str
    submitted_at: datetime


class TriageOutput(BaseModel):
    ticket_id: str
    severity: Severity
    affected_system: str
    routing_queue: str
    confidence: float = Field(ge=0.0, le=1.0)
    classification_reasoning: str
    draft_subject: str
    draft_body: str
    estimated_resolution_hours: int


class AgentState(TypedDict):
    ticket_id: str
    subject: str
    body: str
    reporter_email: str
    severity: str | None
    affected_system: str | None
    routing_queue: str | None
    confidence: float | None
    classification_reasoning: str | None
    draft_subject: str | None
    draft_body: str | None
    estimated_resolution_hours: int | None
    errors: list[str]
    run_id: str
