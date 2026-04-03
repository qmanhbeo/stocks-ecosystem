# Session 92 Log

## Objective
Run the first honest reduced-shape intraday restart:
- `H258`: decide whether the current CafeF `1H` surface is publishable enough as a reduced-shape research contract
- `H259`: if `H258` passes, run the first real intraday predictive screen against the continuation / exit target

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H231` had already shown that the CafeF `1H` bridge works and that reduced-shape open / first-hour / close-hour structure looked plausible
- `H232` remained provisional because the old fetch was partial
- the stale `H225-H228` closure was known to be a data-availability verdict, not a predictive failure verdict
- `H257` had just failed, so the richer event-source branch was parked and the active non-live priority had returned to intraday

The honest question was no longer:
- "is there any multi-ticker intraday data at all?"

It was:
- can the current full raw surface support a reduced-shape research contract honestly?
- and if so, does the first predictive screen show real exit-side signal, or only better data with no edge?

## What changed

Added:
- `analysis/h258_reduced_shape_intraday_contract_audit.py`
- `analysis/h259_intraday_exit_predictive_screen.py`
- `src/intraday_exit_research.py`
- `tests/test_intraday_exit_research.py`

Saved artifacts:
- `artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json`
- `artifacts/run_summaries/latest_portfolio_exit_intraday_reduced_shape_predictive_screen.json`
- `artifacts/timing_data/20260403_103038_h258_reduced_shape_intraday_contract_panel.parquet`
- `artifacts/timing_data/20260403_103038_h258_reduced_shape_intraday_coverage.parquet`
- `artifacts/timing_data/20260403_103038_h258_reduced_shape_intraday_coverage_summary.parquet`
- `artifacts/timing_data/20260403_103038_h258_reduced_shape_intraday_ticker_summary.parquet`
- `artifacts/timing_data/20260403_103038_h258_reduced_shape_intraday_pilot_role_summary.parquet`
- `artifacts/portfolio_baselines/20260403_103104_h259_intraday_exit_predictive_screen_results.parquet`
- `artifacts/portfolio_baselines/20260403_103104_h259_intraday_exit_predictive_screen_scored_dataset.parquet`
- `artifacts/portfolio_baselines/20260403_103104_h259_intraday_exit_predictive_screen_observed_panel.parquet`
- `artifacts/portfolio_baselines/20260403_103104_h259_intraday_exit_predictive_screen_baseline_daily.parquet`

### H258 - Reduced-Shape Intraday Contract Audit
**Hypothesis:**
The current CafeF `1H` surface is now broad enough to reopen blocked intraday work as a reduced-shape research contract even though a universal five-bar / auction artifact is still not honest.

**Command / code:**
`conda run -n stocks python analysis/h258_reduced_shape_intraday_contract_audit.py`

**Inputs:**
- current CafeF `1H` raw files under root `data/stock/`
- VCI daily backbone
- continuation panel benchmark
- window `2023-01-01` through `2025-12-31`

**Saved artifact:**
`artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| raw tickers | `402` | materially above the old `H232` floor |
| tickers with `60+` overlap days | `398` | broad cross-section, not a pilot slice |
| held-row coverage lower bound | `93.05%` | reduced-shape coverage clears the intended gate |
| missing-session rate in-window | `6.87%` | below the `10%` ceiling |
| observed reduced-shape rows | `261,990` | usable panel size |
| open-gap feature share | `99.996%` | structurally dense |
| first-60m feature share | `99.988%` | structurally dense |
| close-hour feature share | `99.9996%` | structurally dense |
| liquid-bank complete-day share | `97.10%` | reduced-shape and full-day both strong |
| liquid-industrial complete-day share | `96.72%` | still strong |
| liquid-fill complete-day share | `97.07%` | still strong |
| small-tail complete-day share | `0.53%` | the universal artifact is still not honest here |
| complete-day share present | `67.50%` | enough for reduced-shape, not enough for universal five-bar publication |

**Result:**
The reduced-shape contract is real. Coverage is no longer the blocker for intraday research. The remaining honesty boundary is artifact shape, not raw availability: open / first-hour / close-hour structure is dense enough, but the illiquid tail still makes a universal five-bar / auction contract untrue.

**Verdict: PASSED**

### H259 - Intraday Exit Predictive Screen
**Hypothesis:**
If the reduced-shape contract is real, a small hand-built intraday feature family should show continuation / exit signal on the observed `2023-2025` subset and beat the path-only baseline enough to keep the exit restart alive.

**Command / code:**
`conda run -n stocks python analysis/h259_intraday_exit_predictive_screen.py`

**Inputs:**
- `H258` reduced-shape contract panel
- `H258` coverage frame
- continuation panel on `2023-2025` only
- custom reduced-shape protocol:
  - dev `2023`
  - validation `2024`
  - confirmation `2025`

**Saved artifact:**
`artifacts/run_summaries/latest_portfolio_exit_intraday_reduced_shape_predictive_screen.json`

| Metric | Value | Note |
|--------|-------|------|
| candidate held rows | `2,259` | full continuation subset for `2023-2025` |
| observed held rows | `2,102` | `93.05%` observed-share, matches `H258` coverage |
| baseline validation AUC | `0.4895` | `path_core_observed` |
| baseline validation top-quintile hold advantage | `-0.00078` | baseline is weak on this narrowed window |
| baseline confirmation AUC | `0.4517` | weak |
| best intraday model | `intraday_shape_core` | raw reduced-shape features only |
| best intraday validation AUC | `0.4806` | below baseline |
| best intraday validation top-quintile hold advantage | `-0.00128` | below baseline |
| best intraday confirmation AUC | `0.5147` | better than baseline, but not enough |
| best intraday confirmation top-quintile hold advantage | `-0.00518` | still negative |

**Result:**
The data contract reopened honestly, but the first predictive screen did not. No reduced-shape intraday model beat the path-only observed-subset baseline on validation strongly enough to survive the branch gate, and no candidate was promotable.

**Verdict: FAILED**

## Branch decision

Do **not** change the live branch.

What Session 92 resolves:
- `H258` passes:
  - the current CafeF `1H` source is good enough for a reduced-shape research contract
  - the old `H225` data-availability block is no longer true in reduced-shape form
  - `H233` remains unresolved because the source is still not honest as a universal five-bar / auction artifact
- `H259` fails:
  - the first reduced-shape exit-family predictive screen does not justify continuing directly to deterministic exit integration
  - do **not** open `H260/H261` on the current reduced-shape contract

Branch effect:
- keep the reduced-shape intraday panel as acquisition / offline evidence
- close the reduced-shape exit restart on the current continuation target
- if model-side intraday work continues later, prefer:
  - library-grade intraday shape atoms
  - or selector-state / stress summaries
  - not direct exit integration on this failed first screen

## Validation

Completed before the runs:
- `python -m py_compile src/intraday_exit_research.py analysis/h258_reduced_shape_intraday_contract_audit.py analysis/h259_intraday_exit_predictive_screen.py tests/test_intraday_exit_research.py`
- `pytest -q tests/test_intraday_exit_research.py tests/test_intraday_acquisition_research.py`

Completed for the experiments:
- `conda run -n stocks python analysis/h258_reduced_shape_intraday_contract_audit.py`
- read `artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json`
- `conda run -n stocks python analysis/h259_intraday_exit_predictive_screen.py`
- read `artifacts/run_summaries/latest_portfolio_exit_intraday_reduced_shape_predictive_screen.json`

Verdict:
- `H258`: **PASSED**
- `H259`: **FAILED**
