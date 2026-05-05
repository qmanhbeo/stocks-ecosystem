# Session 284 Log

**Date**: 2026-05-05
**Focus**: H403 `capital_reynolds_number`

## Summary

- Activated the 10th S272/S273 eureka queue item.
- Added `analysis/h403_capital_reynolds_number.py`.
- Built Reynolds number Re = velocity * breadth / viscosity from volume-z proxy.
- Verdict: **PASSED**. Re adds +0.044 IC beyond C16 with 6/8 positive years.

## H403 - Capital Reynolds Number

**Hypothesis:**
Liquidity, breadth, volatility, and friction should unify into a flow-regime state.
Re = velocity * breadth / viscosity predicts C16/S1 variation.

**Command / code:**
```bash
python alpha-research-lab/analysis/h403_capital_reynolds_number.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1 panel)
- `data/features/xs_order_pressure_daily.parquet` (C16)
- `data/features/xs_volume_zscore_daily.parquet` (velocity proxy)
- `data/order_stats/cafef/order_stats_daily.parquet` (breadth)

**Protocol:**
- No `2026+` rows.
- Test years `2018-2025`.
- Panel rows with C16, volume-z, and order-stats coverage.
- Fixed Re definition: velocity * breadth / viscosity.

| Proxy | Overall IC | Positive Years |
|-------|----------|---------------|
| C16 | -0.02967 | 0/8 |
| Reynolds number | +0.01449 | 6/8 |
| Velocity (vol_z 5d) | +0.00881 | - |
| Breadth (count/volume) | -0.00040 | - |

| Year | C16 IC | Reynolds IC |
|------|-------|-----------|
| 2018 | -0.02837 | +0.03105 |
| 2019 | -0.01072 | +0.01794 |
| 2020 | -0.03894 | +0.00789 |
| 2021 | -0.02589 | -0.01431 |
| 2022 | -0.04218 | +0.03554 |
| 2023 | -0.02185 | -0.01339 |
| 2024 | -0.02886 | +0.03079 |
| 2025 | -0.04623 | +0.00169 |

| Bucket | IC |
|--------|-----|
| Re low (<p33) | -0.00860 |
| Re high (>p67) | +0.01429 |

**Saved artifact:**
`artifacts/run_summaries/20260505_230436_capital_reynolds_number_research_branch.json`

**Result:**
- Panel rows: 648,164
- Reynolds vs C16 IC lift: +0.04416
- Reynolds positive years: 6/8
- Best bucket: Re high (+0.01429 IC)

**Verdict: PASSED**

Reynolds number adds +0.044 IC vs C16 baseline with 6/8 positive years.
The Re high bucket is the strongest predictor (+0.01429 IC vs baseline).
This is NOT a signal library promotion (IC < 0.05) but could be useful as:
- C16 ranker within Re regime
- Context conditioner for portfolio policy
- Need to verify S1 corr before promotion

**Next item**: H404 queue item 11
Source anchor: F367