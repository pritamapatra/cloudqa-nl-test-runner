import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from actions import Action
from llm import PlannerError, PlannerRateLimitError, plan


def make_client(text=None, error=None):
    create = Mock(
        return_value=SimpleNamespace(output_text=text),
        side_effect=error,
    )
    return SimpleNamespace(interactions=SimpleNamespace(create=create))


def invoke(client, **overrides):
    arguments = {
        "test": "Click Continue",
        "snapshot": {"url": "https://example.com", "elements": []},
        "history": [],
    }
    arguments.update(overrides)
    return plan(client, **arguments)


def test_valid_action_and_request():
    client = make_client(json.dumps({
        "action": "click", "reason": "Continue the test", "element": 1,
    }))
    action = invoke(client)
    assert isinstance(action, Action)
    assert action.action == "click"
    assert action.element == 1

    client.interactions.create.assert_called_once()
    request = client.interactions.create.call_args.kwargs
    assert request["model"] == "gemini-3.8-flash"
    assert request["store"] is False
    assert request["stream"] is False
    assert request["timeout"] == 20.0
    assert request["response_format"] == {
        "type": "text",
        "mime_type": "application/json",
        "schema": Action.model_json_schema(),
    }
    payload = json.loads(request["input"])
    assert payload["test"] == "Click Continue"
    assert payload["history"] == []


@pytest.mark.parametrize("text", [
    None,
    "",
    " ",
    "not JSON",
    '{"action":"click","reason":"Click"}',
    '{"action":"finish","reason":"Done","verdict":"pass"}',
    '{"action":"wait","reason":"Wait","unexpected":true}',
    '{"action":"click","reason":"Click","element":true}',
])
def test_invalid_output_rejected(text):
    with pytest.raises(PlannerError):
        invoke(make_client(text))


@pytest.mark.parametrize("location", ["code", "status_code", "response"])
def test_rate_limit_has_no_retry(location):
    error = RuntimeError("PRIVATE_MARKER")
    if location == "response":
        error.response = SimpleNamespace(status_code=429)
    else:
        setattr(error, location, 429)
    client = make_client(error=error)

    with pytest.raises(PlannerRateLimitError) as caught:
        invoke(client)
    assert "PRIVATE_MARKER" not in str(caught.value)
    client.interactions.create.assert_called_once()


def test_other_api_error_is_sanitized():
    client = make_client(error=RuntimeError("PRIVATE_MARKER"))
    with pytest.raises(PlannerError) as caught:
        invoke(client)
    assert not isinstance(caught.value, PlannerRateLimitError)
    assert "PRIVATE_MARKER" not in str(caught.value)
    client.interactions.create.assert_called_once()


@pytest.mark.parametrize("overrides", [
    {"test": " "},
    {"model": " "},
    {"timeout": 0},
    {"timeout": 61},
    {"timeout": float("nan")},
])
def test_bad_arguments_do_not_call_api(overrides):
    client = make_client()
    with pytest.raises(ValueError):
        invoke(client, **overrides)
    client.interactions.create.assert_not_called()
