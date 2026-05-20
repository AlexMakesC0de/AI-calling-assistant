# Prompt Benchmark Fixture (ISR-353)

A small, automated benchmark for the LLM extraction prompt used by the
Transcript Formatter service. It exists so that prompt changes (ISR-356 and
beyond) can be measured against a fixed reference instead of judged by eye.

## What it does

1. Loads 10 anonymised support-call transcripts (`fixtures/`).
2. Runs each one through the **live extraction prompt**
   (`../prompts/extraction.txt`) against an Ollama model.
3. Scores every response against a hand-authored expected answer.
4. Compares the run against a committed baseline (`baseline.json`).

All transcripts, names, account references, emails and phone numbers are
**synthetic** — no real caller data is used.

## Layout

| Path | Purpose |
|---|---|
| `fixtures/*.json` | The 10 transcript fixtures + expected answers |
| `scoring.py` | Metric definitions (accuracy, completeness, hallucination rate) |
| `runner.py` | Loads fixtures, calls Ollama, scores, prints a report |
| `capture_baseline.py` | Runs the benchmark and writes `baseline.json` |
| `baseline.json` | Committed reference outputs + scores |
| `test_prompt_benchmark.py` | Pytest regression test against the baseline |

## The 10 fixtures

Chosen to cover every `issue_category` and a spread of priorities,
resolution statuses and sentiments, plus the awkward cases (missing data,
non-English input).

| # | Fixture | Category | Notable for |
|---|---|---|---|
| 01 | Account lockout | Account | Clean happy path, fully resolved |
| 02 | Billing double charge | Billing | Escalation, dissatisfied caller |
| 03 | Network outage | Network | Unresolved; customer-run steps not credited |
| 04 | Software app crash | Software | Error-code extraction, partial resolution |
| 05 | Hardware defect | Hardware | Warranty replacement, returns follow-up |
| 06 | Shipping delay | Shipping | "Delayed not lost" — must not over-state |
| 07 | Email sync | Technical | No contact detail given (hallucination check) |
| 08 | General inquiry | General | Anonymous caller, no steps (hallucination check) |
| 09 | Dutch billing | Billing | Non-English input, English JSON expected |
| 10 | Angry escalation | Technical | Extreme sentiment, critical priority |

Transcripts are kept under ~2,000 characters so they sit below the service's
2,500-character transcript-trim threshold — the benchmark therefore scores the
prompt on the full transcript every fixture sends.

## Scoring criteria

Each fixture produces three metrics, every one a fraction in `[0.0, 1.0]`.
The 16 graded form fields are grouped as:

- **identity** — `caller_name`, `account_or_reference`, `contact_info`,
  `agent_name`, `follow_up_department`
- **enum** — `issue_category`, `issue_priority`, `resolution_status`,
  `customer_sentiment`
- **bool** — `follow_up_required`
- **keyword** — `issue_description`, `resolution_outcome`, `call_summary`,
  `steps_taken`, `follow_up_actions`, `error_messages`

A field is **correct** when:

- *enum / bool* — the normalised value equals the expected value.
- *identity* — present case: the value matches the expected value (substring
  containment is allowed, so `Maria` matches `Maria Hendriks`); absent case:
  the model also reports no value.
- *keyword* — the field's text covers at least **50%** of the expected
  keywords (case-insensitive substring match). Keywords are deliberately short
  stems (e.g. `escalat`, `unlock`) so paraphrasing does not break scoring. If
  no keywords are expected, the field is correct only when the model leaves it
  empty.

### accuracy

> Fraction of all 16 fields that are correct.

The headline metric: how often the prompt extracts the right value.

### completeness

> Of the fields that *should* hold information, the fraction the model
> actually filled in.

Measured only over fields that can legitimately be empty (identity fields,
`steps_taken`, `follow_up_actions`, `error_messages`). It catches a prompt
that drops information that *was* present in the transcript.

### hallucination rate

> Of the fields that *should* be empty, the fraction where the model invented
> a concrete value. **Lower is better.**

Measured over the same can-be-empty fields. Fixtures 07 and 08 deliberately
withhold caller details so this metric has something to detect.

The free-text fields (`issue_description`, `resolution_outcome`,
`call_summary`) are always expected to contain text, so they count towards
accuracy but are excluded from completeness and hallucination rate, which
would otherwise be pinned to a fixed value.

The per-run `aggregate` is the mean of each metric across all 10 fixtures.

## Running it

The runner needs only Python 3 and a reachable Ollama instance — no formatter
service dependencies.

```bash
cd transcript-formatter/benchmark

# Print a report (weakest fixtures listed last):
python runner.py

# Pick the model explicitly:
OLLAMA_MODEL=gemma2:9b python runner.py
```

Environment variables: `OLLAMA_URL` (default `http://localhost:11434`),
`OLLAMA_MODEL` (default `llama3.1:8b`; falls back to the first installed
model if the requested one is missing), `BENCHMARK_OLLAMA_TIMEOUT`.

## The baseline

`baseline.json` holds the captured LLM output and scores for each fixture,
plus which model and prompt version produced them. It is the reference the
regression test compares against.

Re-capture it **only after an intentional prompt change**, then commit it:

```bash
OLLAMA_MODEL=gemma2:9b python capture_baseline.py
```

## Regression test

`test_prompt_benchmark.py` re-runs the benchmark and fails if a prompt change
regresses accuracy or completeness, or raises the hallucination rate, beyond a
0.07 tolerance (which absorbs LLM run-to-run drift). It runs against the
model recorded in `baseline.json`, and **skips automatically** when Ollama is
unreachable or that model is not installed.

```bash
pip install -r ../../requirements-dev.txt
pytest transcript-formatter/benchmark/
```

## Using it to optimise the prompt (ISR-356)

1. Run `python runner.py` and read the "weakest cases" list — it names the
   fixtures and the specific fields that failed.
2. Edit `../prompts/extraction.txt` to address those weak fields.
3. Re-run `runner.py` and confirm the aggregate metrics improved without
   regressing others.
4. Once satisfied, `capture_baseline.py` to lock in the new baseline and
   commit it alongside the prompt change.
