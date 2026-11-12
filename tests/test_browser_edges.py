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
