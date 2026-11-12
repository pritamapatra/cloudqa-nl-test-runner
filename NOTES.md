# Implementation notes and limitations

## Verified locally

- 96 pytest tests passed.
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
- Experimental credential placeholders, explicit JSON/environment loading,
  local fill resolution, and known-value context/report redaction are tested.
- CLI credential fills are bound to the starting origin. This is not a sandbox;
  same-origin scripts and form submissions can still expose credentials.
- No comprehensive redaction or production credential safety guarantee.
  Do not run against production accounts or sensitive pages.
- Page content is untrusted. Prompt instructions reduce but do not eliminate
  prompt-injection risk. No sandbox or robust action-policy enforcement exists.
- Navigation is HTTP(S)-only, but arbitrary page navigation and clicks remain
  possible. Use only sites and actions you are authorized to test.
- Reports can include action values and evidence; treat them as potentially
  sensitive. Generated reports are ignored by Git.
- Loop timing is cooperative. Individual calls may overrun; initialization,
  navigation, and cleanup are outside the loop budget.
- Rate-limit recovery uses exponential backoff with 0-0.25 seconds of jitter,
  sharing the maximum two recovery retries across failures. Backoff is skipped
  when the remaining budget or step limit prevents another attempt.
- Other planner/action failures have bounded recovery without backoff.
- Rate-limit backoff is verified by offline tests, not live 429 responses.
- Persisted CLI tests cover invalid arguments, text/JSON test files,
  sanitized startup failures, and report serialization.

## Remaining work

1. Resolve live Gemini availability and verify structured-output compatibility.
2. Verify experimental credential integration in an authorized live demo login;
   raw credentials in natural-language text remain unsupported.
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

## Visible scripted demonstration

On November 12, 2026, a headed Chromium demonstration used an injected,
scripted planner with synthetic page content and no Gemini calls:

- Positive: filled CloudQA, clicked Submit, and verified Hello CloudQA
  against the live page; PASS in 3 steps.
- Negative: deliberately fabricated text evidence was rejected;
  FAIL in 1 step.
- Both JSON reports were saved under the ignored reports directory and
  identified their scripted-planner mode; saved verdicts were checked.
- An interactive pause after reporting raised EOFError because the script
  was supplied through standard input. Browser cleanup still ran.
- No demonstration video has been recorded yet.
- This demonstrates the browser pipeline, not live Gemini planning.

## Credential integration checkpoint

Synthetic tests cover JSON/environment loading and precedence, validation,
whole-value placeholder resolution, origin checks, CLI wiring, and redaction.
A real Chromium fixture fills a synthetic password, echoes it into the page,
and verifies that planner context, console output, and the saved report do not
contain that raw value. Placeholder navigation/select/press actions are rejected.
These tests do not prove production credential safety or live Gemini login.

## Additional Gemini diagnostics, November 12, 2026

- Model discovery completed in 1.2 seconds and listed the configured
  gemini-3.8-flash model.
- A plain-text generate_content request to that model returned HTTP 503
  after 5.4 seconds, in addition to earlier Interactions failures.
- A diagnostic Interactions request to advertised gemini-3.7-flash timed
  out after 15.8 seconds. No model configuration was changed.
- These results do not establish a root cause or live schema compatibility.
- Further repeated live requests were paused; live acceptance remains blocked.

## Reproducible demonstration script

demo_scripted.py ran successfully in headed Chromium, with a verified positive
PASS and rejection of fabricated evidence. It uses a scripted planner, synthetic
data, no credentials, and no Gemini calls. The complete 96-test suite passed
afterward. This replaces the earlier ad hoc stdin-based demonstration command;
the historical EOFError note above describes that earlier command only.

## Updated fresh-clone verification: 570c894

On November 12, 2026, commit 570c894 was verified from a fresh clone with
a newly created Python 3.14.2 virtual environment:

- Dependencies installed from requirements.txt; pip check found no broken requirements.
- Playwright's Chromium installation command succeeded.
- All 96 automated tests passed in 5.61 seconds.
- demo_scripted.py produced the expected positive PASS and negative FAIL.
- CLI help included both explicit credential options.
- Ignore checks passed for .env, credentials.json, and generated demo reports.
- The working tree remained clean.
- Package downloads and the existing browser cache were reused.
- No .env was copied; no Gemini calls or live login acceptance tests were performed.
