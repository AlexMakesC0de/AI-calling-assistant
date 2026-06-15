"""
Prompt benchmark runner (ISR-353).

Loads every transcript fixture, runs it through the live extraction prompt
against an Ollama model, parses + scores the response, and reports per-fixture
and aggregate metrics.

Run directly to print a report:

    python runner.py
    OLLAMA_MODEL=gemma2:9b python runner.py

``run_benchmark()`` is the importable entry point used by the baseline
capture script and the regression test. The runner depends only on the
standard library so it can run anywhere Python 3 and Ollama are available,
without installing the formatter service's dependencies.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import scoring

BENCHMARK_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = BENCHMARK_DIR / "fixtures"
# The prompt under test is the real service template, shared with ISR-300.
PROMPT_PATH = BENCHMARK_DIR.parent / "prompts" / "extraction.txt"

# Host default - the formatter service itself talks to http://ollama:11434
# inside Docker, but the benchmark is a host/dev tool.
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
REQUEST_TIMEOUT = float(os.getenv("BENCHMARK_OLLAMA_TIMEOUT", "180"))


class BenchmarkError(RuntimeError):
    """Raised when the benchmark cannot run (e.g. Ollama unreachable)."""


# --- Fixtures + prompt -----------------------------------------------------
def load_fixtures() -> list[dict]:
    """Load every fixture JSON file, sorted by filename."""
    if not FIXTURES_DIR.is_dir():
        raise BenchmarkError(f"Fixtures directory not found: {FIXTURES_DIR}")
    fixtures: list[dict] = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            fixtures.append(json.load(handle))
    if not fixtures:
        raise BenchmarkError(f"No fixtures found in {FIXTURES_DIR}")
    return fixtures


def fixture_transcript(fixture: dict) -> str:
    """Join a fixture's transcript lines into the diarized text block."""
    return "\n".join(fixture["transcript"])


def load_prompt_template() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BenchmarkError(f"Prompt template missing: {PROMPT_PATH}") from exc


def prompt_sha(template: str | None = None) -> str:
    """Short hash identifying which prompt version produced a result set."""
    text = template if template is not None else load_prompt_template()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# --- Ollama ----------------------------------------------------------------
def _http_json(url: str, payload: dict | None = None,
               timeout: float = REQUEST_TIMEOUT) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    request = urllib.request.Request(
        url, data=data, headers=headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise BenchmarkError(f"Ollama request to {url} failed: {exc}") from exc


def list_models(ollama_url: str = DEFAULT_OLLAMA_URL) -> list[str]:
    """Names of all models installed in the target Ollama instance."""
    body = _http_json(f"{ollama_url}/api/tags", timeout=10)
    return [
        str(model.get("name", "")).strip()
        for model in body.get("models", [])
        if model.get("name")
    ]


def resolve_model(requested: str = DEFAULT_MODEL,
                  ollama_url: str = DEFAULT_OLLAMA_URL) -> str:
    """Return ``requested`` if installed, else fall back to the first model."""
    available = list_models(ollama_url)
    if not available:
        raise BenchmarkError("Ollama reports no installed models.")
    if requested in available:
        return requested
    fallback = available[0]
    print(
        f"  ! model '{requested}' not installed; using '{fallback}'",
        file=sys.stderr,
    )
    return fallback


def _strip_fences(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _extract_json_object(text: str) -> str | None:
    """Best-effort extraction of the first top-level JSON object."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for idx in range(start, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                return text[start:idx + 1]
    return None


def parse_model_json(raw: str) -> dict:
    """Parse the model's textual response into a dict, tolerating fences."""
    cleaned = _strip_fences(raw)
    for candidate in (cleaned, _extract_json_object(cleaned)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise BenchmarkError("Model response was not a valid JSON object.")


def call_ollama(prompt: str, model: str,
               ollama_url: str = DEFAULT_OLLAMA_URL) -> str:
    """Send one prompt to Ollama and return the raw text response."""
    body = _http_json(
        f"{ollama_url}/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            # temperature 0 + fixed seed keeps runs as reproducible as the
            # model allows, so the regression test stays low-noise.
            "options": {"temperature": 0, "seed": 42, "num_predict": 800},
        },
    )
    return body.get("response", "")


# --- Benchmark -------------------------------------------------------------
def run_benchmark(model: str | None = None,
                 ollama_url: str = DEFAULT_OLLAMA_URL,
                 verbose: bool = False) -> dict:
    """Run every fixture through the prompt and score the results."""
    template = load_prompt_template()
    fixtures = load_fixtures()
    resolved = model or resolve_model(ollama_url=ollama_url)

    fixture_results: list[dict] = []
    for fixture in fixtures:
        prompt = template.replace(
            "{TRANSCRIPT}", fixture_transcript(fixture)
        )
        raw = call_ollama(prompt, resolved, ollama_url)
        parse_error = None
        try:
            output = parse_model_json(raw)
        except BenchmarkError as exc:
            output, parse_error = {}, str(exc)
        scores = scoring.score_output(fixture["expected"], output)
        result = {
            "id": fixture["id"],
            "title": fixture.get("title", ""),
            "parse_error": parse_error,
            "output": output,
            "accuracy": scores["accuracy"],
            "completeness": scores["completeness"],
            "hallucination_rate": scores["hallucination_rate"],
            "incorrect_fields": scores["incorrect_fields"],
            "hallucinated_fields": scores["hallucinated_fields"],
        }
        fixture_results.append(result)
        if verbose:
            print(_fixture_line(result))

    return {
        "model": resolved,
        "prompt_sha": prompt_sha(template),
        "ollama_url": ollama_url,
        "fixtures": fixture_results,
        "aggregate": scoring.aggregate(fixture_results),
    }


def _fixture_line(result: dict) -> str:
    flag = " PARSE-FAIL" if result["parse_error"] else ""
    return (
        f"  [{result['id']:<22}] "
        f"acc={result['accuracy']:.2f} "
        f"comp={result['completeness']:.2f} "
        f"halluc={result['hallucination_rate']:.2f}{flag}"
    )


def print_report(results: dict) -> None:
    """Print a human-readable benchmark report, weakest fixtures last."""
    agg = results["aggregate"]
    print("\n" + "=" * 62)
    print("PROMPT BENCHMARK REPORT")
    print("=" * 62)
    print(f"  model       : {results['model']}")
    print(f"  prompt_sha  : {results['prompt_sha']}")
    print(f"  fixtures    : {agg['count']}")
    print("-" * 62)
    print(f"  accuracy            : {agg['accuracy']:.3f}")
    print(f"  completeness        : {agg['completeness']:.3f}")
    print(f"  hallucination_rate  : {agg['hallucination_rate']:.3f}  "
          "(lower is better)")
    print("-" * 62)
    print("  Weakest cases first (target these when iterating the prompt):")
    weakest = sorted(results["fixtures"], key=lambda r: r["accuracy"])
    for result in weakest:
        print(_fixture_line(result))
        if result["incorrect_fields"]:
            print(f"      wrong: {', '.join(result['incorrect_fields'])}")
        if result["hallucinated_fields"]:
            print(f"      hallucinated: "
                  f"{', '.join(result['hallucinated_fields'])}")
    print("=" * 62 + "\n")


def main() -> int:
    try:
        results = run_benchmark(verbose=True)
    except BenchmarkError as exc:
        print(f"Benchmark could not run: {exc}", file=sys.stderr)
        return 1
    print_report(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
