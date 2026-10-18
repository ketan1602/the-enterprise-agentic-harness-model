#!/usr/bin/env python3
"""Run the harness_core conformance kit and write measurements/conformance.json. No model needed.

Capability Conformance = Passed Required Checks / Total Required Checks, per implementation,
reported per capability and per plane. There is deliberately no single aggregate. A known gap is
an expected failure: it is reported as a gap, and a gap that starts passing fails this script.
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import harness_core
from harness_core.capabilities.conformance import IMPLEMENTATIONS, KNOWN_GAPS, run_checks
from harness_core.capabilities.model import CAPABILITIES, PLANES

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "measurements" / "conformance.json"
NO_BRIDGE = {
    "knowledge": "interface only: KnowledgeGraphBase; Null default, Neo4j needs a server",
    "context": "none: nothing in harness_core to bridge",
    "memory": "interface only: EpisodicStoreBase; Null default, Qdrant needs a server",
    "orchestration": "interface only: CheckpointStoreBase; Null default, Postgres needs a server",
    "learning": "none: nothing in harness_core to bridge",
}


async def score(capability: str, impl: str, factory) -> tuple[dict, list[dict]]:
    cell: dict = {"passed": 0, "total": 0, "gaps": []}
    surprises: list[dict] = []
    for result in await run_checks(capability, factory):
        gap = KNOWN_GAPS.get((capability, impl, result.name))
        cell["total"] += 1
        if result.passed and gap is None:
            cell["passed"] += 1
        elif not result.passed and gap is not None:
            cell["gaps"].append({"test": result.name, "reason": gap})
        else:
            surprises.append({"capability": capability, "implementation": impl,
                              "check": result.name, "detail": result.error or "passed but listed as a gap"})
    return cell, surprises


def _planes(capabilities: dict) -> dict:
    planes: dict[str, dict] = {p: {} for p in PLANES}
    for cap in CAPABILITIES:
        for impl, cell in capabilities[cap.key]["implementations"].items():
            agg = planes[cap.plane].setdefault(
                impl, {"passed": 0, "total": 0, "capabilities_tested": 0,
                       "capabilities_in_plane": sum(c.plane == cap.plane for c in CAPABILITIES)})
            agg["passed"] += cell["passed"]
            agg["total"] += cell["total"]
            agg["capabilities_tested"] += 1
    return planes


async def measure() -> tuple[dict, list[dict]]:
    capabilities: dict[str, dict] = {}
    surprises: list[dict] = []
    for cap in CAPABILITIES:
        cells = {}
        for impl, factory in IMPLEMENTATIONS[cap.key].items():
            cells[impl], found = await score(cap.key, impl, factory)
            surprises += found
        capabilities[cap.key] = {"name": cap.name, "plane": cap.plane, "implementations": cells,
                                 "no_adapter": NO_BRIDGE.get(cap.key) if "bridge" not in cells else None}
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(), "harness_core_version": harness_core.__version__,
        "formula": "Capability Conformance = Passed Required Checks / Total Required Checks",
        "capabilities": capabilities, "planes": _planes(capabilities)}, surprises


def main() -> int:
    with contextlib.redirect_stdout(io.StringIO()):  # the bridges log through structlog
        report, surprises = asyncio.run(measure())
    if surprises:
        for item in surprises:
            print(f"unexpected: {item}", file=sys.stderr)
        print("conformance has unexpected results; not writing measurements", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
