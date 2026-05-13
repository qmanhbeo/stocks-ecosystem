# Session 111 Log

## H455: sector_momentum_as_regime_not_filter

**Hypothesis:** S248-S252 used sector as FILTER (failed). Use SECTOR RETURN as REGIME to gate signal behavior: C16, C19, C20, S1 IC in sector_up vs sector_down separately.

**Command / code:** `python analysis/h455_sector_momentum_as_regime_not_filter.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/order_stats/cafef/order_stats_daily.parquet` - order stats for signals

**Saved artifact:**
`artifacts/run_summaries/20260508_181059_sector_momentum_as_regime_not_filter_research_branch.json`

### Results

| State | IC | Lift vs Baseline | Notes |
|-------|-----|------------------|-------|
| all_rows (baseline) | 0.1298 | 0.0000 | |
| buy_heavy_expansion | 0.2105 | +0.0807 | Signal alone |
| buy_heavy_expansion_sector_up | 0.2028 | +0.0730 | |
| buy_heavy_expansion_sector_down | 0.1902 | +0.0604 | |
| vol_expansion_sector_up | 0.1644 | +0.0346 | |
| vol_expansion_sector_down | 0.1627 | +0.0329 | |
| sector_down | 0.1301 | +0.0003 | |
| sector_up | 0.1234 | -0.0064 | |
| high_volume_sector_up | 0.0970 | -0.0328 | Negative |
| high_volume_sector_down | 0.0681 | -0.0617 | Negative |

### Key Findings

1. **Sector regime does NOT significantly change signal behavior**
   - vol_expansion regime diff (down - up): -0.0017 (essentially equal)
   - buy_heavy_expansion regime diff (down - up): -0.0127 (marginally different)
   - Both signals work similarly in both regimes

2. **Signals work slightly BETTER in sector_up (not down as hypothesized)**
   - buy_heavy_expansion_sector_up: IC=0.2028 vs sector_down: IC=0.1902
   - vol_expansion_sector_up: IC=0.1644 vs sector_down: IC=0.1627

3. **Sector regime has minimal baseline effect**
   - sector_up: IC=0.1234 (slightly below baseline)
   - sector_down: IC=0.1301 (slightly above baseline)
   - The market excess signal is not a strong regime indicator

4. **High volume is ALWAYS negative**
   - high_volume_sector_up: IC=0.0970 (-0.0328 lift)
   - high_volume_sector_down: IC=0.0681 (-0.0617 lift)
   - Pure volume level is not informative

5. **The signal regime router hypothesis fails**
   - S248-S252 failed as FILTERS, and now also fails as REGIME GATES
   - Signals don't need sector context to work better

**Decision Rule**
- If regime difference > 0.02 for any signal: PASSED
- If regime difference <= 0.01 for all signals: FAILED
- Result: FAILED - regime differences are small (-0.0017 to -0.0127)

**Verdict: FAILED** (Dead-end D038)

### Why Failed
- Sector momentum (market excess) is not a meaningful regime for signal gating
- Signals work similarly across regimes - no router benefit
- The hypothesis was that market DOWN regimes would amplify contrarian signals, but they don't

---

Session 111 - 2026-05-08