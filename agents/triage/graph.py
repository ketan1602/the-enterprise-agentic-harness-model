from __future__ import annotations

from harness_core import AgentHarness, load_config
from langgraph.graph import END, StateGraph

from agents.triage.nodes import classify_node, draft_node
from agents.triage.schemas import AgentState, TicketInput, TriageOutput


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("classify", classify_node)
    g.add_node("draft", draft_node)
    g.set_entry_point("classify")
    g.add_edge("classify", "draft")
    g.add_edge("draft", END)
    return g.compile()


def build_triage_harness() -> AgentHarness:
    config = load_config("config/config.yaml")
    return AgentHarness(
        graph=_build_graph(),
        agent_name="it-triage-agent",
        agent_version="1.0.0",
        input_schema=TicketInput,
        output_schema=TriageOutput,
        config=config,
    )
