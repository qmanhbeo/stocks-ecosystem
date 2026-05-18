# Session 404 - H618 Signal-Day Distribution as Hidden Regime

**Date**: 2026-05-18

## Hypothesis

Queue item 122: same-day multi-signal concentration should outperform spread-
across-days signal accumulation on the same ticker.

Definitions:
- same_day_multi: `signal_count >= 2` today
- spread_multi: `signal_count == 1` today and 3-day rolling `signal_count` sum >= 2

## Command

```bash
python analysis/h618_signal_day_distribution_regime.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_180932_h618_signal_day_distribution_regime_research_branch.json`
- Results: `artifacts/research_branches/20260518_180932_h618_signal_day_distribution_regime_results.parquet`
- Yearly: `artifacts/research_branches/20260518_180932_h618_signal_day_distribution_regime_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| same_day_multi | 0.2445 | 29,542 | 11/11 |
| spread_multi | 0.1821 | 17,867 | 11/11 |
| all_rows | 0.1298 | 809,019 | 11/11 |

Derived:
- lift(`same_day_multi` vs `spread_multi`) = `+0.0624`

## Result

Same-day multi-signal concentration is materially stronger than spread-across-
days accumulation under this contract.

## Verdict: PASSED

## Next

- Advance to queue item 123 (Post-Breadth-Spike Recovery Timing).
