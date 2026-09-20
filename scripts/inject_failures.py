#!/usr/bin/env python3
"""Inject transient failures to test harness retry behaviour.
Usage: python scripts/inject_failures.py [--failure-rate 0.3]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

TOTAL_RUNS = 50


async def main(failure_rate: float) -> None:
    from unittest.mock import MagicMock, patch

    from agents.triage.graph import build_triage_harness

    results = {
        "total_runs": 0,
        "first_attempt_success": 0,
        "retry_recovered": 0,
        "ultimately_failed": 0,
    }
    call_count = [0]

    def make_patched_ainvoke():
        async def patched_ainvoke(messages, **kwargs):
            call_count[0] += 1
            if random.random() < failure_rate:
                from anthropic import RateLimitError
                raise RateLimitError("Simulated rate limit", response=MagicMock(), body={})
            mock_resp = MagicMock()
            if call_count[0] % 2 == 1:
                mock_resp.content = (
                    '{"severity":"P3","affected_system":"VPN","routing_queue":"infrastructure",'
                    '"confidence":0.85,"classification_reasoning":"Simulated classification"}'
                )
            else:
                mock_resp.content = (
                    '{"draft_subject":"Re: Test","draft_body":"We received your request.",'
                    '"estimated_resolution_hours":4}'
                )
            return mock_resp
        return patched_ainvoke

    with patch("agents.triage.nodes.ChatAnthropic") as MockLLM:
        mock_model = MagicMock()
        mock_model.ainvoke = make_patched_ainvoke()
        MockLLM.return_value = mock_model

        harness = build_triage_harness()
        for i in range(TOTAL_RUNS):
            result = await harness.run({
                "ticket_id": f"TKT-{i:03d}",
                "subject": "Test issue",
                "body": "Test body for failure injection.",
                "reporter_email": "test@example.com",
                "submitted_at": "2024-01-01T09:00:00Z",
            })
            results["total_runs"] += 1
            if result.success:
                if result.retry_attempts == 0:
                    results["first_attempt_success"] += 1
                else:
                    results["retry_recovered"] += 1
            else:
                results["ultimately_failed"] += 1

    print(f"Total runs: {results['total_runs']}")
    print(f"First-attempt success: {results['first_attempt_success']}")
    print(f"Retry-recovered: {results['retry_recovered']}")
    print(f"Ultimately failed: {results['ultimately_failed']}")
    effectiveness = (
        results["retry_recovered"]
        / max(results["retry_recovered"] + results["ultimately_failed"], 1)
    ) * 100
    print(f"Retry effectiveness: {effectiveness:.1f}%")

    path = Path("measurements/complexity.json")
    data = json.loads(path.read_text()) if path.exists() else {}
    data["retry_effectiveness_pct"] = round(effectiveness, 1)
    path.write_text(json.dumps(data, indent=2))
    print(f"Updated {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--failure-rate", type=float, default=0.3)
    args = parser.parse_args()
    asyncio.run(main(args.failure_rate))
