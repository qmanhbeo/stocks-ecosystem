# Session 275 Log

**Date**: 2026-05-05
**Focus**: H394 `oracle_shadow_regime_distiller`

## Summary

- Activated the first S272/S273 eureka queue item.
- Added `analysis/h394_oracle_shadow_regime_distiller.py`, a reusable rolling
  date-regime audit built on the new experiment scaffold.
- Tested whether the leaky S24x target-breadth regime has an honest
  pre-decision shadow using S1/C16/order/news/market/tradability date
  aggregates.
- Verdict: **MIXED / park broad predicted-weather promotion**.

## H394 - Oracle Shadow Regime Distiller

**Hypothesis:**
The invalid S24x target-derived market states were accidentally measuring
future S1 barrier-hit breadth. If that latent "weather" can be predicted from
decision-time observables, then predicted weather should honestly bucket S1 or
C16 IC better than VNI-down and random same-date regimes.

**Command / code:**
```bash
python alpha-research-lab/analysis/h394_oracle_shadow_regime_distiller.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_order_pressure_daily.parquet`
- `data/order_stats/cafef/order_stats_daily.parquet`
- `data/features/news/datasets/news_daily_features.parquet`
- `data/features/execution/tradability_daily.parquet`
- `data/features/xs_price_limit_daily.parquet`
- OHLCV / VNINDEX stock files through `src/standalone_signal_utils.py`

**Protocol:**
- No `2026+` rows.
- Train/test years: rolling train-before-test, test years `2018-2025`.
- Date target: `target_hit_rate`, the date-level mean of S1's future
  `s1_barrier_hit_1d`; target-only.
- Honest state: fixed train-quantile buckets of rolling ridge predictions.
- Diagnostic-only state: actual target-breadth quantiles, retained only as an
  upper-bound leakage check.
- Promotion gate: predicted breadth avg date IC `>= +0.10`, at least `60%`
  positive years, and predicted-weather bucket lift `>= +0.01` versus all rows
  plus `>= +0.005` versus random same-date buckets.

**Saved artifact:**
`artifacts/run_summaries/20260505_170942_h394_oracle_shadow_regime_distiller_research_branch_oracle_shadow_regime_distiller.json`

| Metric | Value | Note |
|--------|-------|------|
| Ridge predicted-breadth avg date IC | `+0.05019` | `7 / 8` positive years, but below `+0.10` gate |
| S1-mean breadth baseline avg date IC | `+0.00523` | weak |
| Best honest predicted bucket | `ridge_pred_low20` on C16 | best predicted-weather state |
| `ridge_pred_low20` C16 avg IC | `+0.07862` | all-row C16 `+0.07519` |
| `ridge_pred_low20` lift vs all C16 | `+0.00342` | below `+0.01` gate |
| `ridge_pred_low20` lift vs random dates | `+0.00416` | below `+0.005` gate |
| `ridge_pred_low20` S1 lift | `-0.00708` | predicted bad weather degraded S1 |
| `observed_vni_down_2d` C16 lift | `+0.00582` | cleaner than ridge weather |
| `observed_vni_down_2d` S1 lift | `+0.01230` | also cleaner than ridge weather |
| Leaky oracle low-breadth C16 lift | `+0.01575` | diagnostic only; target-derived |

**Result:**
There is a weak but real-looking observable shadow of target breadth:
`ridge_pred` beats S1 mean and VNI return as a date-level breadth predictor and
is positive in `7 / 8` test years. However, the honest predicted-weather
states do not clear the signal-conditioning gate. The leaky oracle remains much
larger, which confirms the S272 warning: the old state had access to future
breadth information that the current observables only weakly approximate.

The cleaner practical context remains observable `VNI down 2d`, not the broad
ridge-predicted weather state.

**Verdict: MIXED**

**Next action:**
Park broad `oracle_shadow_regime_distiller` promotion under this contract. Move
to the next queue item, `weak_signal_quorum_sleeve`. Reopen H394 only with a
materially different fixed regime target, intraday/opening data, or a consumer
that uses weak date-weather as one vote rather than a promoted standalone
regime.

## Closeout

- Saved artifact was read before the verdict.
- Branch status changed to mixed/parked; no live branch changed.
- Memory write-back done in live state, compact notes, findings, and dead ends.
- `2026+` data was avoided.
- The target-derived oracle states are diagnostic only and were not used for
  promotion.
- No heavy job remains active.
