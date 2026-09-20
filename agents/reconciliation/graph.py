from __future__ import annotations

from harness_core import AgentHarness, load_config
from langgraph.graph import END, StateGraph

from agents.reconciliation.nodes import analyze_node, recommend_node
from agents.reconciliation.schemas import ReconciliationInput, ReconciliationOutput, ReconState


def _build_graph():
    g = StateGraph(ReconState)
    g.add_node("analyze", analyze_node)
    g.add_node("recommend", recommend_node)
    g.set_entry_point("analyze")
    g.add_edge("analyze", "recommend")
    g.add_edge("recommend", END)
    return g.compile()


def build_reconciliation_harness() -> AgentHarness:
    config = load_config("config/config.yaml")
    return AgentHarness(
        graph=_build_graph(),
        agent_name="reconciliation-agent",
        agent_version="1.0.0",
        input_schema=ReconciliationInput,
        output_schema=ReconciliationOutput,
        config=config,
    )
