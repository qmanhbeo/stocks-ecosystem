# Session 105 Log

## Objective
Run the next exact queue item after Session 104 promoted the reduced-shape disagreement atoms as offline state features:
- `H276`: test whether event-conditioned intraday disagreement on the observed `breakout_followthrough` entry subset survives as a materially different timing side branch and earns deterministic follow-through

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H275` had already passed as offline evidence:
  - `fade_tension_disagreement`
  - `intraday_shape_core_disagreement`
  survived the standalone observed-subset library gate
- the next honest question from `next_steps.md` was narrower than a new broad backtest:
  - do event regimes make that disagreement information more transportable on the breakout-like entry subset?
- earlier event work had already shown only narrow trust-context value:
  - `H251` passed
  - `H252` stayed offline-only
- the branch should only advance if an event-conditioned disagreement regime beats the same-model ungated baseline cleanly enough to justify `H277`

## What changed

Added:
- `analysis/h276_event_to_intraday_state_transition.py`

Saved artifacts:
- `artifacts/run_summaries/latest_entry_alpha_event_to_intraday_state_transition.json`
- `artifacts/portfolio_baselines/20260404_140142_h276_event_to_intraday_state_transition_results.parquet`
- `artifacts/portfolio_baselines/20260404_140142_h276_event_to_intraday_state_transition_audit_panel.parquet`

### H276 - Event-To-Intraday State Transition Audit
**Hypothesis:**
If raw event timing and raw reduced-shape intraday disagreement each fail alone as live-ready timing branches, the surviving timing edge may live in event-day disagreement rather than in either source separately.

**Command / code:**
`conda run -n stocks python analysis/h276_event_to_intraday_state_transition.py`

**Inputs:**
- reduced-shape intraday source:
  - `H258` reduced-shape panel
- disagreement construction:
  - `H275`-style residualization against:
    - `S1`
    - `C4`
    - `C12`
- entry subset:
  - observed `breakout_followthrough`
  - buyable rows only
  - `2023-2025`
- event regimes:
  - `all_rows`
  - `report_window_any`
  - `recent_filing_any`
  - `event_transition_any`
- advancement rule:
  - event-conditioned candidate must beat its own ungated baseline on:
    - validation AUC delta
    - validation top-quintile cycle return delta
    - confirmation top-quintile cycle return delta
  - confirmation top-quintile cycle return must stay positive

**Saved artifact:**
`artifacts/run_summaries/latest_entry_alpha_event_to_intraday_state_transition.json`

| Metric | Value | Note |
|--------|-------|------|
| breakout rows | `5,858` | observed `breakout_followthrough` buyable rows in `2023-2025` |
| breakout dates | `711` | overlap dates on the audited subset |
| breakout tickers | `379` | audited ticker breadth |
| `report_window_any` share | `48.26%` | row share of the audited subset |
| `recent_filing_any` share | `11.30%` | row share of the audited subset |
| `event_transition_any` share | `54.44%` | combined report-window or recent-filing share |
| promoted candidates | `0` | no regime / model pair earned `H277` |
| best mixed candidate | `event_transition_any + disagreement_combo` | top-ranked mixed result under the predeclared sort |
| best mixed validation top-quintile delta vs `all_rows` | `+0.0048` | realized return improvement |
| best mixed confirmation top-quintile delta vs `all_rows` | `+0.0120` | realized return improvement |
| best mixed validation AUC delta vs `all_rows` | `-0.0195` | ranking quality worsened |
| best mixed confirmation AUC delta vs `all_rows` | `-0.0135` | ranking quality worsened |
| strongest mixed directional clue | `event_transition_any + intraday_shape_core_disagreement` | cleaner confirmation ranking than the combo |
| strongest mixed directional clue validation / confirmation top-quintile delta | `+0.0043 / +0.0137` | both positive versus `all_rows` |
| strongest mixed directional clue validation / confirmation AUC delta | `-0.0055 / +0.0156` | validation still failed the pass rule |

**Result:**
`H276` is mixed.

What survived:
- event conditioning was not empty:
  - `event_transition_any` improved top-quintile realized return for both disagreement models
  - `recent_filing_any` also improved top-quintile realized return, though on a smaller slice
- the best directional clue was:
  - `event_transition_any + intraday_shape_core_disagreement`
  - validation / confirmation top-quintile cycle return delta vs `all_rows`:
    - `+0.0043 / +0.0137`

What failed:
- no event-conditioned regime beat the ungated baseline cleanly enough to pass
- validation AUC fell for every mixed candidate
- `report_window_any` failed outright across all tested models

So the branch did find a real interaction:
- event context can sharpen the realized high-disagreement tail

But it did **not** find a transportable deterministic gate:
- no candidate earned `H277`
- no candidate is promotable beyond narrow offline evidence

**Verdict: MIXED**

## Branch decision

Do **not** change the live branch.

What Session 105 resolves:
- `H276` is mixed:
  - event-conditioned disagreement is real as narrow offline context on the observed breakout subset
  - it is not strong enough to justify deterministic follow-through on the current contract

Branch effect:
- do **not** open `H277`
- keep:
  - `event_transition_any`
  - `recent_filing_any`
  as narrow offline context only for disagreement-style timing clues
- stop timing-model invention on the current stack
- wait for:
  - genuinely better event data
  - a materially different label / operational contract
  - or more forward evidence

## Validation

Completed before the run:
- `python -m py_compile alpha-research-lab/analysis/h276_event_to_intraday_state_transition.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h276_event_to_intraday_state_transition.py`
- read `artifacts/run_summaries/latest_entry_alpha_event_to_intraday_state_transition.json`

Completed after the note update:
- `conda run -n stocks pytest -q alpha-research-lab/tests/test_entry_alpha_research.py alpha-research-lab/tests/test_intraday_exit_research.py`
  - `20 passed`
  - `2` existing pandas `FutureWarning`s

Verdict:
- `H276`: **MIXED**
