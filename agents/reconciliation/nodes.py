from __future__ import annotations

import json
import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from agents.reconciliation.prompts import (
    ANALYZE_SYSTEM_PROMPT,
    ANALYZE_USER_TEMPLATE,
    RECOMMEND_SYSTEM_PROMPT,
    RECOMMEND_USER_TEMPLATE,
)
from agents.reconciliation.schemas import ReconState


def _llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0.1,
        max_tokens=1024,
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )


async def analyze_node(state: ReconState) -> dict:
    user_content = ANALYZE_USER_TEMPLATE.format(
        period=state["period"],
        gl_record_count=state["gl_record_count"],
        gl_total=state["gl_total"],
        payment_record_count=state["payment_record_count"],
        payment_total=state["payment_total"],
        bank_record_count=state["bank_record_count"],
        bank_total=state["bank_total"],
        sample_discrepancies=state["sample_discrepancies"],
    )
    response = await _llm().ainvoke([
        SystemMessage(content=ANALYZE_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])
    data = json.loads(response.content.strip())
    return {
        "status": data["status"],
        "discrepancy_count": int(data["discrepancy_count"]),
        "total_variance": float(data["total_variance"]),
        "requires_human_review": bool(data["requires_human_review"]),
        "_analysis_notes": data.get("analysis_notes", ""),
    }


async def recommend_node(state: ReconState) -> dict:
    user_content = RECOMMEND_USER_TEMPLATE.format(
        status=state["status"],
        discrepancy_count=state["discrepancy_count"],
        total_variance=state["total_variance"],
        requires_human_review=state["requires_human_review"],
        analysis_notes=state.get("_analysis_notes", ""),
    )
    response = await _llm().ainvoke([
        SystemMessage(content=RECOMMEND_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])
    data = json.loads(response.content.strip())
    return {
        "summary": data["summary"],
        "recommended_actions": data["recommended_actions"],
    }
