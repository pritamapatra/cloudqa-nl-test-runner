import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from google import genai
from playwright.sync_api import sync_playwright

from credential_store import load_credentials
from report import write_report
from runner import run


def main() -> int:
    parser = argparse.ArgumentParser(description="CloudQA plain-English test runner")
    parser.add_argument("--url", required=True, help="Starting HTTP(S) URL")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--test", help="Plain-English test case")
    source.add_argument("--test-file", help=".txt or JSON file containing a test")
    parser.add_argument("--headed", action="store_true", help="Show the browser")
    parser.add_argument("--report", default="report.json", help="JSON report path")
    credential_source = parser.add_mutually_exclusive_group()
    credential_source.add_argument(
        "--credentials", help="Explicit flat JSON credential file for authorized demo sites"
    )
    credential_source.add_argument(
        "--credential-env", action="store_true",
        help="Use CLOUDQA_CUSTOMER_USERNAME/PASSWORD for an authorized demo site",
    )
    args = parser.parse_args()

    try:
        url = urlsplit(args.url)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
        ):
            parser.error("--url must be HTTP(S), without embedded credentials")
        # Access the port to reject malformed values before launching a browser.
        url.port
    except ValueError:
        parser.error("--url is invalid")

    test = args.test
    if args.test_file:
        path = Path(args.test_file)
        try:
            content = path.read_text(encoding="utf-8")
            if path.suffix.lower() == ".txt":
                test = content
            elif path.suffix.lower() == ".json":
                data = json.loads(content)
                if not isinstance(data, dict) or set(data) != {"test"}:
                    parser.error("JSON test file must contain only a 'test' field")
                test = data["test"]
            else:
                parser.error("--test-file must use .txt or .json")
        except (OSError, UnicodeError, json.JSONDecodeError):
            parser.error("Cannot read or parse the test file")

    if not isinstance(test, str) or not test.strip():
        parser.error("Test must be a nonblank string")

    result = {
        "verdict": "fail",
        "reason": "Run did not start",
        "elapsed_seconds": 0.0,
        "steps": 0,
        "retries": 0,
        "history": [],
    }

    try:
        load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        credentials = None
        if args.credentials is not None or args.credential_env:
            credentials = load_credentials(
                args.credentials, allowed_origin=args.url
            )
            test = credentials.redact(test)
            print("MODE: Experimental demo credentials; fills bound to starting origin.")
            print("Use placeholders only; never put raw credentials in test instructions.")
        else:
            print("MODE: Public pages only; real credential workflows are not supported.")
        with genai.Client(
            http_options={
                "timeout": 20_000,
                "retry_options": {"attempts": 1},
            }
        ) as client:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=not args.headed)
                try:
                    page = browser.new_page()
                    page.set_default_timeout(5_000)
                    page.set_default_navigation_timeout(10_000)
                    page.goto(
                        args.url, wait_until="domcontentloaded", timeout=10_000
                    )
                    result = run(
                        page, client, test.strip(), model=model,
                        credentials=credentials,
                    )
                finally:
                    browser.close()
    except Exception as exc:
        result["verdict"] = "fail"
        result["reason"] = f"Run failed ({type(exc).__name__}); details suppressed"

    try:
        write_report(result, args.report)
    except Exception as exc:
        print(f"REPORT ERROR: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
