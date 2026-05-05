# Session 283 Log

**Date**: 2026-05-05
**Focus**: H402 `shadow_liquidity_gravity_well`

## Summary

- Activated the ninth S272/S273 eureka queue item.
- Added `analysis/h402_shadow_liquidity_gravity_well.py`.
- Tested order fragmentation proxies (buy-count/volume ratio, avg buy-sell size)
  versus raw C16 order pressure.
- Verdict: **MIXED**. Fragmentation adds marginal IC beyond C16 but with poor
  year consistency.

## H402 - Shadow Liquidity Gravity Well

**Hypothesis:**
Order counts and average order size should approximate missing book depth
through fragmentation. Test whether this contains information beyond raw C16.

**Command / code:**
```bash
python alpha-research-lab/analysis/h402_shadow_liquidity_gravity_well.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1 panel)
- `data/features/xs_order_pressure_daily.parquet` (C16)
- `data/order_stats/cafef/order_stats_daily.parquet` (fragmentation proxies)

**Protocol:**
- No `2026+` rows.
- Test years `2018-2025`.
- Panel rows with both C16 and order-stats coverage.
- Fixed state definitions: high fragmentation bucket (top 20%), positive avg size.

| Proxy | Overall IC | Positive Years |
|-------|----------|-------------|
| C16 | -0.02967 | 0/8 |
| Fragmentation ratio | -0.02214 | 2/8 |
| Avg buy-sell size | +0.03033 | - |

| Year | C16 IC | Fragmentation IC |
|------|-------|---------------|
| 2018 | -0.02837 | -0.03737 |
| 2019 | -0.01072 | -0.02354 |
| 2020 | -0.03894 | -0.02594 |
| 2021 | -0.02589 | +0.00757 |
| 2022 | -0.04218 | -0.03908 |
| 2023 | -0.02185 | +0.00143 |
| 2024 | -0.02886 | -0.03394 |
| 2025 | -0.04623 | -0.01069 |

**Saved artifact:**
`artifacts/run_summaries/20260505_230157_shadow_liquidity_gravity_well_research_branch.json`

**Result:**
- Panel rows: 648,164
- Fragmentation vs C16 IC lift: +0.00753 (marginal)
- Fragmentation positive years: 2/8 (poor consistency)
- Avg buy-minus-sell size standalone: +0.03033 IC (best proxy)

**Verdict: MIXED**

Fragmentation adds marginal IC beyond C16 (+0.00753), but:
- C16 itself is negative IC (-0.02967), so lift is against a weak baseline
- Year consistency is poor (2/8 positive)
- The only positive proxy is avg buy-minus-sell size at +0.03033

Do not promote fragmentation as a ranker. Could reopen with:
- Fragmentation inside high-C16 conditioning only
- Avg-size positive as a high-C16 conditioner
- Materially different queue/open-fill data

**Next item**: H403 `anti_signal_annihilation_veto` (queue item 8)
Source anchor: F366