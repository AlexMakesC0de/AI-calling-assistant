"""
Capture a benchmark baseline (ISR-353).

Runs the prompt benchmark once and writes the per-fixture LLM outputs and
scores to ``baseline.json``. That baseline is the reference point the
regression test (``test_prompt_benchmark.py``) checks future prompt changes
against, so it should be re-captured - and committed - deliberately whenever
the extraction prompt is intentionally changed.

    python capture_baseline.py
    OLLAMA_MODEL=gemma2:9b python capture_baseline.py

The baseline records which model produced it; the regression test re-runs
against that same model so the comparison stays meaningful.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

import runner

BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"


def capture() -> dict:
    """Run the benchmark and persist the result as the committed baseline."""
    results = runner.run_benchmark(verbose=True)
    baseline = {
        "captured_at": _dt.datetime.now(_dt.timezone.utc)
        .isoformat(timespec="seconds"),
        "model": results["model"],
        "prompt_sha": results["prompt_sha"],
        "aggregate": results["aggregate"],
        "fixtures": [
            {
                "id": fixture["id"],
                "title": fixture["title"],
                "accuracy": fixture["accuracy"],
                "completeness": fixture["completeness"],
                "hallucination_rate": fixture["hallucination_rate"],
                "incorrect_fields": fixture["incorrect_fields"],
                "hallucinated_fields": fixture["hallucinated_fields"],
                "parse_error": fixture["parse_error"],
                "output": fixture["output"],
            }
            for fixture in results["fixtures"]
        ],
    }
    BASELINE_PATH.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    runner.print_report(results)
    print(f"Baseline written to {BASELINE_PATH}")
    return baseline


def main() -> int:
    try:
        capture()
    except runner.BenchmarkError as exc:
        print(f"Could not capture baseline: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
