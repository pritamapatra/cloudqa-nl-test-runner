# Implementation notes and limitations

## Verified locally

- 52 pytest tests passed.
- A real Chromium fixture completed fill -> click -> live text verification.
- A scripted false PASS was rejected by the live verifier.
- Console and JSON reporting are integrated.
- Public example.com CLI runs produced failure reports with exit code 1.
- Recent Gemini calls returned HTTP 503; a minimal request also failed.
- An earlier default-retry request lasted 126.5 seconds despite timeout=15.
- The CLI now sets retry_options.attempts=1, mapped by the installed SDK to
  zero retries. Subsequent observed 503 failures returned much sooner.

## Important boundaries

- No verified live observe-plan-act success yet.
- Planner schema acceptance by the service remains unverified.
- Evidence matching is not proof that every requested test condition is met.
  The model chooses evidence and judges overall completion.
- Text evidence uses normalized substrings; URL evidence uses exact matching.
- Element evidence checks visible element inner_text, not input values.
- Observation names are approximate, not a complete accessibility-tree model.
- No deliberate iframe or shadow-root traversal.
- Interactive discovery is selector-based; custom controls may be missed.
- Observation body text is limited to 8,000 characters.
- Observations do not intentionally collect input values, but this is NOT
  complete credential or PII redaction.
- No credential placeholders, secure credential injection, or comprehensive
  redaction. Do not run against real accounts or sensitive pages.
- Page content is untrusted. Prompt instructions reduce but do not eliminate
  prompt-injection risk. No sandbox or robust action-policy enforcement exists.
- Navigation is HTTP(S)-only, but arbitrary page navigation and clicks remain
  possible. Use only sites and actions you are authorized to test.
- Reports can include action values and evidence; treat them as potentially
  sensitive. Generated reports are ignored by Git.
- Loop timing is cooperative. Individual calls may overrun; initialization,
  navigation, and cleanup are outside the loop budget.
- Recovery attempts are bounded but have no backoff policy.
- Persisted CLI tests cover invalid arguments, text/JSON test files,
  sanitized startup failures, and report serialization.

## Remaining work

1. Resolve live Gemini availability and verify structured-output compatibility.
2. Add tested credential placeholders/loading/redaction before real login use.
3. Verify positive and negative live tests across multiple authorized sites.
4. Strengthen task-completion verification and browser action safety.
5. Expand persisted observer/executor/verifier edge-case tests.
6. Packaging review and demonstration video.

## Fresh-clone installation verification

On November 12, 2026, commit `526280c` was verified from a fresh clone
using a newly created Python 3.14.2 virtual environment:

- Installed dependencies from requirements.txt; pip check found no broken requirements.
- Ran Playwright's Chromium installation command successfully.
- All 52 automated tests passed in 5.79 seconds.
- CLI --help succeeded; the working tree remained clean.
- Package downloads and the existing browser cache were reused.
- No .env was copied and no Gemini calls were made during this check.
- This verifies local installation and offline tests, not live Gemini operation.
