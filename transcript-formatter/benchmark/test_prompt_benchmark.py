"""
Regression test: guard prompt changes against the captured benchmark baseline.

This test runs the live extraction prompt over every fixture and fails when a
prompt change regresses accuracy or completeness, or raises the hallucination
rate, beyond a small tolerance that absorbs LLM run-to-run drift.

It skips automatically when Ollama is unreachable or the baseline's model is
not installed, so it never blocks a machine without the LLM stack.

After an *intentional* prompt change, re-capture and commit the baseline:

    python capture_baseline.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import runner

BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"
# Absorbs run-to-run LLM drift: temperature 0 is not fully deterministic
# across Ollama versions and hardware. A real prompt regression moves the
# aggregate metrics by far more than this.
TOLERANCE = 0.07


@pytest.fixture(scope="module")
def baseline() -> dict:
    if not BASELINE_PATH.is_file():
        pytest.skip("No baseline.json - run capture_baseline.py first.")
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def live_results(baseline: dict) -> dict:
    """Run the benchmark once, against the baseline's model, for all tests."""
    try:
        available = runner.list_models()
    except runner.BenchmarkError as exc:
        pytest.skip(f"Ollama unreachable: {exc}")
    if baseline["model"] not in available:
        pytest.skip(
            f"Baseline model '{baseline['model']}' not installed locally."
        )
    return runner.run_benchmark(model=baseline["model"])


def test_accuracy_not_regressed(baseline: dict, live_results: dict) -> None:
    base = baseline["aggregate"]["accuracy"]
    live = live_results["aggregate"]["accuracy"]
    assert live >= base - TOLERANCE, (
        f"Accuracy regressed: baseline {base:.3f}, now {live:.3f}"
    )


def test_completeness_not_regressed(baseline: dict, live_results: dict) -> None:
    base = baseline["aggregate"]["completeness"]
    live = live_results["aggregate"]["completeness"]
    assert live >= base - TOLERANCE, (
        f"Completeness regressed: baseline {base:.3f}, now {live:.3f}"
    )


def test_hallucination_not_increased(baseline: dict,
                                     live_results: dict) -> None:
    base = baseline["aggregate"]["hallucination_rate"]
    live = live_results["aggregate"]["hallucination_rate"]
    assert live <= base + TOLERANCE, (
        f"Hallucination rate rose: baseline {base:.3f}, now {live:.3f}"
    )


def test_every_fixture_returns_valid_json(live_results: dict) -> None:
    broken = [
        fixture["id"]
        for fixture in live_results["fixtures"]
        if fixture["parse_error"]
    ]
    assert not broken, f"Fixtures returned unparseable JSON: {broken}"
