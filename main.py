import argparse
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser(description="CloudQA plain-English test runner")
    parser.add_argument("--url", required=True, help="Starting HTTP(S) URL")
    parser.add_argument("--test", required=True, help="Plain-English test case")
    parser.add_argument("--headed", action="store_true", help="Show the browser")
    args = parser.parse_args()

    url = urlsplit(args.url)
    if url.scheme not in {"http", "https"} or not url.hostname:
        parser.error("--url must be an absolute HTTP(S) URL")
    if not args.test.strip():
        parser.error("--test must not be empty")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            try:
                page = browser.new_page()
                page.goto(args.url, wait_until="domcontentloaded", timeout=30_000)
                print(f"URL: {page.url}")
                print(f"TITLE: {page.title()}")
                print("STATUS: Navigation complete; test execution is not implemented.")
            finally:
                browser.close()
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
