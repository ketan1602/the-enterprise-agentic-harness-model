from __future__ import annotations

import json
import os

from agents.reconciliation.prompts import (
    ANALYZE_SYSTEM_PROMPT,
    ANALYZE_USER_TEMPLATE,
    RECOMMEND_SYSTEM_PROMPT,
    RECOMMEND_USER_TEMPLATE,
)
from agents.reconciliation.schemas import ReconState

_DEFAULT_MODEL = "openai/gpt-oss-120b"


def _get_model() -> str:
    return os.environ.get("AIR_MODEL", _DEFAULT_MODEL)


def _get_api_key() -> str:
    key = os.environ.get("AIREFINERY_API_KEY", "").strip()
    if not key:
        raise OSError("AIREFINERY_API_KEY must be set (see .env.example)")
    return key


def _strip_markdown(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            inner = parts[1].strip()
            if inner.startswith("json"):
                inner = inner[4:].strip()
            return inner
    return text


async def analyze_node(state: ReconState) -> dict:
    """Analyze the reconciliation batch: compute status, discrepancy count, variance."""
    from air import AsyncAIRefinery

    client = AsyncAIRefinery(api_key=_get_api_key())
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
    response = await client.chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
    )
    data = json.loads(_strip_markdown(response.choices[0].message.content))
    return {
        "status": data["status"],
        "discrepancy_count": int(data["discrepancy_count"]),
        "total_variance": float(data["total_variance"]),
        "requires_human_review": bool(data["requires_human_review"]),
        "_analysis_notes": data.get("analysis_notes", ""),
    }


async def recommend_node(state: ReconState) -> dict:
    """Generate summary and recommended actions based on analysis."""
    from air import AsyncAIRefinery

    client = AsyncAIRefinery(api_key=_get_api_key())
    user_content = RECOMMEND_USER_TEMPLATE.format(
        status=state["status"],
        discrepancy_count=state["discrepancy_count"],
        total_variance=state["total_variance"],
        requires_human_review=state["requires_human_review"],
        analysis_notes=state.get("_analysis_notes", ""),
    )
    response = await client.chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": RECOMMEND_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
    )
    data = json.loads(_strip_markdown(response.choices[0].message.content))
    return {
        "summary": data["summary"],
        "recommended_actions": data["recommended_actions"],
    }
