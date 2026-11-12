from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import runner
from actions import Action
from llm import PlannerRateLimitError


def finish(verdict="pass"):
    fields = {
        "action": "finish",
        "reason": "Check completed",
        "verdict": verdict,
    }
    if verdict == "pass":
        fields.update(evidence="Welcome", evidence_type="text")
    return Action(**fields)


@pytest.fixture
def environment(monkeypatch):
    observation = SimpleNamespace(
        snapshot={"text": "Welcome", "elements": []}, elements={}
    )
    observe = Mock(return_value=observation)
    execute = Mock(return_value={"completed": True})
    verify = Mock(return_value={"ok": True})
    monkeypatch.setattr(runner, "observe", observe)
    monkeypatch.setattr(runner, "execute", execute)
    monkeypatch.setattr(runner, "verify", verify)
    return SimpleNamespace(observe=observe, execute=execute, verify=verify)


def run(planner, **kwargs):
    return runner.run(
        object(), object(), "Verify Welcome", planner=planner, **kwargs
    )


def test_pass_requires_verification(environment):
    planner = Mock(return_value=finish())
    result = run(planner)
    assert result["verdict"] == "pass"
    environment.verify.assert_called_once()
    assert result["steps"] == 1


def test_failed_evidence_cannot_pass(environment):
    environment.verify.return_value = {"ok": False}
    result = run(Mock(return_value=finish()))
    assert result["verdict"] == "fail"
    assert result["retries"] == 2
    assert environment.verify.call_count == 3


def test_explicit_failure_skips_verification(environment):
    result = run(Mock(return_value=finish("fail")))
    assert result["verdict"] == "fail"
    environment.verify.assert_not_called()


def test_action_then_verified_finish(environment):
    planner = Mock(side_effect=[
        Action(action="click", reason="Continue", element=1),
        finish(),
    ])
    result = run(planner)
    assert result["verdict"] == "pass"
    environment.execute.assert_called_once()
    assert planner.call_args.kwargs["history"][0]["result"]["completed"]


def test_step_limit(environment):
    planner = Mock(return_value=Action(action="wait", reason="Wait"))
    result = run(planner, max_steps=2)
    assert result["verdict"] == "fail"
    assert result["steps"] == 2
    assert "Step limit" in result["reason"]


def test_rate_limit_stops_immediately(environment):
    planner = Mock(side_effect=PlannerRateLimitError("private"))
    result = run(planner)
    assert result["verdict"] == "fail"
    planner.assert_called_once()
    assert "private" not in str(result)


def test_repeated_errors_are_bounded_and_sanitized(environment):
    planner = Mock(side_effect=RuntimeError("PRIVATE_MARKER"))
    result = run(planner)
    assert result["verdict"] == "fail"
    assert planner.call_count == 3
    assert result["retries"] == 2
    assert "PRIVATE_MARKER" not in str(result)


def test_budget_expiry_prevents_execution(environment, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(runner.time, "monotonic", lambda: clock[0])

    def slow_planner(*args, **kwargs):
        clock[0] = 61.0
        return Action(action="click", reason="Continue", element=1)

    result = run(slow_planner)
    assert result["verdict"] == "fail"
    assert "Time budget" in result["reason"]
    environment.execute.assert_not_called()


def test_assert_alone_is_not_completion(environment):
    planner = Mock(return_value=Action(
        action="assert",
        reason="Check text",
        evidence="Welcome",
        evidence_type="text",
    ))
    result = run(planner, max_steps=1)
    assert result["verdict"] == "fail"
    assert "Step limit" in result["reason"]
