import json

from playwright.sync_api import sync_playwright

from actions import Action
from report import write_report
from runner import run


def test_real_browser_pipeline(tmp_path):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_default_timeout(2_000)
            page.set_content("""
                <label for="name">Name</label>
                <input id="name">
                <button onclick="
                    document.getElementById('result').innerText =
                    'Hello ' + document.getElementById('name').value;
                ">Submit</button>
                <p id="result"></p>
            """)

            def planner(client, *, snapshot, history, **kwargs):
                if len(history) == 0:
                    index = next(
                        item["index"] for item in snapshot["elements"]
                        if item["tag"] == "input" and item["name"] == "Name"
                    )
                    return Action(
                        action="fill", reason="Enter fixture name",
                        element=index, value="CloudQA",
                    )
                if len(history) == 1:
                    index = next(
                        item["index"] for item in snapshot["elements"]
                        if item["tag"] == "button" and item["name"] == "Submit"
                    )
                    return Action(
                        action="click", reason="Submit fixture", element=index
                    )
                return Action(
                    action="finish", reason="Greeting is visible",
                    verdict="pass", evidence="Hello CloudQA",
                    evidence_type="text",
                )

            result = run(
                page, None, "Enter CloudQA and verify the greeting",
                planner=planner,
            )
            assert result["verdict"] == "pass"
            assert result["steps"] == 3
            assert page.locator("#name").input_value() == "CloudQA"

            report_path = tmp_path / "report.json"
            write_report(result, str(report_path))
            saved = json.loads(report_path.read_text())
            assert saved["history"][-1]["result"]["ok"] is True

            def false_pass(*args, **kwargs):
                return Action(
                    action="finish", reason="Incorrect claim",
                    verdict="pass", evidence="THIS TEXT DOES NOT EXIST",
                    evidence_type="text",
                )

            negative = run(
                page, None, "Verify absent text",
                planner=false_pass, max_retries=0,
            )
            assert negative["verdict"] == "fail"
            assert negative["history"][0]["result"]["ok"] is False
        finally:
            browser.close()
