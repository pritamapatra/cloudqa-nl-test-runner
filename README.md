# CloudQA Natural-Language Test Runner

Python + Playwright browser testing with a Gemini Interactions action planner.

## Current status

- Browser observation, strict action validation, execution, evidence verification,
  bounded runner, console output, and JSON reports are implemented.
- 96 automated tests passed locally, including a real Chromium pipeline test.
- Live Gemini completion is NOT verified: recent minimal and structured requests
  returned HTTP 503 or timed out.
- The real-browser automated test uses a scripted planner, not Gemini.
- Public pages by default; explicit experimental credential opt-in for authorized
  demo accounts only. Production accounts and sensitive sites are unsupported.

## Setup

Use a Python environment compatible with the pinned dependencies. Local
development used Python 3.14.

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt
    python -m playwright install chromium

Configure a supported Gemini API-key environment variable privately, such as
GEMINI_API_KEY. A local .env file is loaded explicitly and is ignored by Git.

The default model is gemini-3.8-flash. GEMINI_MODEL overrides it. This model was
used in an earlier successful SDK smoke test; current live calls are blocked.
Never commit keys or put raw credentials in test instructions or URLs.
Credential mode redacts known values, not arbitrary sensitive page data.

## Run

    .venv/bin/python main.py \
      --url https://example.com \
      --test "Verify that the page displays Example Domain." \
      --report reports/example.json

Use --headed for a visible browser.

Alternatively, use --test-file case.txt, containing a plain-English test, or
--test-file case.json with exactly one field:

    {"test": "Verify that the page displays Example Domain."}

--test and --test-file are mutually exclusive.

Exit code 0 means verified PASS; 1 means FAIL or a runtime/reporting error.
Invalid CLI arguments exit through argparse, normally with code 2.

## Execution

Each step observes visible controls, asks Gemini for one structured Action,
and executes or verifies it. Supported actions:

- goto, click, fill, select by native option label, press
- wait: fixed 500 ms
- assert: verify live text, exact URL, or indexed element text
- finish: pass/fail; PASS requires live evidence verification

Limits: 15 planning steps, a 60-second loop budget, and at most two recovery
attempts shared across failures. Rate limits use bounded exponential backoff
with jitter within that allowance and the remaining loop budget. SDK retries are disabled
in the CLI client; its timeout is 20,000 ms.

The loop budget is cooperative, not a hard process deadline. Browser startup,
initial navigation, and cleanup are outside it. In-flight operations can overrun.
Each planner call receives at most 20 seconds or the remaining loop budget.
Actual SDK timing must still be verified against the live service.

## Tests

    .venv/bin/python -m pytest -q

Tests cover planner request construction, invalid output, rate-limit/error
handling, runner limits, evidence rejection, real-browser fill/click, and report
serialization. Automated tests do not contact Gemini.

See NOTES.md for limitations and remaining work.

## Experimental demo credentials

Use only authorized, disposable demo accounts. Live Gemini login is not yet
verified. Do not use production credentials or sensitive pages.

Opt in with either:

- `--credentials credentials.json`: explicit flat JSON file.
- `--credential-env`: environment-only credential loading.

Flat JSON format, showing synthetic values only:

    {"customer.username":"SYNTHETIC_USER","customer.password":"SYNTHETIC_PASSWORD"}

The explicit environment variables `CLOUDQA_CUSTOMER_USERNAME` and
`CLOUDQA_CUSTOMER_PASSWORD` override matching file entries. The existing local
.env loading also makes these variables available. Neither credential mode is
enabled automatically.

In a test, use `{{customer.username}}` and `{{customer.password}}` as complete
fill values. Never put raw credentials in the test. Credentials embedded in
natural-language test text are not parsed or supported.

Credential placeholders resolve locally, only for fill actions. CLI credential
fills require the starting URL's scheme, hostname, and effective port; a
cross-origin login redirect is unsupported. Known credential values are redacted
from planner test text, observations, history, and returned reports.

Redaction replaces exact known strings only. It does not cover encoded,
transformed, split, or unknown secrets, or arbitrary PII. It does not sanitize
the website itself. Same-origin pages, scripts, form submissions, and model-chosen
actions can still misuse credentials. Origin binding is not a security sandbox.
Only the conventional credentials.json filename is ignored by Git; protect
custom credential paths yourself. Never commit any credential file.

## Reproducible scripted demonstration

    .venv/bin/python demo_scripted.py --headed

Omit --headed for a headless run. No API key or Gemini call is needed.
The synthetic fixture demonstrates fill -> click -> live evidence verification,
then rejection of deliberately fabricated evidence. Both reports under reports/
identify scripted-planner mode. Expected console verdicts are PASS, then FAIL;
the demo process exits 0 only when both expected results are confirmed.

This is not a live natural-language acceptance test or proof of Gemini operation.
