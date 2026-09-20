from __future__ import annotations

import json
import os

from agents.triage.prompts import (
    CLASSIFY_SYSTEM_PROMPT,
    CLASSIFY_USER_TEMPLATE,
    DRAFT_SYSTEM_PROMPT,
    DRAFT_USER_TEMPLATE,
)
from agents.triage.schemas import AgentState

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


async def classify_node(state: AgentState) -> dict:
    """Classify ticket severity, system, and routing queue."""
    from air import AsyncAIRefinery

    client = AsyncAIRefinery(api_key=_get_api_key())
    response = await client.chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": CLASSIFY_USER_TEMPLATE.format(
                subject=state["subject"], body=state["body"])},
        ],
        temperature=0.1,
    )
    data = json.loads(_strip_markdown(response.choices[0].message.content))
    return {
        "severity": data["severity"],
        "affected_system": data["affected_system"],
        "routing_queue": data["routing_queue"],
        "confidence": float(data["confidence"]),
        "classification_reasoning": data["classification_reasoning"],
        "errors": state.get("errors", []),
    }


async def draft_node(state: AgentState) -> dict:
    """Draft the first-response email for the ticket."""
    from air import AsyncAIRefinery

    client = AsyncAIRefinery(api_key=_get_api_key())
    response = await client.chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
            {"role": "user", "content": DRAFT_USER_TEMPLATE.format(
                subject=state["subject"], severity=state["severity"],
                routing_queue=state["routing_queue"], body=state["body"])},
        ],
        temperature=0.1,
    )
    data = json.loads(_strip_markdown(response.choices[0].message.content))
    return {
        "draft_subject": data["draft_subject"],
        "draft_body": data["draft_body"],
        "estimated_resolution_hours": int(data["estimated_resolution_hours"]),
    }
