"""Console and JSON result output."""

import json
from pathlib import Path


def write_report(result: dict, destination: str = "report.json") -> None:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"VERDICT: {result['verdict'].upper()}")
    print(f"REASON: {result['reason']}")
    print(f"STEPS: {result['steps']}")
    print(f"ELAPSED: {result['elapsed_seconds']}s")
    print(f"REPORT: {path}")
