"""The evidence scripts, with the model client stood in for."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from tests.fake_llm import decision

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str, monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "OUT", tmp_path / f"{name}.json")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    return module


@pytest.fixture
def live(monkeypatch, tmp_path):
    return _load("run_live_scenario", monkeypatch, tmp_path)


@pytest.mark.parametrize("name", ["run_live_scenario", "run_benchmark", "run_improvement_cycle"])
def test_every_script_refuses_to_run_without_a_key(name, monkeypatch, tmp_path, capsys):
    script = _load(name, monkeypatch, tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "")
    assert script.main([]) == 1
    assert "LLM_API_KEY must be set" in capsys.readouterr().err
    assert not script.OUT.exists()


def test_the_live_scenario_writes_a_per_model_report(live):
    assert live.main(["--category", "normal_ticket", "--model", "a/b"]) == 0
    report = json.loads(live.OUT.read_text())
    entry = report["models"]["a/b"]
    assert entry["summary"]["runs"] == 1 and entry["summary"]["evaluation_passed"] == 1
    assert entry["repeats"] == 1 and report["limits"]


def test_repeats_multiply_the_runs(live):
    live.main(["--category", "normal_ticket", "--repeats", "3", "--model", "a/b"])
    assert json.loads(live.OUT.read_text())["models"]["a/b"]["summary"]["runs"] == 3


def test_models_are_merged_across_invocations(live):
    live.main(["--category", "normal_ticket", "--model", "a/b"])
    live.main(["--category", "normal_ticket", "--model", "c/d"])
    assert set(json.loads(live.OUT.read_text())["models"]) == {"a/b", "c/d"}


def test_a_real_bad_decision_is_counted_and_stopped(live):
    live.main(["--category", "unauthorized_tool", "--model", "a/b"])
    summary = json.loads(live.OUT.read_text())["models"]["a/b"]["summary"]
    assert summary["downstream"] == {"real_bad_decisions": 1, "stopped_same_decision": 1,
                                     "benign_decisions": 0}
    assert summary["direct_violations"] == 1 and summary["harnessed_violations"] == 0
    assert summary["interventions"]["vetoed"] == 1


def test_a_model_that_behaves_is_reported_as_benign_not_as_a_success(live, fake_llm):
    fake_llm.respond = lambda message: decision("create_ticket", subject="Order O-1 not delivered")
    live.main(["--category", "prompt_injection", "--model", "a/b"])
    summary = json.loads(live.OUT.read_text())["models"]["a/b"]["summary"]
    assert summary["downstream"] == {"real_bad_decisions": 0, "stopped_same_decision": 0,
                                     "benign_decisions": 3}


def test_nothing_is_written_when_every_run_fails_in_the_model_step(live, fake_llm, capsys):
    def explode(message):
        raise RuntimeError("boom")

    fake_llm.respond = explode
    assert live.main(["--category", "normal_ticket", "--model", "a/b"]) == 2
    assert not live.OUT.exists() and "Nothing written" in capsys.readouterr().err


def test_the_benchmark_measures_overhead_outside_the_model_and_equivalence(monkeypatch, tmp_path):
    script = _load("run_benchmark", monkeypatch, tmp_path)
    assert script.main(["--runs", "3"]) == 0
    report = json.loads(script.OUT.read_text())
    assert report["overhead"]["runs"] == 3
    assert report["overhead"]["harnessed"]["median_us"] >= 0 and report["limits"]
    equivalence = report["equivalence"]
    assert equivalence["decisions_replayed"] == equivalence["cases"] == 16
    assert equivalence["identical_outcomes"] == 16


def test_the_improvement_cycle_is_recorded_per_model_and_merged(monkeypatch, tmp_path):
    script = _load("run_improvement_cycle", monkeypatch, tmp_path)
    assert script.main(["--model", "a/b"]) == 0
    assert script.main(["--model", "c/d"]) == 0
    report = json.loads(script.OUT.read_text())
    assert set(report["models"]) == {"a/b", "c/d"} and report["note"]
    entry = report["models"]["a/b"]
    assert entry["reference"]["failed_cases"] == ["policy_lookup-1"]
    assert entry["reference"]["apply_with_unauthorised_approver"] == "refused"
    assert entry["core_adapters_gate_the_same_way"] is True


def test_the_live_summary_counts_escalations_to_a_human(live):
    live.main(["--category", "refund_pending", "--category", "refund_approved", "--model", "a/b"])
    summary = json.loads(live.OUT.read_text())["models"]["a/b"]["summary"]
    assert summary["interventions"]["escalated_to_human"] == 2
    assert summary["interventions"]["vetoed"] == 1


def test_the_report_keeps_per_case_detail_including_what_the_model_decided(live):
    live.main(["--category", "unauthorized_tool", "--category", "prompt_injection", "--model", "a/b"])
    by_case = json.loads(live.OUT.read_text())["models"]["a/b"]["summary"]["by_case"]
    assert set(by_case) == {"unauthorized_tool-1", "prompt_injection-1", "prompt_injection-2",
                            "prompt_injection-3"}
    cell = by_case["unauthorized_tool-1"]
    assert cell["decisions"] == {"delete_customer": 1} and cell["vetoed"] == 1
    assert cell["direct_violated"] == 1 and cell["harnessed_violated"] == 0


def test_a_model_error_on_the_direct_path_is_counted_and_listed_not_hidden(live, fake_llm):
    calls = iter(range(100))

    def flaky(message):
        if next(calls) == 0:
            raise RuntimeError("gateway hiccup")
        return decision("create_ticket", subject="x")

    fake_llm.respond = flaky
    live.main(["--category", "normal_ticket", "--model", "a/b"])
    entry = json.loads(live.OUT.read_text())["models"]["a/b"]
    assert entry["summary"]["direct_model_errors"] == 1
    assert [row["id"] for row in entry["notable"]] == ["normal_ticket-1"]
