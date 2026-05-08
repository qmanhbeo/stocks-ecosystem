# Session 109 Log

## H453: order_flow_imbalance_momentum

**Hypothesis:** H451 tested LEVEL × vol_regime. What about CHANGE in imbalance? Acceleration in buy pressure might signal hidden demand better than level alone.

**Command / code:** `python analysis/h453_order_flow_imbalance_momentum.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/order_stats/cafef/order_stats_daily.parquet` - buy_sell_volume_imbalance

**Saved artifact:**
`artifacts/run_summaries/20260508_180257_order_flow_imbalance_momentum_research_branch.json`

### Results

| State | IC | Lift vs Baseline | Notes |
|-------|-----|------------------|-------|
| all_rows (baseline) | 0.1301 | 0.0000 | |
| sell_heavy_decel_expansion | 0.2369 | +0.1069 | **STRONGEST** |
| buy_heavy_accel_expansion | 0.2320 | +0.1019 | **NEW SIGNAL** |
| sell_heavy_expansion | 0.2310 | +0.1009 | H451 reference |
| accel_expansion | 0.2126 | +0.0825 | |
| buy_heavy_expansion | 0.2110 | +0.0809 | H451 (level only) |
| decel_expansion | 0.1999 | +0.0698 | |
| imbalance_accelerating | 0.1601 | +0.0300 | delta alone |
| imbalance_decelerating | 0.1503 | +0.0202 | delta alone |
| vol_expansion | 0.1756 | +0.0455 | |

### Key Findings

1. **Level + delta + vol combos are the strongest signals**
   - sell_heavy_decel_expansion: IC=0.2369, +0.1069 lift, 11/11 positive years
   - buy_heavy_accel_expansion: IC=0.2320, +0.1019 lift, 11/11 positive years

2. **Imbalance delta (acceleration) is independently informative**
   - imbalance_accelerating alone: IC=0.1601, +0.0300 lift
   - imbalance_decelerating alone: IC=0.1503, +0.0202 lift
   - Both are meaningful signals beyond level alone

3. **Delta × vol_expansion matches Level × vol_expansion**
   - accel_expansion: IC=0.2126, +0.0825 lift
   - buy_heavy_expansion (level only): IC=0.2110, +0.0809 lift
   - Delta vs level lift: +0.0016 (about equal)

4. **Selling pressure DECREASING in vol expansion is a strong signal**
   - decel_expansion: IC=0.1999, +0.0698 lift (11/11 positive years)
   - sell_heavy_decel_expansion: IC=0.2369, +0.1069 lift
   - This captures the exhaustion/reversal pattern in volatile markets

5. **Stable imbalance underperforms**
   - imbalance_stable: IC=0.1060 (below baseline 0.1301)
   - No change in imbalance is predictive of weakness

### Decision Rule
- If buy_heavy_accel_expansion IC > 0.01 lift AND > H451 reference: PASSED
- Result: PASSED - both level+delta+vol combos beat H451 reference

### New Signals Captured
- **Imbalance momentum**: delta of buy_sell_volume_imbalance captures acceleration/deceleration
- **Level + delta + vol combo**: combining current level AND momentum with vol regime
- **Sell-side exhaustion**: selling pressure decreasing in vol expansion = reversal signal

**Verdict: PASSED** - NEW SIGNALS CONFIRMED

## Next Queue Items
- AQ: low_vol_low_return_regime (tested in H449 - vol_contraction_exhaustion had negative IC = dead-end D037)
- Consider activation state integration for H453 findings

---

Session 109 - 2026-05-08