import json

import pytest
from playwright.sync_api import sync_playwright

from actions import Action
from executor import execute
from observer import observe
from verifier import verify


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch()
        try:
            yield instance
        finally:
            instance.close()


@pytest.fixture
def page(browser):
    instance = browser.new_page()
    instance.set_default_timeout(1_000)
    try:
        yield instance
    finally:
        instance.close()


def test_observer_visible_indexes_labels_and_no_input_values(page):
    page.set_content("""
        <input hidden value="HIDDEN_SENTINEL">
        <label for="name">Display name</label>
        <input id="name" value="INPUT_SENTINEL">
        <button disabled>Unavailable</button>
        <select aria-label="Country">
          <option>Canada</option><option>Japan</option>
        </select>
    """)
    observation = observe(page)
    controls = observation.snapshot["elements"]

    assert [item["index"] for item in controls] == [1, 2, 3]
    assert list(observation.elements) == [1, 2, 3]
    assert controls[0]["name"] == "Display name"
    assert controls[1]["enabled"] is False
    assert controls[2]["name"] == "Country"
    assert controls[2]["options"] == ["Canada", "Japan"]
    serialized = json.dumps(observation.snapshot)
    assert "INPUT_SENTINEL" not in serialized
    assert "HIDDEN_SENTINEL" not in serialized


def test_observer_caps_body_text(page):
    page.set_content("<p>" + "x" * 8_100 + "</p>")
    assert len(observe(page).snapshot["text"]) == 8_000


@pytest.mark.parametrize("change", ["hidden", "disabled"])
def test_executor_rechecks_target_after_observation(page, change):
    page.set_content("<button id='target'>Run</button>")
    observation = observe(page)
    page.locator("#target").evaluate(
        "(element, attribute) => element.setAttribute(attribute, '')",
        change,
    )
    action = Action(action="click", reason="Test stale state", element=1)
    with pytest.raises(ValueError, match="not visible and enabled"):
        execute(page, observation, action)


def test_executor_rejects_unknown_index(page):
    page.set_content("<button>Run</button>")
    action = Action(action="click", reason="Invalid index", element=99)
    with pytest.raises(ValueError, match="Unknown element index"):
        execute(page, observe(page), action)


def test_native_selection_uses_label_not_value(page):
    page.set_content("""
        <select><option value="ca">Canada</option>
        <option value="jp">Japan</option></select>
    """)
    action = Action(
        action="select", reason="Select visible label", element=1, value="Japan"
    )
    result = execute(page, observe(page), action)
    assert result["completed"] is True
    assert page.locator("select").input_value() == "jp"


def test_text_evidence_normalizes_whitespace_and_excludes_hidden_text(page):
    page.set_content("<p>Hello   CloudQA</p><p hidden>Hidden success</p>")
    observation = observe(page)
    visible = Action(
        action="assert", reason="Visible evidence",
        evidence="Hello\nCloudQA", evidence_type="text",
    )
    hidden = Action(
        action="assert", reason="Hidden evidence",
        evidence="Hidden success", evidence_type="text",
    )
    assert verify(page, observation, visible)["ok"] is True
    assert verify(page, observation, hidden)["ok"] is False


def test_url_evidence_requires_exact_match(page):
    page.set_content("<p>Fixture</p>")
    observation = observe(page)
    exact = Action(
        action="assert", reason="Exact URL",
        evidence=page.url, evidence_type="url",
    )
    mismatch = Action(
        action="assert", reason="Different URL",
        evidence=page.url + "#different", evidence_type="url",
    )
    assert verify(page, observation, exact)["ok"] is True
    assert verify(page, observation, mismatch)["ok"] is False


def test_element_evidence_rejects_unknown_and_now_hidden_targets(page):
    page.set_content("<button id='target'>Success</button>")
    observation = observe(page)
    unknown = Action(
        action="assert", reason="Unknown target", element=99,
        evidence="Success", evidence_type="element",
    )
    assert verify(page, observation, unknown)["ok"] is False

    page.locator("#target").evaluate("element => element.hidden = true")
    hidden = Action(
        action="assert", reason="Hidden target", element=1,
        evidence="Success", evidence_type="element",
    )
    assert verify(page, observation, hidden)["ok"] is False


def test_credential_fill_resolves_locally_without_mutating_action(page):
    from credential_store import CredentialStore

    page.set_content("<input type='password' aria-label='Password'>")
    observation = observe(page)
    store = CredentialStore({"customer.password": "SYNTHETIC_PASSWORD_789"})
    action = Action(
        action="fill", reason="Fill synthetic password",
        element=1, value="{{customer.password}}",
    )
    result = execute(page, observation, action, credentials=store)
    assert page.locator("input").input_value() == "SYNTHETIC_PASSWORD_789"
    assert action.value == "{{customer.password}}"
    assert "SYNTHETIC_PASSWORD_789" not in json.dumps(result)


def test_credential_placeholder_without_store_fails_before_fill(page):
    page.set_content("<input aria-label='Password'>")
    action = Action(
        action="fill", reason="Missing credential store",
        element=1, value="{{customer.password}}",
    )
    with pytest.raises(ValueError, match="require a credential store"):
        execute(page, observe(page), action)
    assert page.locator("input").input_value() == ""


def test_credential_pipeline_redacts_echoed_secret(page, tmp_path, capsys):
    from credential_store import CredentialStore
    from report import write_report
    from runner import run

    secret = "SYNTHETIC_PIPELINE_PASSWORD_123"
    store = CredentialStore({"customer.password": secret})
    page.set_content("""
        <label for="password">Password</label>
        <input id="password" type="password">
        <button onclick="
            document.getElementById('result').innerText =
            'Submitted ' + document.getElementById('password').value;
        ">Submit</button>
        <p id="result"></p>
    """)
    contexts = []

    def planner(client, *, snapshot, history, **kwargs):
        context = json.dumps({"snapshot": snapshot, "history": history, **kwargs})
        contexts.append(context)
        assert secret not in context

        if not history:
            index = next(
                item["index"] for item in snapshot["elements"]
                if item["name"] == "Password"
            )
            return Action(
                action="fill", reason="Use synthetic placeholder",
                element=index, value="{{customer.password}}",
            )
        if len(history) == 1:
            index = next(
                item["index"] for item in snapshot["elements"]
                if item["name"] == "Submit"
            )
            return Action(action="click", reason="Submit fixture", element=index)
        assert "[REDACTED]" in snapshot["text"]
        return Action(
            action="finish", reason="Submission text is visible",
            verdict="pass", evidence="Submitted", evidence_type="text",
        )

    result = run(
        page, None, "Submit the synthetic password and verify Submitted",
        planner=planner, credentials=store,
    )
    assert result["verdict"] == "pass"
    assert len(contexts) == 3
    assert page.locator("#password").input_value() == secret
    assert secret in page.locator("#result").inner_text()

    destination = tmp_path / "synthetic-report.json"
    write_report(result, str(destination))
    assert secret not in destination.read_text()
    assert secret not in capsys.readouterr().out
    assert "{{customer.password}}" in destination.read_text()


@pytest.mark.parametrize("url", [
    "https://user:synthetic@example.com/",
    "https://example.com:invalid/",
])
def test_executor_rejects_unsafe_navigation_before_request(page, url):
    page.set_content("<p>Unchanged fixture</p>")
    original_url = page.url
    action = Action(action="goto", reason="Synthetic rejection check", value=url)
    with pytest.raises(ValueError):
        execute(page, observe(page), action)
    assert page.url == original_url
