# Session 96 Log

## Objective
Run the smallest honest deterministic follow-through after Session 95's breakout-entry trust audit:
- `H267`: test whether a simple breakout-entry gate built from the `H266` winner score improves the observed breakout sleeve versus the ungated observed-breakout baseline

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H266` had already passed the breakout-entry trust audit on the observed `breakout_followthrough` subset
- the surviving `H266` score was:
  - `entry_prob__intraday_shape_core`
- the key contract was already narrow:
  - observed breakout rows only
  - `2023-2025` only
  - offline evidence only
- the next honest question was no longer:
  - "does reduced-shape intraday rank breakout entries better?"
- it was:
  - does a deterministic gate built from that score actually improve the realized breakout-only sleeve relative to the ungated observed-breakout baseline?
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

## What changed

Added:
- `analysis/h267_breakout_entry_intraday_gate_integration.py`

Saved artifacts:
- `artifacts/run_summaries/latest_entry_alpha_breakout_intraday_gate_integration.json`
- `artifacts/entry_alpha/20260403_122950_h267_breakout_entry_intraday_gate_integration_results.parquet`
- `artifacts/entry_alpha/20260403_122950_h267_breakout_entry_intraday_gate_integration_best_daily.parquet`
- `artifacts/entry_alpha/20260403_122950_h267_breakout_entry_intraday_gate_integration_baseline_daily.parquet`
- `artifacts/entry_alpha/20260403_122950_h267_breakout_entry_intraday_gate_integration_gate_panel.parquet`

### H267 - Breakout Entry Intraday Gate Integration
**Hypothesis:**
If `H266` is real, a simple high-conviction gate on the observed `breakout_followthrough` subset should improve deterministic realized performance versus the ungated observed-breakout sleeve.

**Command / code:**
`conda run -n stocks python analysis/h267_breakout_entry_intraday_gate_integration.py`

**Inputs:**
- `H266` scored panel and summary
- branch-local `2023-2025` candidate / label caches under `artifacts/entry_alpha/`
- observed breakout sleeve only:
  - `entry_thesis_family == breakout_followthrough`
  - `can_buy_next_open == True`
  - `entry_prob__intraday_shape_core` observed
- predeclared dev-only threshold grid:
  - `dev_q50`
  - `dev_q80`
  - `dev_q90`
- coverage guard:
  - total allowed rows `>= 150`
  - confirmation allowed rows `>= 40`
  - confirmation cash-weight increase `<= +0.15` vs the ungated observed-breakout baseline

**Saved artifact:**
`artifacts/run_summaries/latest_entry_alpha_breakout_intraday_gate_integration.json`

| Metric | Value | Note |
|--------|-------|------|
| baseline variant | `observed_breakout_always_on` | ungated observed-breakout sleeve |
| baseline validation relative return | `-0.1615` | benchmark-relative |
| baseline confirmation relative return | `-0.3327` | benchmark-relative |
| baseline overall relative return | `-0.4499` | full `2023-2025` restarted slice |
| winning gate | `dev_q90` | strongest dev-quantile threshold |
| winning threshold | `0.5198` | dev-phase `90%` quantile of `entry_prob__intraday_shape_core` |
| winning allowed rows | `536` | `207` dev / `178` validation / `151` confirmation |
| winning validation relative return | `+0.2659` | validation turns positive |
| winning confirmation relative return | `+0.0029` | confirmation stays slightly positive |
| winning validation relative delta | `+0.4274` | vs ungated observed-breakout baseline |
| winning confirmation relative delta | `+0.3357` | vs ungated observed-breakout baseline |
| winning validation IR delta | `+1.7316` | vs ungated observed-breakout baseline |
| winning confirmation IR delta | `+1.7199` | vs ungated observed-breakout baseline |
| winning confirmation cash weight | `0.0082` | easily inside the coverage guard |

**Result:**
`H267` passes cleanly on the predeclared deterministic gate contract.

The useful reading is still narrow:
- the win lives inside the observed breakout sleeve
- the selected rule is high-conviction, not broad:
  - only `536` rows overall
  - only `151` confirmation rows
- but this is no longer just a predictive-score result:
  - the score survives deterministic integration on the local contract

This is still not a live-promotion result:
- the branch remains `2023-2025` only
- the working contract is still the observed breakout sleeve
- the live branch remains untouched

What it does justify is one reintegration follow-through:
- `H268`: apply the `H267` breakout trust gate only to `breakout_followthrough` rows inside the broader entry book, leave the other families unchanged, and test whether the mixed-family deterministic ladder improves on the ungated broader baseline

**Verdict: PASSED**

## Branch decision

Do **not** change the live branch.

What Session 96 resolves:
- `H267` passes:
  - reduced-shape intraday breakout trust survives deterministic integration on the observed breakout sleeve
  - the best rule is a dev-calibrated high-conviction gate:
    - `dev_q90`
    - threshold `0.5198`
  - the mechanism is now stronger than a pure score-ranking story, but it is still local to the breakout sleeve

Branch effect:
- keep all continuation-veto follow-through closed:
  - `H260/H261` remain closed
  - `H264/H265` remain closed
- keep the live sticky branch unchanged
- promote the breakout-entry gate result as offline evidence only
- the next honest follow-through is:
  - `H268`: family-local breakout trust compatibility integration
- if `H268` fails, the next fallback should be:
  - breakout survivor label rewrite
  - or selector-state / top-k intraday stress routing

## Validation

Completed before the run:
- `python -m py_compile analysis/h267_breakout_entry_intraday_gate_integration.py`
- `pytest -q tests/test_entry_alpha_research.py tests/test_intraday_exit_research.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h267_breakout_entry_intraday_gate_integration.py`
- read `artifacts/run_summaries/latest_entry_alpha_breakout_intraday_gate_integration.json`

Verdict:
- `H267`: **PASSED**
