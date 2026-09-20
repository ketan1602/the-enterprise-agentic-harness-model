from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel


class ReconciliationInput(BaseModel):
    batch_id: str
    period: str
    gl_record_count: int
    payment_record_count: int
    bank_record_count: int
    gl_total: float
    payment_total: float
    bank_total: float
    sample_discrepancies: list[dict]


class ReconciliationOutput(BaseModel):
    batch_id: str
    status: str  # clean | discrepancies_found | requires_review
    discrepancy_count: int
    total_variance: float
    requires_human_review: bool
    summary: str
    recommended_actions: list[str]


class ReconState(TypedDict):
    batch_id: str
    period: str
    gl_record_count: int
    payment_record_count: int
    bank_record_count: int
    gl_total: float
    payment_total: float
    bank_total: float
    sample_discrepancies: list[dict]
    status: str | None
    discrepancy_count: int | None
    total_variance: float | None
    requires_human_review: bool | None
    summary: str | None
    recommended_actions: list[str] | None
    errors: list[str]
    _analysis_notes: str | None
