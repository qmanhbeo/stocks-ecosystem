# Session 34 Log — LLM Parked, Dense Signal Sweep (2026-03-26)

## Directive
- Park LLM path clearly due runtime/throughput bottleneck.
- Move to next high-value dense experiments.

---

## LLM Status

**H98 LLM path: PARKED (explicitly).**

Reason:
- Full extraction runtime is currently operationally too slow / unstable in this environment.
- Local Ollama path timed out in prior smoke runs and remains a bottleneck for full-history processing.

Action taken:
- No further H98 runs in this session.
- Focus shifted to dense non-LLM signals with immediate computability from existing OHLCV data.

---

## New Dense Feature Pipelines Implemented

### H100 — Open/Close Asymmetry (ticker-day dense)
- Script: `data_tools/build_open_close_asymmetry_features.py`
- Output: `data/features/xs_open_close_asymmetry.parquet` (826,404 rows)
- Features: overnight/intraday returns, O2O/C2C, asymmetry and 5d/20d rolling variants

### H101 — Cross-Sectional Dispersion Regime (date-level dense)
- Script: `data_tools/build_dispersion_regime_features.py`
- Output: `data/features/xs_dispersion_regime_daily.parquet` (2,748 rows)
- Features: dispersion std/iqr/tail spread, breadth, rolling dispersion and z-score

### WF Integration
- `cross_sectional_wf.py` new flags:
  - `--use-oc-asymmetry`
  - `--use-dispersion-regime`

---

## Experiments

Base config for all runs:
```bash
conda run -n stocks python cross_sectional_wf.py \
  --use-volume-signals --barrier-pct 0.01 --target-horizon 1 \
  --save-all-probas <OUT>
```

### H100: + open/close asymmetry
- Probas: `data/features/xs_barrier_vol_1d_h100_oc_asym_hose_full.parquet`
- Portfolio eval:
  - IC: **+0.1541** (vs H93 +0.1491, +0.0050)
  - Top-5 avg edge: **+25.36%** (vs H93 +24.15%, +1.21%)
  - Top-5 Sharpe: **11.63** (vs H93 15.08, **-3.45**)
  - Edge std: 2.18% (vs H93 1.60%, +0.58%)
- Verdict: **MIXED/FAIL for RL quality** (more raw edge, much worse stability).

### H101: + dispersion regime
- Probas: `data/features/xs_barrier_vol_1d_h101_dispersion_hose_full.parquet`
- Portfolio eval:
  - IC: **+0.1474** (vs H93 +0.1491, -0.0017)
  - Top-5 avg edge: **+23.83%** (vs H93 +24.15%, -0.32%)
  - Top-5 Sharpe: **15.34** (vs H93 15.08, **+0.26**)
  - Edge std: 1.55% (vs H93 1.60%, -0.05%)
- Verdict: **PASS (risk-adjusted)**, with slightly better Sharpe / lower variance.

### H102: H100 + H101 combined
- Probas: `data/features/xs_barrier_vol_1d_h102_oc_disp_hose_full.parquet`
- Portfolio eval:
  - IC: **+0.1531** (vs H93 +0.1491, +0.0040)
  - Top-5 avg edge: **+25.23%** (vs H93 +24.15%, +1.08%)
  - Top-5 Sharpe: **9.96** (vs H93 15.08, **-5.12**)
  - Edge std: 2.53% (vs H93 1.60%, +0.93%)
- Verdict: **FAIL** (high-variance degradation from asymmetry dominates).

---

## Session Conclusion

1. **LLM is parked clearly**; not an active path until throughput/runtime constraints are resolved.
2. **H101 (dispersion regime) is the best next-step dense signal among tested options**.
3. **H100 and H102 are rejected for RL-signal quality** due to volatility inflation despite higher raw edge.
