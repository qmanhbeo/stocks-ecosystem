# Session 36 Log — Earnings Calendar Dense Branch (2026-03-26)

## Objective
- Run next high-value dense experiment: earnings/reporting calendar.
- Keep standalone significance gate explicit for RL suitability.

---

## Implemented

### H104 — Earnings Calendar Features
- Script: `data_tools/build_earnings_calendar_features.py`
- Output: `data/features/xs_earnings_calendar_daily.parquet` (2,748 rows, dense)
- Features:
  - `days_since_q_end`, `days_to_next_q_end`
  - reporting-window flags (`15-45`, `20-50`, `30-60` days after quarter end)
  - `pre_q_end_10d`, `post_q_end_10d`
  - `quarter_phase`, `quarter_phase_sin/cos`
  - quarter flags `q1..q4`

### WF integration
- `cross_sectional_wf.py` new flag:
  - `--use-earnings-calendar`

---

## Results

### H104 (H93 + earnings calendar)
- Probas: `data/features/xs_barrier_vol_1d_h104_earn_cal_hose_full.parquet`
- Portfolio:
  - IC: **+0.1480** (vs H93 +0.1491, −0.0011)
  - Top-5 edge: **+24.14%** (vs +24.15%, flat)
  - Sharpe: **11.80** (vs 15.08, −3.28)
  - Std: 2.05% (vs 1.60%, +0.45)
- Verdict: **FAIL** (risk-adjusted degradation).

### H105 (H101 + earnings calendar)
- Probas: `data/features/xs_barrier_vol_1d_h105_disp_earn_hose_full.parquet`
- Portfolio:
  - IC: **+0.1466** (vs H101 +0.1474, −0.0008)
  - Top-5 edge: **+24.16%** (vs H101 +23.83%, +0.33)
  - Sharpe: **11.96** (vs H101 15.34, −3.38)
  - Std: 2.02% (vs 1.55%, +0.47)
- Verdict: **FAIL** (hurts best dense branch).

---

## Standalone Gate (earnings calendar)

Standalone IC tests against label `actual` are weak:
- `days_since_q_end`: avg IC +0.0060 (6/11 positive years)
- `in_report_w15_45`: avg IC +0.0059 (8/11)
- `in_report_w20_50`: avg IC +0.0014 (8/11)
- Other phase features near zero

Context checks vs S1 daily top-5 hit-rate are also weak:
- `in_report_w20_50` Spearman: −0.0041 (p=0.832)
- `quarter_phase_sin` Spearman: −0.0311 (p=0.103)

Interpretation:
- Earnings calendar is dense but too weak as standalone signal in this setup.

---

## Session Conclusion

1. Earnings calendar branch (H104/H105) is rejected.
2. Standalone gate remains active and was satisfied procedurally.
3. H101 remains best post-LLM-park dense branch.
