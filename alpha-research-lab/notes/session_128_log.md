# Session 128: H479 adaptive_signal_weights

**Date:** 2026-05-09
**Hypothesis:** Weight C23-C26 by their recent 60d IC instead of equal weight. If IC-weighted outperforms, adaptive weighting adds value.

**Command:**
```bash
python analysis/h479_adaptive_signal_weights.py
```

**Inputs:**
- S1 from xs_barrier_vol_1d_hose_full.parquet (default)
- Order stats from order_stats/cafef/order_stats_daily.parquet
- Test years: 2015-2025

**Saved artifact:** artifacts/run_summaries/20260509_230557_adaptive_signal_weights_research_branch.json

**Results:**
| State | Avg IC | Lift vs baseline | Positive Years |
|-------|-------|----------------|---------------|
| IC-weighted composite | 0.1760 | +0.0465 | 11/11 |
| Equal weight composite | 0.1754 | +0.0458 | 11/11 |
| all_rows (baseline) | 0.1296 | - | 11/11 |

**Component ICs:**
- C26 (buy_heavy × illiq × vol_expansion): 0.2154
- C23 (high_illiq × vol_expansion): 0.1858
- C24 (ceiling_count × vol_expansion): 0.1754
- C25 (vwap_below × vol_expansion): 0.1754

**Result:** IC-weighted composite (0.1760) vs equal weight (0.1754) improvement is only +0.0007 — below the +0.005 MIXED threshold. Equal weight works just as well.

**Verdict: FAILED** - Adaptive IC-weighting adds no meaningful value over equal-weight. The signals don't have dramatically different ICs over time, so weighting doesn't help.

**Finding:** F406 - Equal-weight composite of C23-C26 captures the signal ensemble just as well as IC-weighted. The signals share vol_expansion as common amplifier, so their relative predictive power stays relatively stable. No adaptive weighting benefit found.

**Dead-end:** D043 - Adaptive signal weighting via rolling IC does NOT outperform equal weight for C23-C26. The ensemble is robust to weighting scheme.

**Source anchor:** F406

**Next action:** AU: extreme_negative_sentiment (next in queue)