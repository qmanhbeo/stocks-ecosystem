# Session 115 Log

## H462: activation_rate_hidden_signal

**Hypothesis:** H388/H395 tested membership (fresh vs stale), not VELOCITY of activation. A stock suddenly appearing might signal different info than gradual entry. Test rank_change speed × vol_expansion vs forward IC.

**Command / code:** `python analysis/h462_activation_rate_hidden_signal.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/order_stats/cafef/order_stats_daily.parquet` - order stats

**Saved artifact:**
`artifacts/run_summaries/20260508_182313_activation_rate_hidden_signal_research_branch.json`

### Results

| State | IC | Lift vs Baseline | Notes |
|-------|-----|------------------|-------|
| all_rows (baseline) | 0.1298 | 0.0000 | |
| buy_heavy_expansion | 0.2105 | +0.0807 | H451 baseline |
| rank_accel_sell_expansion | 0.1705 | +0.0407 | Sell pressure building |
| rank_accel_buy_expansion | 0.1521 | +0.0223 | WORSE than baseline |
| rank_accel_expansion | 0.1465 | +0.0167 | |
| rank_stable | 0.1292 | -0.0006 | |
| rank_accelerating | 0.1132 | -0.0166 | ANTI-predictive |
| high_rank_expansion | 0.1131 | -0.0167 | |
| rank_decel_buy_expansion | 0.0872 | -0.0426 | Anti-predictive |
| low_rank_expansion | 0.0519 | -0.0779 | Anti-predictive |
| rank_decelerating | 0.0633 | -0.0665 | ANTI-predictive |

### Key Findings

1. **Rank acceleration is ANTI-predictive when used alone**
   - rank_accelerating: IC=0.1132 (-0.0166 lift) - below baseline
   - rank_decelerating: IC=0.0633 (-0.0665 lift) - strongly anti-predictive
   - rank_stable: IC=0.1292 (-0.0006 lift) - neutral

2. **Rank acceleration DOES NOT improve buy_heavy_expansion**
   - rank_accel_buy_expansion: IC=0.1521 (+0.0223 lift)
   - vs buy_heavy_expansion: IC=0.2105 (+0.0807 lift)
   - IMPROVEMENT: -0.0584 (MUCH WORSE!)
   - Adding rank acceleration HURTS the signal

3. **Surprising: rank_accel_sell_expansion is positive**
   - IC=0.1705 (+0.0407 lift)
   - This suggests: buy pressure DECREASING (acceleration negative) + sell-heavy + vol expansion = sell pressure building
   - But this is a different mechanism than the hypothesis

4. **High/low rank × vol are anti-predictive**
   - high_rank_expansion: IC=0.1131 (-0.0167) - high rank alone is not good
   - low_rank_expansion: IC=0.0519 (-0.0779) - contrarian in vol expansion doesn't work

**Decision Rule:**
- If rank acceleration adds >0.005 IC lift: PASSED
- Else: FAILED

**Verdict: FAILED** (Dead-end D040)

### Why Failed
- Rank acceleration is ANTI-predictive as a standalone signal
- Adding rank acceleration to buy_heavy_expansion makes it MUCH WORSE
- The hypothesis that "suddenly appearing = hidden info" is not supported
- High/low rank are anti-predictive

### Note
- rank_accel_sell_expansion might be worth exploring separately (different mechanism)
- But H462 as designed is a dead-end

---

Session 115 - 2026-05-08