# Session 35 Log — Standalone Criteria Enforced + H103 Return Skewness (2026-03-26)

## Objective
- Enforce standalone-signal significance checks (for RL usability) as a mandatory gate.
- Continue dense-signal sweep with next candidate: return skewness.

---

## New Experiment: H103 Return Skewness

### Implemented
- `data_tools/build_return_skewness_features.py`
  - Output: `data/features/xs_return_skewness.parquet` (826,404 rows)
  - Features:
    - `ret_skew_5d`, `ret_skew_20d`, `ret_skew_60d`
    - `downside_dev_20d`, `upside_dev_20d`
    - `down_up_vol_ratio_20d`, `left_tail_frac_20d`, `ret_skew_z20`

- `cross_sectional_wf.py`
  - New flag: `--use-return-skewness`

### WF + Portfolio evaluation
- WF probas: `data/features/xs_barrier_vol_1d_h103_ret_skew_hose_full.parquet`
- Portfolio result (`analysis/h40_rank_portfolio.py --no-vix-filter`):
  - IC: **+0.1489** (vs H93 +0.1491, −0.0002)
  - Top-5 avg edge: **+24.19%** (vs H93 +24.15%, +0.04%)
  - Top-5 Sharpe: **10.63** (vs H93 15.08, −4.45)
  - Edge std: 2.28% (vs H93 1.60%, +0.68)

**Verdict:** FAIL (risk-adjusted degradation).

---

## Standalone Significance Check (RL Gate)

Script:
- `analysis/standalone_dense_signal_checks.py`

Artifact:
- `artifacts/run_summaries/20260326_154550_dense_signal_standalone_checks_standalone_signal.json`

Results:

### H100 proxy feature (`oc_asym_5d`)
- Standalone IC avg: **+0.0273**
- Positive years: **10/11**
- Corr with S1: **+0.147**
- Interpretation: standalone predictive + partly orthogonal, but supervised integration still hurts Sharpe.

### H103 proxy feature (`ret_skew_z20`)
- Standalone IC avg: **+0.0019**
- Positive years: **6/11**
- Corr with S1: **−0.0035**
- Interpretation: orthogonal but too weak standalone (below IC > 0.01 bar).

### H101 context check (`xs_dispersion_z20` vs S1 daily top-5 edge)
- Spearman: **−0.0289**
- p-value: **0.130**
- Interpretation: weak standalone context relation; H101 benefit appears in supervised interaction, not as a strong standalone predictor.

---

## Session Conclusion

1. Standalone significance is now explicitly evaluated and logged.
2. H103 (return skewness) is rejected.
3. H100 remains standalone-interesting but supervised-failing.
4. H101 remains the best dense branch from Sessions 34–35.
