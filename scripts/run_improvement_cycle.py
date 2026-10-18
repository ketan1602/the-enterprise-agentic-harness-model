#!/usr/bin/env python3
"""Run the Evaluation and Learning cycle with live models; write measurements/improvement.json.

Each model's result is merged into the file, so models can be added one invocation at a time:
    python scripts/run_improvement_cycle.py --model openai/gpt-oss-120b --model meta-llama/Llama-3.1-70B-Instruct
Needs LLM_API_KEY and LLM_BASE_URL.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scenario.improve import improvement_cycle
from scenario.llm import config_error, model_id

OUT = ROOT / "measurements" / "improvement.json"
NOTE = ("Knowledge is withheld, so the model cannot see the refund policy. Downstream cases replay "
        "the model's own decision, so only the Knowledge-dependent case changes: evaluation fails "
        "it while no control is violated. The proposal carries no executable change; Learning here "
        "is the approval gate. One live sample per model.")


async def cycle(model_name: str) -> dict:
    reference = await improvement_cycle("reference", model_name)
    with contextlib.redirect_stdout(io.StringIO()):
        core = await improvement_cycle("core", model_name)
    gate = {k: v for k, v in reference.items() if k.startswith("apply_")}
    return {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "reference": reference,
            "core_adapters_gate_the_same_way":
                gate == {k: v for k, v in core.items() if k.startswith("apply_")}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", action="append", help="model id (repeatable)")
    args = parser.parse_args(argv)
    load_dotenv()
    if error := config_error():
        print(error, file=sys.stderr)
        return 1
    report = json.loads(OUT.read_text()) if OUT.exists() else {}
    report.setdefault("models", {})
    for name in args.model or [model_id()]:
        report["models"][name] = asyncio.run(cycle(name))
        print(f"{name}: failed cases {report['models'][name]['reference']['failed_cases']}")
    report["note"] = NOTE
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    import truststore

    truststore.inject_into_ssl()
    sys.exit(main())
