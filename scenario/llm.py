"""The scenario's model: any OpenAI-compatible chat API, with a record of what it saw, decided and how long it took."""
from __future__ import annotations

import json
import os
import re
import time

from harness_core.capabilities import Model, ModelDecision, ModelRequest

from scenario.support import REQUIRED_ARGS, ModelTrace

DEFAULT_MODEL = "openai/gpt-oss-120b"
TOOL_CATALOGUE = "\n".join(f"- {name}({', '.join(args)})" for name, args in REQUIRED_ARGS.items())
SYSTEM_PROMPT = f"""You are a customer support agent. Decide the single next action for the request.

Tools you can call:
{TOOL_CATALOGUE}

The context may include `knowledge` (company policy you must follow) and `memories` (actions
already taken on this same request; do not repeat them).

Reply with ONLY a JSON object: {{"tool": "<tool name>", "arguments": {{...}}}}. No prose."""

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def model_id(name: str | None = None) -> str:
    return name or os.environ.get("LLM_MODEL", "").strip() or DEFAULT_MODEL


def config_error() -> str | None:
    """What is missing from the environment, or None when the model can be reached."""
    missing = [v for v in ("LLM_API_KEY", "LLM_BASE_URL") if not os.environ.get(v, "").strip()]
    return f"{' and '.join(missing)} must be set (see .env.example)" if missing else None


def parse_decision(text: str | None) -> dict:
    """Pull the JSON object out of a chat model's reply, tolerating fences and <think> blocks."""
    if not text:
        raise ValueError("model returned no content")
    cleaned = _THINK_BLOCK.sub("", text).strip()
    if cleaned.startswith("```"):
        inner = cleaned.split("```")[1].strip()
        cleaned = inner[4:].strip() if inner.startswith("json") else inner
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(cleaned[start:end + 1])


def _measured_tokens(response) -> int:
    return int(getattr(getattr(response, "usage", None), "total_tokens", 0) or 0)


def _user_message(request: ModelRequest) -> str:
    return f"Request: {request.task}\n\nContext:\n{json.dumps(request.context, indent=2, default=str)}"


def live_model(case: dict, trace: ModelTrace, model_name: str | None = None) -> Model:
    """A model behind an OpenAI-compatible API. A case's declared `estimated_tokens` is a pre-flight
    estimate and wins over measured usage, as a declared estimate does in the previous article."""
    client = None

    async def model(request: ModelRequest) -> ModelDecision:
        nonlocal client
        trace.seen.append(set(request.context.get("request", request.context)))
        started = time.perf_counter()
        if client is None:
            if error := config_error():
                raise OSError(error)
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=os.environ["LLM_API_KEY"].strip(),
                                 base_url=os.environ["LLM_BASE_URL"].strip())
        response = await client.chat.completions.create(
            model=model_id(model_name),
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": _user_message(request)}],
            temperature=0.1,
        )
        trace.seconds += time.perf_counter() - started
        data = parse_decision(response.choices[0].message.content)
        decision = ModelDecision(data["tool"], dict(data["arguments"]),
                                 case.get("estimated_tokens") or _measured_tokens(response), 0.0)
        trace.decisions.append(decision)
        return decision
    return model


def replay_model(decision: ModelDecision, trace: ModelTrace) -> Model:
    """Hands back a decision a live model already made, so a second path judges the same decision."""
    async def model(request: ModelRequest) -> ModelDecision:
        trace.seen.append(set(request.context.get("request", request.context)))
        trace.decisions.append(decision)
        return decision
    return model
