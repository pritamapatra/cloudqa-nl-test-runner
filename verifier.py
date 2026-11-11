from playwright.sync_api import Page

from actions import Action
from observer import Observation


def normalize(text: str) -> str:
    return " ".join(text.split())


def verify(page: Page, observation: Observation, action: Action) -> dict:
    if action.evidence_type is None or not action.evidence:
        raise ValueError("Verification requires typed evidence")

    expected = normalize(action.evidence)
    if not expected:
        raise ValueError("Evidence must not be blank")

    if action.evidence_type == "url":
        actual = page.url
        ok = actual == action.evidence.strip()
    elif action.evidence_type == "text":
        actual = page.locator("body").inner_text()
        ok = expected in normalize(actual)
    else:
        handle = observation.elements.get(action.element)
        if handle is None:
            return {"ok": False, "type": "element", "expected": action.evidence,
                    "observed": "", "error": "Unknown element index"}
        if not handle.is_visible():
            return {"ok": False, "type": "element", "expected": action.evidence,
                    "observed": "", "error": "Element is not visible"}
        actual = handle.inner_text()
        ok = expected in normalize(actual)

    return {
        "ok": ok,
        "type": action.evidence_type,
        "expected": action.evidence,
        "observed": action.evidence if ok else actual[:500],
    }
