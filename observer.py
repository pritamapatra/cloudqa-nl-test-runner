from dataclasses import dataclass
from typing import Any

from playwright.sync_api import ElementHandle, Page


@dataclass
class Observation:
    snapshot: dict[str, Any]
    elements: dict[int, ElementHandle]


def observe(page: Page) -> Observation:
    handles = page.query_selector_all(
        "a[href], button, input, textarea, select, "
        "[role='button'], [role='link'], [role='combobox'], "
        "[role='checkbox'], [role='radio'], [contenteditable='true']"
    )
    elements = {}
    controls = []

    for handle in handles:
        if not handle.is_visible():
            continue
        index = len(elements) + 1
        metadata = handle.evaluate("""e => {
            const text = n => (n?.innerText || n?.textContent || '').trim();
            const ids = (e.getAttribute('aria-labelledby') || '').split(/\\s+/).filter(Boolean);
            const labelledby = ids.map(id => text(document.getElementById(id))).join(' ');
            const labels = Array.from(e.labels || []).map(text).join(' ');
            return {
                tag: e.tagName.toLowerCase(),
                role: e.getAttribute('role') || '',
                type: e.getAttribute('type') || '',
                name: (labelledby || e.getAttribute('aria-label') ||
                       labels || e.getAttribute('placeholder') ||
                       e.getAttribute('title') ||
                       (e.tagName === 'INPUT' || e.tagName === 'TEXTAREA' ? '' : text(e))).slice(0, 200),
                options: e.tagName === 'SELECT'
                    ? Array.from(e.options).slice(0, 50).map(o => text(o)) : []
            };
        }""")
        metadata["index"] = index
        metadata["enabled"] = handle.is_enabled()
        elements[index] = handle
        controls.append(metadata)

    return Observation(
        snapshot={
            "url": page.url,
            "title": page.title(),
            "text": page.locator("body").inner_text()[:8000],
            "elements": controls,
        },
        elements=elements,
    )
