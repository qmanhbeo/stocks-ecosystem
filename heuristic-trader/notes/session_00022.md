# Session 22: Signal vs Translation Disambiguation

**Date:** 2026-05-19  
**Status:** MATERIAL FINDINGS (not promotion-ready)

## Purpose
Run a clean disambiguation pass for:
1. signal weakness vs execution translation weakness,
2. translation parameter sensitivity, and
3. simple train-only regime routing.

## Artifact Pack
- `artifacts/signal_translation_disambiguation/20260519_213127/`
  - `exp1_oracle_summary.csv`
  - `exp2_translation_summary.csv`
  - `exp2_translation_best_per_strategy.csv`
  - `exp3_router_summary.csv`
  - `summary.json`

## Strategies Tested
Top-3 from latest sweep by mean excess:
- `s1b_c11_ret_60d_lag_rank_70_30_depth5`
- `m_c11_ret_60d_lag_rank_depth5`
- `m_c8_vol_zscore_5d_depth5`

## Experiment 1 — Oracle Execution Ablation
Variants:
- `canonical`
- `oracle_no_filters_fixed`
- `oracle_no_filters_dynamic`

Headline:
- Two C11 families flipped from negative to positive mean excess under oracle execution.
- C8 improved but stayed slightly negative.

Interpretation:
- Signal edge is not purely absent; execution filters/translation are materially suppressing it.
- However, oracle variants still show severe tail years, so this is not a turnkey deploy signal.

## Experiment 2 — Translation Sweep
Grid per strategy:
- `top_k in {3,5,7}`
- `rebalance_days in {5,10}`
- `min_hold_days in {2,3,5}`
- `candidate_scan_multiplier in {3,5,10,20}`
- `sizing_mode in {fixed_initial,dynamic_portfolio}`

Headline:
- Best translated config for `s1b_c11...` reached positive mean excess (+13.57%).
- But tail remained severe (`worst_fold_return ~ -40.95%`) and 2025 remained deeply negative vs benchmark.

Interpretation:
- Translation quality matters a lot and can recover substantial edge.
- Current best candidates are still regime-fragile; positive aggregate is dominated by outsized 2021 performance.

## Experiment 3 — Train-Only Regime Router
Router design:
- State = prior-year VNINDEX sign (`bull`/`bear`).
- Gate ON only if same-state train-years had positive mean excess.

Headline:
- Router underperformed canonical for all 3 tested strategies.
- Mean excess worsened in every case.

Interpretation:
- This coarse yearly-state gate is a dead end in current form.
- Regime conditioning likely needs richer state features and/or intra-year gating.

## Conclusion
- Failure is **not** purely “weak signal” and **not** purely “weak strategy plumbing.”
- The data supports a mixed diagnosis:
  - execution translation is a real bottleneck,
  - but risk/tail robustness across regimes is still insufficient for promotion.

## Notes Audit Gate
- `make notes-audit` -> unavailable (no Make target in this repo).
- `python tools/validate_notes_consistency.py --notes-dir notes` -> unavailable (script missing).
- Manual audit performed instead:
  - session links in `sessions_compact.md` resolve,
  - finding/dead-end header IDs are unique in chunk files,
  - compact IDs map to chunk IDs.
- Recommendation: add repo-local `tools/validate_notes_consistency.py` and `make notes-audit`.
