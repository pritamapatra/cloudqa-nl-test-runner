from urllib.parse import urlsplit

from playwright.sync_api import Page

from actions import Action
from observer import Observation


def execute(page: Page, observation: Observation, action: Action) -> dict:
    if action.action == "goto":
        url = urlsplit(action.value)
        if url.scheme not in {"http", "https"} or not url.hostname:
            raise ValueError("goto requires an absolute HTTP(S) URL")
        page.goto(action.value, wait_until="domcontentloaded", timeout=10_000)
        return {"action": "goto", "url": page.url}

    if action.action == "wait":
        page.wait_for_timeout(500)
        return {"action": "wait", "milliseconds": 500}

    if action.action in {"assert", "finish"}:
        raise ValueError("Assertions and verdicts must be handled by the verifier/runner")

    handle = observation.elements.get(action.element)
    if handle is None:
        raise ValueError(f"Unknown element index: {action.element}")
    if not handle.is_visible() or not handle.is_enabled():
        raise ValueError("Target element is not visible and enabled")

    if action.action == "click":
        handle.click(timeout=5_000)
    elif action.action == "fill":
        handle.fill(action.value, timeout=5_000)
    elif action.action == "select":
        handle.select_option(label=action.value, timeout=5_000)
    elif action.action == "press":
        handle.press(action.value, timeout=5_000)
    else:
        raise ValueError(f"Unsupported browser action: {action.action}")

    return {"action": action.action, "element": action.element, "completed": True}
