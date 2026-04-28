# Session 191 Log - Event-V2 Optionality Payoff Audit (2026-04-28)

## Objective

Continue the evergreen loop after closing the current-data flow branch:
- keep the live alpha branch unchanged
- avoid `2026` predictive use
- avoid GPU / Ollama / PhoBERT jobs
- test whether event-v2 states are useful as payoff-shape / risk-filter states
  rather than additive mean-rank overlays

This session stayed long-only.
It did not use `2026` for predictive tuning.

## Branch selection

H321 showed that the self-exciting event-v2 cascade state is a real sparse
timing cohort. H322 showed that it is not a useful additive overlay, and H349
showed that it does not transfer to the entry-alpha label contract.

The remaining plausible event-v2 rescue was not another rank overlay. It was
that first-public or cascade states might change payoff shape: more upside
tail, less bad-tail exposure, or better tradability on active event rows.

## Experiment

### H352 - Event-V2 Optionality Payoff

**Hypothesis:**
First-public and cascade event states may matter as sparse tail-payoff or
risk-filter features. If the thesis is real, active event rows should show a
validation and confirmation upside-tail advantage against matched non-event
controls without materially worse downside tail, hit rate, or tradability.

**Command / code:**
`python analysis/h352_event_v2_optionality_payoff.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_hawkes_disclosure_cascade.json`
- H321 saved panel:
  `artifacts/portfolio_baselines/20260409_155621_h321_hawkes_disclosure_cascade_panel.parquet`
- `data/features/execution/tradability_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_154419_h352_event_v2_optionality_payoff_research_branch_event_v2_optionality_payoff.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | upside-tail hints but no clean two-phase payoff state |
| panel rows / tickers / dates | `258,375 / 394 / 748` | H321 source-limited 2023-2025 window |
| best state | `recent5_high_self_no_today` | recent high self-intensity event state, no same-day event |
| best decision reason | `weak_tail_hint_but_not_a_clean_two_phase_optionality_state` | branch remains offline evidence |
| validation active rows | `1,586` | enough coverage |
| validation mean lift | `+0.0016` | matched non-event controls |
| validation q90 lift | `+0.0196` | upside tail positive |
| validation q10 lift | `-0.0145` | downside tail materially worse |
| validation bad-tail-rate lift | `-0.0054` | bad-tail frequency slightly better |
| confirmation active rows | `1,641` | enough coverage |
| confirmation mean lift | `-0.0026` | expected value not clean |
| confirmation q90 lift | `+0.0174` | upside tail remains positive |
| confirmation q10 lift | `-0.0239` | downside tail materially worse |
| confirmation bad-tail-rate lift | `+0.0065` | bad-tail frequency slightly worse |

**Result:**
The optionality thesis is only partially true. The event-v2 states generally
show positive validation and confirmation `q90` lifts, but the same states also
show materially worse `q10` downside tails and inconsistent mean lifts.

The original slow implementation completed but crossed the short-job runtime
boundary because it used Python quantile lambdas in repeated groupby reference
tables. The script was repaired to precompute reference tables and use
vectorized groupby quantiles, then rerun. The final artifact above is from the
fast verified path.

**Verdict: MIXED**

## Branch decision

Keep event-v2 payoff-shape evidence as offline timing evidence only:
- do not promote any event-v2 payoff state
- do not integrate event-v2 as a live additive overlay
- do not treat H349's entry-label failure as rescued by H352
- only reopen with a stricter portfolio-level convexity test or new event data
  if the branch becomes high priority again

## Memory changes

Updated:
- `notes/live_state.md`
- `notes/findings-271-300.md`
- `notes/signal_library.md`

Added:
- `analysis/h352_event_v2_optionality_payoff.py`

Durable finding:
- `F292`

No promoted signal was added.

## Verification

Completed:
- `python -m py_compile analysis/h352_event_v2_optionality_payoff.py`
- `python analysis/h352_event_v2_optionality_payoff.py`
- read the saved run summary artifact

The broader test suite was not run.

## Next step

Continue the evergreen loop with a non-event integration branch unless a
stricter portfolio-level convexity test is intentionally activated.
