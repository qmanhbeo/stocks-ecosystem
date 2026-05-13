# Session 110 Log

## H454: implied_limit_proximity

**Hypothesis:** price_change_raw strings encode limit proximity. Near-limit + vol expansion might signal queue exhaustion (many buyers waiting, vol expanding = stress, reversal).

**Command / code:** `python analysis/h454_implied_limit_proximity.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/order_stats/cafef/order_stats_daily.parquet` - price_change_raw

**Saved artifact:**
`artifacts/run_summaries/20260508_180706_implied_limit_proximity_research_branch.json`

### Results

| State | IC | Lift vs Baseline | Notes |
|-------|-----|------------------|-------|
| all_rows (baseline) | 0.1298 | 0.0000 | |
| approaching_ceiling_expansion | 0.2170 | +0.0872 | **STRONGEST** |
| approaching_ceiling | 0.2166 | +0.0868 | Strong alone |
| near_limit_expansion | 0.1963 | +0.0665 | |
| near_limit | 0.1932 | +0.0634 | |
| vol_expansion | 0.1753 | +0.0455 | |
| approaching_floor_expansion | 0.1611 | +0.0313 | |
| near_limit_contraction | 0.1578 | +0.0280 | |
| near_limit_high_vol_expansion | 0.1375 | +0.0077 | Weaker with vol |
| low_move | 0.1060 | -0.0238 | Underperforms |

### Key Findings

1. **Limit proximity is a strong standalone signal**
   - approaching_ceiling: IC=0.2166, +0.0868 lift, 11/11 positive years (36,669 rows)
   - near_limit: IC=0.1932, +0.0634 lift, 11/11 positive years (72,705 rows)
   - Both are stronger than vol_expansion alone

2. **Approaching ceiling is the strongest limit-proximity state**
   - approaching_ceiling (+5% to +7%): IC=0.2166
   - near_limit (|pct| >= 5%): IC=0.1932
   - The near-ceiling momentum effect is very strong

3. **Vol expansion adds marginal value to limit proximity**
   - approaching_ceiling_expansion: IC=0.2170 vs approaching_ceiling: IC=0.2166
   - Delta: only +0.0004 lift from adding vol_expansion
   - Near-limit is the dominant signal, vol regime is secondary

4. **Approaching floor (sell-side) is weaker than ceiling**
   - approaching_floor_expansion: IC=0.1611, +0.0313 lift
   - at_floor (-7%): only 1 valid year (too sparse)
   - The buy-side queue is stronger than sell-side in VN market

5. **High volume WITH near-limit is WEAKER**
   - near_limit_high_vol_expansion: IC=0.1375, +0.0077 lift
   - This contradicts the "queue pressure" hypothesis
   - The signal is pure price momentum, not volume-augmented

6. **Low-move stocks underperform**
   - low_move: IC=0.1060, -0.0238 lift
   - No momentum = bad

### Decision Rule
- If near_limit × vol_expansion lift > 0.01 AND > near_limit alone: PASSED
- Result: PASSED but the signal is limit proximity ALONE, not limit × vol combo
- Vol expansion adds minimal value to limit proximity

**Verdict: PASSED** - limit proximity is a NEW SIGNAL (C22)

### New Signal Discovered
- **C22: limit_approaching_ceiling** - stocks approaching the +7% daily limit are strong momentum signals
- This is the UPWARD limit queue effect, not a reversal pattern
- Use as regime-independent ranker, not vol-conditioned

---

Session 110 - 2026-05-08