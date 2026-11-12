"""Bounded browser test loop. Planner context must contain no real credentials."""

import random
import time

from executor import execute
from llm import PlannerError, PlannerRateLimitError, plan
from observer import observe
from verifier import verify


def run(
    page,
    client,
    test,
    *,
    model="gemini-3.8-flash",
    max_steps=15,
    budget_seconds=60.0,
    max_retries=2,
    planner=plan,
    credentials=None,
):
    if not test.strip():
        raise ValueError("test must not be blank")
    if not 1 <= max_steps <= 15:
        raise ValueError("max_steps must be between 1 and 15")
    if not 0 < budget_seconds <= 60:
        raise ValueError("budget_seconds must be greater than 0 and at most 60")
    if not 0 <= max_retries <= 2:
        raise ValueError("max_retries must be between 0 and 2")

    sanitize = credentials.redact if credentials is not None else lambda value: value
    test = sanitize(test)

    started = time.monotonic()
    deadline = started + budget_seconds
    history = []
    retries = 0

    def remaining():
        return deadline - time.monotonic()

    def result(verdict, reason):
        return sanitize({
            "verdict": verdict,
            "reason": reason,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "steps": len(history),
            "retries": retries,
            "history": history,
        })

    for step in range(1, max_steps + 1):
        if remaining() <= 0:
            return result("fail", "Time budget exhausted")

        entry = {"step": step}
        history.append(entry)

        try:
            observation = observe(page)
            if remaining() <= 0:
                return result("fail", "Time budget exhausted during observation")

            action = planner(
                client,
                test=test,
                snapshot=sanitize(observation.snapshot),
                history=sanitize(history[:-1]),
                model=model,
                timeout=min(20.0, remaining()),
            )
            entry["action"] = sanitize(action.model_dump(exclude_none=True))

            if remaining() <= 0:
                return result("fail", "Time budget exhausted during planning")

            if action.action == "finish" and action.verdict == "fail":
                entry["result"] = {"ok": False}
                return result("fail", action.reason)

            if action.action in {"assert", "finish"}:
                checked = verify(page, observation, action)
                entry["result"] = checked
                if remaining() <= 0:
                    return result("fail", "Time budget exhausted during verification")
                if not checked["ok"]:
                    if retries >= max_retries:
                        return result("fail", "Evidence verification failed")
                    retries += 1
                    continue
                if action.action == "finish":
                    return result("pass", action.reason)
            else:
                if credentials is None:
                    entry["result"] = execute(page, observation, action)
                else:
                    entry["result"] = execute(
                        page, observation, action, credentials=credentials
                    )
                if remaining() <= 0:
                    return result("fail", "Time budget exhausted during execution")

        except PlannerRateLimitError:
            entry["result"] = {"ok": False, "error": "Planner rate limited"}
            if retries >= max_retries:
                return result("fail", "Gemini rate limit; recovery limit exhausted")
            if step >= max_steps:
                return result("fail", "Step limit exhausted after Gemini rate limit")
            delay = (2.0 ** retries) + random.uniform(0.0, 0.25)
            if remaining() <= delay:
                return result("fail", "Insufficient time budget for rate-limit backoff")
            entry["result"]["backoff_seconds"] = round(delay, 3)
            retries += 1
            time.sleep(delay)
        except PlannerError as exc:
            entry["result"] = {"ok": False, "error": str(exc)}
            if remaining() <= 0:
                return result("fail", "Time budget exhausted")
            if retries >= max_retries:
                return result("fail", "Recovery limit exhausted")
            retries += 1
        except Exception as exc:
            # Do not include exception messages: they may contain sensitive data.
            entry["result"] = {
                "ok": False,
                "error": type(exc).__name__,
            }
            if remaining() <= 0:
                return result("fail", "Time budget exhausted")
            if retries >= max_retries:
                return result("fail", "Recovery limit exhausted")
            retries += 1

    return result("fail", "Step limit exhausted without verified completion")
