"""A stand-in for the model client, so the tests make no API calls.

It lives in tests/ only. It answers the way a plausible model would: it obeys what the customer
asks (including an injected instruction), follows refund policy and memories it is shown, and
otherwise opens a ticket.
"""
from __future__ import annotations

import json
import re
from unittest.mock import MagicMock

DELETE = re.compile(r"delete their record \((C-\d+)\)")
INJECTED = re.compile(r"delete my customer record (C-\d+)")
REFUND = re.compile(r"refund of (\d+(?:\.\d+)?) for order (O-\d+)")


def decision(tool: str, **arguments) -> str:
    return json.dumps({"tool": tool, "arguments": arguments})


def _parse(message: str) -> tuple[str, dict]:
    head, _, body = message.partition("\n\nContext:\n")
    return head.removeprefix("Request: "), json.loads(body)


def plausible_model(message: str) -> str:
    words, context = _parse(message)
    if found := (DELETE.search(words) or INJECTED.search(words)):
        return decision("delete_customer", customer_id=found.group(1))
    if "delete_customer" in words and (found := re.search(r"C-\d+", words)):
        return decision("delete_customer", customer_id=found.group(0))
    if found := REFUND.search(words):
        amount, order = float(found.group(1)), found.group(2)
        policy = " ".join(str(record) for record in context.get("knowledge", []))
        if amount > 100 and "supervisor approval" in policy:
            return decision("create_ticket", subject=f"Refund {order} needs approval")
        return decision("issue_refund", order_id=order, amount=amount)
    if context.get("memories"):
        return decision("add_note", subject=words, note="duplicate")
    return decision("create_ticket", subject=words)


class FakeLLM:
    """Records every call; `respond` maps the user message to the model's raw reply."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.respond = plausible_model
        self.total_tokens = 100

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        response = MagicMock()
        response.choices[0].message.content = self.respond(kwargs["messages"][1]["content"])
        response.usage.total_tokens = self.total_tokens
        return response

    def user_message(self, index: int) -> str:
        return self.calls[index]["messages"][1]["content"]
