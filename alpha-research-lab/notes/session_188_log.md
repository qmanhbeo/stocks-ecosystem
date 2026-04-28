# Session 188 Log - Event-Cascade Entry-Label Audit (2026-04-28)

## Objective

Continue the evergreen loop with the highest-ranked current-data hypothesis:
- keep the live alpha branch unchanged
- avoid `2026` predictive use
- avoid GPU / Ollama / PhoBERT training jobs
- test whether the H321 event-cascade state failed additive promotion because
  it belongs on the stock-specific entry-label contract instead of the
  full-universe rank contract

This session stayed long-only.
It did not use `2026` for predictive tuning.

## Branch selection

H321 found a sparse self-excitation cascade state,
`today_self_accel_high`, that beat the matched H310 same-day follow-up control.
H322 then showed the same state was not additive enough over the frozen
`S1 / C4 / C13` core.

The next honest question was therefore not another event-rank overlay. It was
whether the state identifies better entry opportunities among the existing
entry-alpha candidate book.

The pass used the H321 source-limited event window:
- `2023` dev
- `2024` validation
- `2025` confirmation
- `2026+` excluded

## Experiment

### H349 - Event-Cascade Entry-Label Audit

**Hypothesis:**
`today_self_accel_high` may be a sparse entry-opportunity state: it should
improve `buy_now_label` and cycle returns inside the entry-alpha candidate
panel after matching against the existing entry prior.

**Command / code:**
`python analysis/h349_event_cascade_entry_label.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_hawkes_disclosure_cascade.json`
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_labels_cycle5.parquet`
- `data/features/entry_alpha/entry_scores_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_143353_h349_event_cascade_entry_label_research_branch_event_cascade_entry_label.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | no validation / confirmation entry-label lift after entry-prior matching |
| panel rows | `14,960` | 2023-2025 entry-candidate panel |
| panel tickers / dates | `393 / 748` | source-limited H321-compatible window |
| candidate state | `today_self_accel_high` | H321 winner |
| validation active rows / dates | `15 / 15` | enough for the predeclared first test |
| confirmation active rows / dates | `19 / 18` | enough for the predeclared first test |
| validation daily label lift | `-0.1807` | active state vs same-day candidate average |
| validation matched label lift | `-0.1111` | matched by date and entry-prior bucket |
| validation matched net lift | `-0.0166` | matched by date and entry-prior bucket |
| validation matched relative lift | `-0.0166` | vs VNINDEX, matched by date and entry-prior bucket |
| confirmation daily label lift | `+0.0453` | raw daily label lift positive only |
| confirmation matched label lift | `-0.0263` | turns negative after entry-prior matching |
| confirmation matched net lift | `-0.0345` | negative |
| confirmation matched relative lift | `-0.0345` | negative |

**Result:**
The cascade-as-entry-label thesis fails. The state has enough entry-candidate
coverage for a first pass, but validation is negative across label and return
lifts, and confirmation only has a raw daily label lift. After matching against
the existing entry prior, confirmation label and return lifts are negative.

**Verdict: FAILED**

## Branch decision

Do not continue event-cascade entry-label variants under the current
entry-alpha contract. This does not erase H321 as sparse event-timing evidence,
but it closes the idea that `today_self_accel_high` is simply waiting for the
entry-label target.

The next evergreen branch should move to a different mechanism from the
high-value queue, with `official-disclosure-bridge` the current lead because it
is source/audit-first and now has local HNX raw data.

## Memory changes

Updated:
- `notes/next_steps.md`
- `notes/findings-271-300.md`

Added:
- `analysis/h349_event_cascade_entry_label.py`

Durable finding:
- `F289`

No signal-library update was made because H349 did not create, promote, or
change a signal-library candidate. The negative result is recorded in the
active findings chunk and live queue.

## Verification

Completed:
- `python -m py_compile analysis/h349_event_cascade_entry_label.py`
- `python analysis/h349_event_cascade_entry_label.py`
- read the saved run summary and details artifacts

The broader test suite was not run.

## Next step

Continue the evergreen loop with `official-disclosure-bridge` as the next
smallest honest experiment: first audit source coverage and timestamp mapping,
not alpha IC.
