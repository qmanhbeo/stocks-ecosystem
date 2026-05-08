# Session 114 Log

## H461: momentum_regime_combo

**Hypothesis:** C21 sells/buys are strongest because they capture deceleration/acceleration in vol expansion. Can momentum (high/low return) improve the combo?

**Command / code:** `python analysis/h461_momentum_regime_combo.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/order_stats/cafef/order_stats_daily.parquet` - order stats

**Saved artifact:**
`artifacts/run_summaries/20260508_182042_momentum_regime_combo_research_branch.json`

### Results

| State | IC | Lift vs Baseline | vs C21 Baseline | Rows | Notes |
|-------|-----|------------------|-----------------|------|-------|
| sell_heavy_decel_expansion | 0.2393 | +0.1095 | baseline | 15,617 | C21 strongest |
| sell_heavy_decel_expansion_low_return | 0.2346 | +0.1048 | -0.0047 | 11,195 | Slightly worse |
| buy_heavy_accel_expansion | 0.2338 | +0.1040 | baseline | 24,658 | C21 baseline |
| buy_heavy_accel_expansion_high_return | 0.2321 | +0.1023 | -0.0017 | 20,227 | Slightly worse |
| buy_heavy_accel_expansion_low_return | NaN | NaN | NaN | 3,519 | Too sparse |
| sell_heavy_decel_expansion_high_return | NaN | NaN | NaN | 3,455 | Too sparse |
| vol_expansion | 0.1753 | +0.0455 | - | 162,883 | |

### Key Findings

1. **Momentum DOES NOT improve C21 combos**
   - buy_heavy_accel_expansion_high_return: -0.0017 vs C21 baseline
   - sell_heavy_decel_expansion_low_return: -0.0047 vs C21 baseline
   - Both are marginally WORSE, not better

2. **C21 signals are complete as-is**
   - The level + delta + vol combination already captures the signal
   - Adding return/momentum splits the sample without adding information

3. **C21 signals are CONTRARIAN in nature**
   - sell_heavy_decel = sell pressure DECREASING in vol expansion = exhaustion reversal
   - buy_heavy_accel = buy pressure INCREASING in vol expansion = hidden demand
   - Momentum (return) is NOT part of the mechanism

4. **Some momentum × C21 states too sparse**
   - buy_heavy_accel_expansion_low_return: only 3,519 rows (NaN IC)
   - sell_heavy_decel_expansion_high_return: only 3,455 rows (NaN IC)

**Decision Rule:**
- If momentum adds >0.005 IC lift: PASSED
- Else: MIXED

**Verdict: MIXED** - momentum doesn't improve C21; C21 signals are complete

---

Session 114 - 2026-05-08