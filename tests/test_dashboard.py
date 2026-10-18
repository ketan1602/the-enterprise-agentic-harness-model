"""Dashboard routes. Metrics must come from measurement files, never from constants."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from dashboard import paths
from dashboard.app import app
from scenario.cases import load_cases


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize("path", ["/", "/demo", "/metrics", "/eval"])
async def test_pages_return_200(client, path):
    async with client as c:
        assert (await c.get(path)).status_code == 200


async def test_overview_describes_the_ten_capability_model(client):
    async with client as c:
        data = (await c.get("/api/overview")).json()
    capabilities = [cap for plane in data["planes"] for cap in plane["capabilities"]]
    assert data["series_id"] == "ENG-05"
    assert data["title"] == "The Enterprise Agentic Harness Model"
    assert [p["name"] for p in data["planes"]] == ["Runtime", "Control", "Assurance"]
    assert len(capabilities) == 10
    assert len(data["loop"]) == 5 and len(data["roadmap"]) == 7


def test_no_unmeasured_headline_is_hardcoded_in_the_pages():
    for page in Path(paths.STATIC).glob("*.html"):
        text = page.read_text()
        assert "85%" not in text and "312" not in text, page.name


async def test_metrics_without_measurements_says_how_to_generate_them(client, monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "MEASUREMENTS", tmp_path)
    async with client as c:
        data = (await c.get("/api/metrics")).json()
    assert data["no_data"] is True
    assert "python scripts/run_live_scenario.py" in data["commands"]


def _summary(real_bad: int, stopped: int, benign: int, harnessed_violations: int,
             legitimate: int, legitimate_passed: int) -> dict:
    return {"runs": 12, "evaluation_passed": 12, "violation_runs": 8, "direct_violations": real_bad,
            "harnessed_violations": harnessed_violations, "model_errors": 0, "by_category": {},
            "downstream": {"real_bad_decisions": real_bad, "stopped_same_decision": stopped,
                           "benign_decisions": benign},
            "legitimate_runs": legitimate, "legitimate_passed": legitimate_passed,
            "interventions": {"vetoed": stopped, "fields_stripped": 0, "retried": 0}}


def _write_measurements(directory: Path) -> None:
    cell = {"passed": 1, "total": 2, "capabilities_tested": 1, "capabilities_in_plane": 6}
    (directory / "conformance.json").write_text(json.dumps({
        "generated_at": "t", "harness_core_version": "x", "capabilities": {},
        "planes": {"Runtime": {"reference": cell}}}))
    (directory / "benchmark.json").write_text(json.dumps({
        "generated_at": "t", "python": "p", "machine": "m", "limits": [],
        "overhead": {"runs": 3, "model": "m1", "added_median_us": 9.5,
                     "direct": {"median_us": 1.0, "p95_us": 2.0},
                     "harnessed": {"median_us": 10.5, "p95_us": 11.0}},
        "equivalence": {"cases": 12, "decisions_replayed": 12, "identical_outcomes": 12}}))
    (directory / "live_scenario.json").write_text(json.dumps({
        "limits": [], "models": {
            "m1": {"generated_at": "t", "repeats": 1, "summary": _summary(5, 4, 1, 1, 4, 3)},
            "m2": {"generated_at": "t", "repeats": 1, "summary": _summary(3, 3, 0, 0, 4, 4)}}}))


async def test_metrics_echo_whatever_the_measurement_files_say(client, monkeypatch, tmp_path):
    _write_measurements(tmp_path)
    monkeypatch.setattr(paths, "MEASUREMENTS", tmp_path)
    async with client as c:
        data = (await c.get("/api/metrics")).json()
    finding = data["key_finding"]
    assert "Across 2 live model(s)" in finding
    assert "7 of 8 real bad decisions stopped" in finding
    assert "1 violations got through" in finding
    assert "7 of 8 legitimate runs unaffected" in finding
    assert "9.5 microseconds" in finding
    assert "7/8" in data["charts"]["effectiveness"]


async def test_metrics_carry_the_improvement_cycle_when_present(client, monkeypatch, tmp_path):
    _write_measurements(tmp_path)
    (tmp_path / "improvement.json").write_text(json.dumps({"models": {"m1": {"reference": {"cases": 5}}}}))
    monkeypatch.setattr(paths, "MEASUREMENTS", tmp_path)
    async with client as c:
        data = (await c.get("/api/metrics")).json()
    assert data["improvement"]["models"]["m1"]["reference"]["cases"] == 5


async def test_committed_measurements_render(client):
    async with client as c:
        data = (await c.get("/api/metrics")).json()
    assert data["no_data"] is False
    live = json.loads((paths.MEASUREMENTS / "live_scenario.json").read_text())
    assert data["live"] == live and data["totals"]["models"] == len(live["models"])


async def test_demo_lists_all_cases(client):
    async with client as c:
        assert len((await c.get("/api/demo/cases")).json()) == len(load_cases())


async def test_demo_judges_the_same_real_decision_on_both_paths(client):
    async with client as c:
        data = (await c.post("/api/demo/run", json={"case_id": "unauthorized_tool-1"})).json()
    assert data["paired"] is True and data["model"]
    assert data["direct"]["violated"] is True
    assert data["harnessed"]["status"] == "blocked" and data["harnessed"]["violated"] is False
    assert data["harnessed"]["decision"] == data["direct"]["decision"]
    assert "run.blocked" in data["harnessed"]["events"]


async def test_demo_can_withhold_knowledge_on_the_harnessed_path(client):
    body = {"case_id": "policy_lookup-1"}
    async with client as c:
        with_policy = (await c.post("/api/demo/run", json=body)).json()
        without = (await c.post("/api/demo/run", json={**body, "knowledge": False})).json()
    assert with_policy["harnessed"]["last_tool"] == "create_ticket"
    assert without["harnessed"]["status"] == "awaiting_approval"
    assert without["harnessed"]["verdict"]["passed"] is False


async def test_demo_rejects_an_unknown_case(client):
    async with client as c:
        assert (await c.post("/api/demo/run", json={"case_id": "nope"})).status_code == 404


@pytest.mark.parametrize("call", [
    ("/api/demo/run", {"case_id": "normal_ticket-1"}),
    ("/api/eval/run", None),
], ids=["demo", "eval"])
async def test_a_missing_key_is_a_clear_error(client, monkeypatch, call):
    monkeypatch.setenv("LLM_API_KEY", "")
    url, body = call
    async with client as c:
        resp = await (c.post(url, json=body) if body else c.post(url))
    assert resp.status_code == 400
    assert "LLM_API_KEY must be set" in resp.json()["detail"]


async def test_eval_runs_every_case_on_both_paths(client):
    async with client as c:
        data = (await c.post("/api/eval/run")).json()
    expected_violations = sum(1 for case in load_cases() if case["violation"])
    assert data["total"] == len(load_cases()) and data["passed"] == data["total"]
    assert sum(r["direct_violated"] for r in data["rows"]) == expected_violations
    assert sum(r["harnessed_violated"] for r in data["rows"]) == 0


def test_the_server_trusts_the_system_certificate_store():
    import ssl

    import truststore

    import dashboard.app  # noqa: F401 - importing the app is what installs the trust store

    assert ssl.SSLContext is truststore.SSLContext
