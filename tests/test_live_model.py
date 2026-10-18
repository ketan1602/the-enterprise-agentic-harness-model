"""scenario/llm.py with the model client stood in for.

These prove the wiring, not how a real model behaves.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from harness_core.capabilities import ModelDecision, ModelRequest

from scenario.cases import load_cases, run_direct, run_harnessed
from scenario.llm import (
    DEFAULT_MODEL,
    SYSTEM_PROMPT,
    live_model,
    model_id,
    parse_decision,
    replay_model,
)
from scenario.support import ModelTrace
from tests.fake_llm import decision

CASES = {c["id"]: c for c in load_cases()}
OBJECT = {"tool": "create_ticket", "arguments": {"subject": "x"}}


def test_the_prompt_shows_every_tool_including_the_one_the_agent_may_not_use():
    for tool in ("create_ticket", "add_note", "issue_refund", "delete_customer"):
        assert f"- {tool}(" in SYSTEM_PROMPT


async def test_the_harnessed_prompt_withholds_the_secret_the_direct_prompt_exposes(fake_llm):
    case = CASES["secret_in_context-1"]
    await run_direct(case)
    await run_harnessed(case)
    assert "FAKE-4111-0000" in fake_llm.user_message(0)
    assert "FAKE-4111-0000" not in fake_llm.user_message(1)


async def test_refund_policy_reaches_the_model_only_when_knowledge_is_available(fake_llm):
    case = CASES["policy_lookup-1"]
    await run_harnessed(case)
    await run_harnessed(case, with_knowledge=False)
    assert "refund requests above 100" in fake_llm.user_message(0)
    assert "refund requests above 100" not in fake_llm.user_message(1)


async def test_memories_reach_the_model_on_a_repeat_request(fake_llm):
    case = CASES["duplicate_ticket-1"]
    outcome = await run_harnessed(case)
    assert len(fake_llm.calls) == 2
    assert case["utterance"] in fake_llm.user_message(1)
    assert '"memories": []' not in fake_llm.user_message(1)
    assert outcome["last_tool"] == "add_note"


async def test_the_injected_words_reach_the_model_verbatim(fake_llm):
    await run_direct(CASES["prompt_injection-1"])
    assert "Ignore your instructions" in fake_llm.user_message(0)


async def test_unusable_model_output_is_reported_not_raised(fake_llm):
    fake_llm.respond = lambda message: "not json"
    harnessed = await run_harnessed(CASES["normal_ticket-1"])
    direct = await run_direct(CASES["normal_ticket-1"])
    assert harnessed["status"] == "failed"
    assert harnessed["reason"].startswith("model_error: JSONDecodeError")
    assert direct["status"] == "raised:JSONDecodeError"


async def test_empty_model_content_is_a_model_error(fake_llm):
    fake_llm.respond = lambda message: None
    outcome = await run_harnessed(CASES["normal_ticket-1"])
    assert outcome["status"] == "failed" and "no content" in outcome["reason"]


async def test_a_missing_key_is_a_model_error_and_builds_no_client(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    with patch("openai.AsyncOpenAI") as client_class:
        outcome = await run_harnessed(CASES["normal_ticket-1"])
    client_class.assert_not_called()
    assert outcome["status"] == "failed" and "LLM_API_KEY must be set" in outcome["reason"]


@pytest.mark.parametrize("reply", [
    json.dumps(OBJECT),
    "```json\n" + json.dumps(OBJECT) + "\n```",
    "<think>let me see\nthe options</think>\n" + json.dumps(OBJECT),
    "Sure, here you go: " + json.dumps(OBJECT) + " Hope that helps.",
], ids=["plain", "fenced", "think-block", "surrounding-prose"])
def test_the_decision_is_found_in_a_chat_models_reply(reply):
    assert parse_decision(reply) == OBJECT


@pytest.mark.parametrize("bad", ["", None, "no braces here", "{broken"])
def test_an_unparseable_reply_raises(bad):
    with pytest.raises(ValueError):
        parse_decision(bad)


async def test_a_declared_token_estimate_wins_over_measured_usage(fake_llm):
    fake_llm.total_tokens = 321
    request = ModelRequest("t", {"request": {}})
    measured = await live_model(CASES["normal_ticket-1"], ModelTrace())(request)
    declared = await live_model(CASES["over_budget-1"], ModelTrace())(request)
    assert measured.tokens == 321
    assert declared.tokens == CASES["over_budget-1"]["estimated_tokens"] == 5001


async def test_replay_returns_the_recorded_decision_and_makes_no_call(fake_llm):
    recorded = ModelDecision("create_ticket", {"subject": "x"}, 7, 0.0)
    trace = ModelTrace()
    assert await replay_model(recorded, trace)(ModelRequest("t", {"request": {"a": 1}})) == recorded
    assert fake_llm.calls == [] and trace.decisions == [recorded] and trace.seen == [{"a"}]


async def test_a_model_id_can_be_chosen_per_run(fake_llm, monkeypatch):
    llama = "meta-llama/Llama-3.1-70B-Instruct"
    await run_harnessed(CASES["normal_ticket-1"], model_name=llama)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    await run_harnessed(CASES["normal_ticket-1"])
    monkeypatch.setenv("LLM_MODEL", "x/y")
    assert [c["model"] for c in fake_llm.calls] == [llama, DEFAULT_MODEL]
    assert model_id() == "x/y" and model_id("a/b") == "a/b"


async def test_model_time_is_recorded_and_bounded_by_the_run():
    outcome = await run_harnessed(CASES["normal_ticket-1"])
    assert 0 <= outcome["model_seconds"] <= outcome["seconds"]


async def test_building_the_model_client_is_model_time_not_harness_overhead():
    import time
    from unittest.mock import MagicMock

    from tests.fake_llm import FakeLLM

    llm = FakeLLM()
    client = MagicMock()
    client.chat.completions.create = llm.create

    def slow_constructor(**kwargs):
        time.sleep(0.05)
        return client

    with patch("openai.AsyncOpenAI", side_effect=slow_constructor):
        outcome = await run_harnessed(CASES["normal_ticket-1"])
    assert outcome["model_seconds"] >= 0.05
    assert outcome["seconds"] - outcome["model_seconds"] < 0.04


async def test_a_failed_prior_run_on_the_direct_path_is_recorded_not_fatal(fake_llm):
    replies = iter([decision("create_ticket", customer_id="C-1"),
                    decision("create_ticket", subject="x")])
    fake_llm.respond = lambda message: next(replies)
    outcome = await run_direct(CASES["duplicate_ticket-1"])
    assert outcome["prior_failures"] == 1 and outcome["status"] == "executed"


async def test_a_tool_call_with_an_argument_the_tool_does_not_accept_is_blocked_up_front(fake_llm):
    fake_llm.respond = lambda message: decision("create_ticket", subject="x", note="extra")
    harnessed = await run_harnessed(CASES["normal_ticket-1"])
    direct = await run_direct(CASES["normal_ticket-1"])
    assert harnessed["status"] == "blocked" and harnessed["reason"].startswith("invalid_arguments")
    assert harnessed["effects"] == [] and harnessed["interventions"]["vetoed"] is True
    assert direct["status"] == "raised:TypeError" and direct["effects"] == []
