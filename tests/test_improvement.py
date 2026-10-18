"""Evaluation and Learning in the scenario: degrade, score, propose, gate."""
from __future__ import annotations

import pytest

from scenario.improve import improvement_cycle


@pytest.fixture
async def reference():
    return await improvement_cycle("reference")


async def test_evaluation_catches_the_regression_that_no_control_flags(reference):
    assert reference["baseline_passed"] == reference["cases"]
    assert reference["failed_cases"] == ["policy_lookup-1"]
    assert reference["degraded_passed"] == reference["cases"] - 1
    assert reference["violations_while_degraded"] == 0


async def test_learning_proposes_but_only_an_authorised_approver_can_apply(reference):
    assert reference["proposal_status"] == "proposed"
    assert reference["apply_without_approval"] == "refused"
    assert reference["apply_with_unauthorised_approver"] == "refused"
    assert reference["apply_with_authorised_approver"] == "applied"
    assert reference["improvements_recorded"] == 1


async def test_core_adapters_reach_the_same_result(reference):
    assert await improvement_cycle("core") == reference
