"""Executable evidence behind the claims in scripts/run_conformance.py about harness_core."""
from __future__ import annotations

import importlib
import pkgutil

import harness_core
from harness_core.stores.approval import NullApprovalStore
from harness_core.stores.checkpoint import NullCheckpointStore
from harness_core.stores.episodic import NullEpisodicStore
from harness_core.stores.knowledge_graph import NullKnowledgeGraph


def test_the_capability_model_ships_in_the_pinned_release():
    major_minor = tuple(int(part) for part in harness_core.__version__.split(".")[:2])
    assert major_minor >= (1, 4)
    assert hasattr(importlib.import_module("harness_core.capabilities"), "CapabilityHarness")


async def test_null_episodic_store_does_not_retain():
    store = NullEpisodicStore()
    await store.upsert("r1", "text", {})
    assert await store.search("text") == []


async def test_null_checkpoint_store_does_not_retain():
    store = NullCheckpointStore()
    await store.save("r1", "agent", {"step": 1})
    assert await store.load("r1") is None


async def test_null_knowledge_graph_returns_nothing():
    graph = NullKnowledgeGraph()
    await graph.upsert_node("Doc", {"id": "d1"})
    assert await graph.query("MATCH (n) RETURN n") == []


async def test_null_approval_store_forgets():
    store = NullApprovalStore()
    await store.create("g1", "r1", "ok?")
    assert await store.get("g1") is None


def test_package_has_no_context_or_learning_module():
    modules = {m.name for m in pkgutil.iter_modules(harness_core.__path__)}
    assert not {"context", "learning", "memory", "knowledge"} & modules
