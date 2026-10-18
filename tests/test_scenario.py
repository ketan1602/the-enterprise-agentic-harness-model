"""The support scenario. The model is the stand-in in tests/fake_llm.py, so no API calls."""
from __future__ import annotations

import pytest

from scenario.cases import load_cases, matches, run_case, run_direct, run_harnessed
from tests.fake_llm import decision

CASES = load_cases()
BY_ID = {c["id"]: c for c in CASES}
VIOLATION_CASES = [c for c in CASES if c["violation"]]
DOWNSTREAM = [c for c in CASES if c["control"] == "downstream"]
TOOLS = ("create_ticket", "add_note", "issue_refund", "delete_customer")


def test_case_file_is_well_formed():
    assert len(CASES) == 16 and len(BY_ID) == 16
    assert len(VIOLATION_CASES) == 12
    assert {c["control"] for c in CASES} == {"downstream", "upstream", "none"}


def test_the_customers_words_never_name_a_tool():
    for case in (c for c in CASES if c["category"] != "prompt_injection"):
        assert not any(tool in case["utterance"] for tool in TOOLS), case["id"]


def test_injection_variants_name_the_tool_because_that_is_the_attack():
    named = [c["id"] for c in CASES if c["category"] == "prompt_injection"
             and "delete_customer" in c["utterance"]]
    assert named == ["prompt_injection-2", "prompt_injection-3"]


@pytest.mark.parametrize("adapters", ["reference", "core"])
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
async def test_every_case_meets_its_expectation(case, adapters):
    result = await run_case(case, adapters)
    assert matches(case, result["harnessed"]), (case["expected"], result["harnessed"]["status"])


@pytest.mark.parametrize("adapters", ["reference", "core"])
@pytest.mark.parametrize("case", VIOLATION_CASES, ids=lambda c: c["id"])
async def test_harness_prevents_every_violation(case, adapters):
    assert (await run_case(case, adapters))["harnessed"]["violated"] is False


@pytest.mark.parametrize("case", VIOLATION_CASES, ids=lambda c: c["id"])
async def test_the_direct_path_commits_every_violation(case):
    assert (await run_direct(case))["violated"] is True


@pytest.mark.parametrize("case", [c for c in DOWNSTREAM if c["id"] != "suspended_agent-1"],
                         ids=lambda c: c["id"])
async def test_downstream_controls_judge_the_same_decision(case, fake_llm):
    result = await run_case(case)
    assert result["paired"] is True
    assert result["harnessed"]["decision"] == result["direct"]["decision"]
    assert len(fake_llm.calls) == 1


async def test_a_suspended_agent_is_stopped_before_the_model_is_consulted(fake_llm):
    result = await run_case(BY_ID["suspended_agent-1"])
    assert result["paired"] is True and result["harnessed"]["status"] == "blocked"
    assert result["harnessed"]["decision"] is None and result["harnessed"]["effects"] == []
    assert len(fake_llm.calls) == 1


@pytest.mark.parametrize("case", [c for c in CASES if c["control"] != "downstream"],
                         ids=lambda c: c["id"])
async def test_other_controls_ask_the_model_on_each_path(case):
    assert (await run_case(case))["paired"] is False


@pytest.mark.parametrize("case", [c for c in CASES if c["expected"].get("status") == "blocked"],
                         ids=lambda c: c["id"])
async def test_blocked_runs_execute_nothing(case):
    assert (await run_harnessed(case))["effects"] == []


async def test_knowledge_changes_the_decision():
    case = BY_ID["policy_lookup-1"]
    with_policy = await run_harnessed(case)
    without = await run_harnessed(case, with_knowledge=False)
    assert with_policy["last_tool"] == "create_ticket" and with_policy["verdict"]["passed"]
    assert without["status"] == "awaiting_approval" and without["verdict"]["passed"] is False
    assert without["violated"] is False


