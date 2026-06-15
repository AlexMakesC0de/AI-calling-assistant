# Extraction prompt changelog

Each entry documents a deliberate change to `extraction.txt` and the
benchmark evidence behind it. Re-capture
`transcript-formatter/benchmark/baseline.json` alongside every prompt
change so the regression test compares against the prompt that produced
the baseline.

The baseline benchmark is `gemma2:9b`, temperature 0, seed 42.

---

## v2 — ISR-356 — 2026-05-29

**Headline:** target the field-level failure modes that the v1 baseline
exposed without adding examples or changing the JSON shape.

**Baseline before this change** (`prompt_sha a6dfa9700cfc`):
accuracy 0.875, completeness 0.961, hallucination rate 0.048.

The weakest fixtures (per `benchmark/baseline.json`) were
`01_account_lockout`, `04_software_app_crash`, `08_general_inquiry`, and
`10_angry_escalation` at 0.81 accuracy each. The misses clustered on six
recurring failure modes:

| # | Failure mode | Evidence |
|---|---|---|
| 1 | `issue_priority` returned as `"Not mentioned"` — an invalid enum value | fixtures 08, 09 |
| 2 | `issue_category` defaults to `Technical` even when `Account` or `General` fits better | fixture 01 |
| 3 | `resolution_status` overuses `Partially Resolved` for cases that were clearly `Escalated` or `Unresolved` | fixtures 02, 03, 05, 10 |
| 4 | `follow_up_department` returns `None` even when the agent named a team to escalate to | fixtures 04, 06, 10 |
| 5 | `error_messages` contains a status sentence ("Account is locked") instead of a real error code | fixture 01 |
| 6 | `customer_sentiment` drifts one level (e.g. `Satisfied` → `Very Satisfied`) | fixtures 01, 04, 06, 08, 10 |

### Changes

1. **Enum rule made explicit.** Replaced "use your best judgement for enum
   fields" with "for ENUM fields you must ALWAYS return one of the allowed
   values, never `Not mentioned`, never empty". Directly targets failure
   mode 1.
2. **issue_category gets a one-line definition per option** (Account,
   Billing, Network, Software, Hardware, Shipping, Technical, General).
   Technical is now described as the *fallback* for issues that don't fit
   the named buckets — addressing failure mode 2.
3. **resolution_status gets a decision rule per option,** with the
   distinction between Partially Resolved (workaround given, root cause
   not fixed) and Escalated (handed to another team / queue) called out
   explicitly. Targets failure mode 3.
4. **follow_up_department rule added.** "If the agent named a team for
   follow-up (e.g. 'engineering team', 'returns team'), name that team
   here. Write 'None' only when no team is named." Targets failure
   mode 4.
5. **error_messages definition tightened** to exact codes or formal
   message strings only, with explicit "do NOT use this field for status
   descriptions like 'Account is locked'" guidance. Targets failure
   mode 5.
6. **customer_sentiment gets anchor cues per option** (effusive thanks,
   polite thanks, calm, annoyed, angry/repeat caller). Subjective, so
   smaller expected gain — included anyway because the cues should at
   least stop the systematic one-level drift on the satisfied end.
7. **steps_taken guidance clarified** as "concrete agent troubleshooting
   actions during the call", with an explicit "return empty when no
   troubleshooting was performed". Targets fixture 08's hallucinated
   step ("Explained weekend support hours" listed as a step).

The JSON shape, key set, and confidence-rating block are unchanged so
the schema validator (ISR-296) keeps passing without modification.

**After this change** (`prompt_sha 1201aecf6f63`):
accuracy 0.950, completeness 1.000, hallucination rate 0.000.

| Metric | v1 baseline | v2 | Δ |
|---|---|---|---|
| accuracy | 0.875 | 0.950 | **+0.075** |
| completeness | 0.961 | 1.000 | **+0.039** |
| hallucination rate | 0.048 | 0.000 | **−0.048** |

Per-fixture: three fixtures now score 1.00 (`02_billing_double_charge`,
`05_hardware_defect`, `06_shipping_delay`); fixture `01_account_lockout`
moved from 0.81 / 0.33 hallucination to 0.94 / 0.00 (the
`error_messages` definition tightening eliminated the "Account is locked"
false error). One small regression: `09_dutch_billing` moved 0.94 → 0.88
because the Dutch model now phrases the `issue_description` without the
keyword `"charge"`; the issue is sub-threshold and the aggregate impact
is far outweighed by the wins elsewhere.

The remaining misses are concentrated in `customer_sentiment` (subjective
one-level drift on satisfied/dissatisfied judgements) and a single
`resolution_status` disagreement on the network-outage fixture. Both are
at the limit of what prompt tuning alone can move without overfitting
the fixtures.
