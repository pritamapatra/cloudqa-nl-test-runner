"""Synthetic browser demonstration, not a live Gemini acceptance test."""

import argparse

from playwright.sync_api import sync_playwright

from actions import Action
from report import write_report
from runner import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    print("DEMO MODE: Scripted planner; real Chromium; no Gemini or credentials.")

    def positive_planner(client, *, snapshot, history, **kwargs):
        if len(history) < 2:
            name = "Name" if not history else "Submit"
            index = next(
                item["index"] for item in snapshot["elements"]
                if item["name"] == name
            )
            if not history:
                return Action(
                    action="fill", reason="Enter synthetic name",
                    element=index, value="CloudQA",
                )
            return Action(action="click", reason="Submit fixture", element=index)
        return Action(
            action="finish", reason="Greeting verified against live page",
            verdict="pass", evidence="Hello CloudQA", evidence_type="text",
        )

    def negative_planner(*args, **kwargs):
        return Action(
            action="finish", reason="Deliberately fabricated demo claim",
            verdict="pass", evidence="THIS TEXT DOES NOT EXIST",
            evidence_type="text",
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not args.headed, slow_mo=400 if args.headed else 0,
        )
        try:
            page = browser.new_page()
            page.set_content("""
                <h1>CloudQA scripted browser demonstration</h1>
                <p>Scripted planner. No Gemini. Synthetic data only.</p>
                <label for="name">Name</label><input id="name">
                <button onclick="
                    document.getElementById('result').innerText =
                    'Hello ' + document.getElementById('name').value;
                ">Submit</button>
                <p id="result"></p>
            """)
            for name, planner, expected in (
                ("positive", positive_planner, "pass"),
                ("negative", negative_planner, "fail"),
            ):
                result = run(
                    page, None, "Demonstrate visible greeting verification",
                    planner=planner, max_retries=0,
                )
                result["demo_mode"] = "scripted planner; real Chromium; no Gemini"
                write_report(result, f"reports/demo-scripted-{name}.json")
                if result["verdict"] != expected:
                    raise RuntimeError(f"Unexpected {name} demo result")
                if name == "negative" and result["history"][0]["result"]["ok"] is not False:
                    raise RuntimeError("Fabricated evidence was not rejected")
            print("EXPECTED RESULTS VERIFIED: positive PASS; fabricated evidence FAIL.")
            if args.headed:
                page.wait_for_timeout(5_000)
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
