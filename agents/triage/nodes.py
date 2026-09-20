from __future__ import annotations

import json
import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from agents.triage.prompts import (
    CLASSIFY_SYSTEM_PROMPT,
    CLASSIFY_USER_TEMPLATE,
    DRAFT_SYSTEM_PROMPT,
    DRAFT_USER_TEMPLATE,
)
from agents.triage.schemas import AgentState


def _llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0.1,
        max_tokens=1024,
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )


async def classify_node(state: AgentState) -> dict:
    model = _llm()
    messages = [
        SystemMessage(content=CLASSIFY_SYSTEM_PROMPT),
        HumanMessage(content=CLASSIFY_USER_TEMPLATE.format(
            subject=state["subject"], body=state["body"]
        )),
    ]
    response = await model.ainvoke(messages)
    data = json.loads(response.content.strip())
    return {
        "severity": data["severity"],
        "affected_system": data["affected_system"],
        "routing_queue": data["routing_queue"],
        "confidence": float(data["confidence"]),
        "classification_reasoning": data["classification_reasoning"],
        "errors": state.get("errors", []),
    }


async def draft_node(state: AgentState) -> dict:
    model = _llm()
    messages = [
        SystemMessage(content=DRAFT_SYSTEM_PROMPT),
        HumanMessage(content=DRAFT_USER_TEMPLATE.format(
            subject=state["subject"],
            severity=state["severity"],
            routing_queue=state["routing_queue"],
            body=state["body"],
        )),
    ]
    response = await model.ainvoke(messages)
    data = json.loads(response.content.strip())
    return {
        "draft_subject": data["draft_subject"],
        "draft_body": data["draft_body"],
        "estimated_resolution_hours": int(data["estimated_resolution_hours"]),
    }