async def test_a_model_that_resists_the_injection_gives_the_harness_nothing_to_stop(fake_llm):
    fake_llm.respond = lambda message: decision("create_ticket", subject="Order O-1 not delivered")
    result = await run_case(BY_ID["prompt_injection-1"])
    assert result["paired"] is True and result["direct"]["violated"] is False
    assert result["harnessed"]["interventions"]["vetoed"] is False


async def test_the_harness_records_what_it_did():
    assert (await run_harnessed(BY_ID["unauthorized_tool-1"], replay=(
        await run_direct(BY_ID["unauthorized_tool-1"]))["decision"]))["interventions"]["vetoed"]
    assert (await run_harnessed(BY_ID["secret_in_context-1"]))["interventions"]["fields_stripped"] == 3
    assert (await run_harnessed(BY_ID["transient_failure-1"]))["interventions"]["retried"] is True
    quiet = (await run_harnessed(BY_ID["normal_ticket-1"]))["interventions"]
    assert quiet == {"vetoed": False, "escalated_to_human": False, "fields_stripped": 0,
                     "retried": False}


async def test_a_normal_refund_under_the_limit_passes_the_gate():
    outcome = await run_harnessed(BY_ID["refund_small-1"])
    assert outcome["status"] == "completed" and outcome["last_tool"] == "issue_refund"


@pytest.mark.parametrize("adapters", ["reference", "core"])
async def test_the_verdict_names_the_mismatch(adapters):
    wrong = {**BY_ID["unauthorized_tool-1"], "expected": {"status": "completed"}}
    verdict = (await run_case(wrong, adapters))["harnessed"]["verdict"]
    assert verdict["passed"] is False and verdict["mismatches"] == ["status"]


async def test_the_tool_harness_is_what_stops_an_ungranted_tool():
    case = BY_ID["unauthorized_tool-1"]
    direct = await run_direct(case)
    harnessed = await run_harnessed(case, replay=direct["decision"])
    assert harnessed["status"] == "blocked" and harnessed["reason"] == "tool_not_allowed:delete_customer"
    assert harnessed["effects"] == [] and harnessed["interventions"]["vetoed"] is True


async def test_an_approved_refund_pauses_for_a_human_then_executes():
    result = await run_case(BY_ID["refund_approved-1"])
    harnessed = result["harnessed"]
    assert result["paired"] is True and harnessed["status"] == "completed"
    assert harnessed["effects"] == [{"tool": "issue_refund", "order_id": "O-1", "amount": 150.0}]
    assert harnessed["human"] == {"approver": "supervisor-1", "approve": True, "outcome": "completed"}
    assert harnessed["interventions"]["escalated_to_human"] is True
    assert [e for e in harnessed["events"] if e.startswith("run.a")] == [
        "run.awaiting_approval", "run.approved"]


async def test_a_rejected_refund_never_executes():
    harnessed = (await run_case(BY_ID["refund_rejected-1"]))["harnessed"]
    assert harnessed["status"] == "rejected" and harnessed["effects"] == []
    assert harnessed["verdict"]["passed"] is True and harnessed["interventions"]["vetoed"] is True


async def test_an_unauthorised_approver_cannot_release_a_refund():
    harnessed = (await run_case(BY_ID["refund_bad_approver-1"]))["harnessed"]
    assert harnessed["status"] == "awaiting_approval" and harnessed["reason"] == "approver_not_authorised"
    assert harnessed["effects"] == [] and harnessed["verdict"]["passed"] is True


async def test_a_pending_refund_with_no_human_stays_paused():
    harnessed = (await run_case(BY_ID["refund_pending-1"]))["harnessed"]
    assert harnessed["status"] == "awaiting_approval" and harnessed["human"] is None


@pytest.mark.parametrize("case", [c for c in CASES if c["category"] == "prompt_injection"],
                         ids=lambda c: c["id"])
async def test_every_injection_variant_is_stopped_when_the_model_obeys(case):
    result = await run_case(case)
    assert result["direct"]["violated"] is True and result["harnessed"]["violated"] is False
    assert result["harnessed"]["status"] == "blocked"
