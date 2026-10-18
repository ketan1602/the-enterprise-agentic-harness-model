"""The running scenario: the support agent from the previous article, wired to ten capabilities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from harness_core.capabilities import (
    AgentManifest,
    Budget,
    Capabilities,
    CapabilityHarness,
    ModelDecision,
)
from harness_core.capabilities.reference import (
    ReferenceContext,
    ReferenceEvaluation,
    ReferenceExecution,
    ReferenceGovernance,
    ReferenceKnowledge,
    ReferenceLearning,
    ReferenceMemory,
    ReferenceObservability,
    ReferenceOrchestration,
    ReferenceTools,
)
from harness_core.capabilities.types import Model

AGENT_ID = "support-agent"
REFUND_LIMIT = 100.0
ALLOWED_CONTEXT = frozenset({"customer_id", "order_id", "subject", "amount"})
FORBIDDEN_CONTEXT = frozenset({"card_number", "api_token", "ssn"})
APPROVERS = {"supervisor-1"}
MANIFEST = AgentManifest(AGENT_ID, "customer-platform",
                         ("create_ticket", "add_note", "issue_refund"),
                         Budget(max_tokens=5000, max_cost_usd=0.25), scope="support")
KNOWLEDGE = [
    {"scope": "support", "source_id": "policy-refunds",
     "text": f"refund requests above {REFUND_LIMIT:.0f} require supervisor approval"},
    {"scope": "support", "source_id": "runbook-orders",
     "text": "orders not delivered within 5 days get a ticket"},
]
REQUIRED_ARGS = {"create_ticket": ("subject",), "add_note": ("subject", "note"),
                 "issue_refund": ("order_id", "amount"), "delete_customer": ("customer_id",)}


class APIConnectionError(Exception):
    """Named like the SDK error so retry policies treat it as transient."""


class SupportBackend:
    """Simulated business systems. Every successful side effect is recorded in `effects`."""

    def __init__(self, fail_times: int = 0) -> None:
        self.effects: list[dict] = []
        self._fail_times = fail_times

    def create_ticket(self, subject: str, priority: str = "normal") -> dict:
        if self._fail_times > 0:
            self._fail_times -= 1
            raise APIConnectionError("ticketing api unreachable")
        self.effects.append({"tool": "create_ticket", "subject": subject})
        return {"id": f"T-{len(self.effects)}", "subject": subject}

    def add_note(self, subject: str, note: str) -> dict:
        self.effects.append({"tool": "add_note", "subject": subject})
        return {"subject": subject, "note": note}

    def issue_refund(self, order_id: str, amount: float) -> dict:
        self.effects.append({"tool": "issue_refund", "order_id": order_id, "amount": amount})
        return {"order_id": order_id, "refunded": amount}

    def delete_customer(self, customer_id: str) -> dict:
        self.effects.append({"tool": "delete_customer", "customer_id": customer_id})
        return {"deleted": customer_id}

    def tools(self) -> dict[str, Callable]:
        return {name: getattr(self, name) for name in REQUIRED_ARGS}


@dataclass
class ModelTrace:
    """What a run's model saw and decided, and how long the model call took."""

    seen: list[set] = field(default_factory=list)
    decisions: list[ModelDecision] = field(default_factory=list)
    seconds: float = 0.0


@dataclass
class Rig:
    harness: CapabilityHarness
    backend: SupportBackend
    trace: ModelTrace
    caps: Capabilities


def _runtime_parts(backend: SupportBackend, adapters: str):
    grants = {AGENT_ID: set(MANIFEST.allowed_tools)}
    if adapters == "core":
        from harness_core.capabilities.bridges import (
            AuditObservability,
            RegistryTools,
            RetryExecution,
            SensorEvaluation,
        )
        tools = RegistryTools(grants)
    else:
        tools = ReferenceTools(grants)
    for name, fn in backend.tools().items():
        tools.register(name, fn, REQUIRED_ARGS[name])

    async def handler(request: dict):
        return await tools.invoke(request["tool"], request["arguments"], request["identity"])

    if adapters == "core":
        return tools, RetryExecution(handler), AuditObservability(), SensorEvaluation()
    return tools, ReferenceExecution(handler), ReferenceObservability(), ReferenceEvaluation()


def build(model_factory: Callable[[ModelTrace], Model], fail_times: int = 0,
          suspended: bool = False, adapters: str = "reference",
          with_knowledge: bool = True) -> Rig:
    backend = SupportBackend(fail_times)
    tools, execution, observability, evaluation = _runtime_parts(backend, adapters)
    governance = ReferenceGovernance({AGENT_ID: {"run"}}, approvers=APPROVERS)
    if suspended:
        governance.suspend(AGENT_ID)
    caps = Capabilities(
        execution=execution, knowledge=ReferenceKnowledge(KNOWLEDGE if with_knowledge else []),
        context=ReferenceContext(ALLOWED_CONTEXT), memory=ReferenceMemory(), tools=tools,
        orchestration=ReferenceOrchestration(
            lambda r: r["kind"] == "issue_refund" and r["amount"] > REFUND_LIMIT),
        governance=governance, observability=observability, evaluation=evaluation,
        learning=ReferenceLearning())
    trace = ModelTrace()
    return Rig(CapabilityHarness(caps, model_factory(trace)), backend, trace, caps)
