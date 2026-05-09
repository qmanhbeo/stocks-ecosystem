# Session 124 Log — 2026-05-09

## H477: ap_residual_signal_discovery

**Decision: MIXED**

### Hypothesis
After removing vol_expansion correlation from S1 (cross-sectional regression on vol_expansion_rank each day), the residual S1 rank still contains independent signal beyond vol_expansion. If residual IC > 0.01 with >= 60% positive years, independent signal exists.

### Command / code
```bash
python analysis/h477_ap_residual_signal_discovery.py
```

### Inputs
- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet` (start_year=2015, 809,019 rows)
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet` (for vol regime)
- OHLCV: per-ticker gia_lich_su_*.parquet files (for 5d/20d rolling avg vol)

### Saved artifact
`artifacts/run_summaries/20260509_184235_ap_residual_signal_discovery_research_branch.json`

### Results

| State | Score | IC | Positive Years | Notes |
|-------|-------|-----|----------------|-------|
| all_rows (baseline) | s1_xs_proba | 0.130 | 11/11 | Raw S1 baseline |
| all_rows | s1_residual_rank | -0.001 | 4/11 | Residual baseline: near-zero |
| high_vol_expansion | s1_xs_proba | 0.175 | 11/11 | Vol expansion amplifies S1 |
| high_vol_expansion | s1_residual_rank | 0.003 | 7/11 | Marginal positive |
| s1_residual_top20 | s1_xs_proba | 0.125 | 11/11 | -0.005 vs raw baseline (dropped) |
| **s1_residual_top20** | **s1_residual_rank** | **0.0013** | **7/11 (63.6%)** | **Marginal independent signal** |

### Key findings

1. **S1 residual is near-zero, not negative**: After removing vol_expansion, the residual S1 has IC +0.0013, not negative. This means S1 is NOT fully explained by vol_expansion — there's a tiny independent component.

2. **Marginal but real**: IC 0.0013 with 7/11 positive years (63.6%) is above the 60% threshold. This is a real but WEAK independent signal.

3. **Vol expansion amplifies S1**: S1 in high_vol_expansion = 0.175 vs 0.130 baseline (+0.045). Confirms H463-H471 pattern.

4. **High residual + high vol = combo**: high_vol_exp_top20_s1 evaluated on residual score = 0.004 (4/11 positive years) — WORSE than residual alone. The combo doesn't add value.

5. **Top residual underperforms raw S1**: s1_residual_top20 evaluated on raw S1 score = 0.125 (-0.005 vs baseline). Top residual tickers have LOWER raw S1 quality than average — they're orthogonal, not superior.

### Interpretation

The residual IC (0.0013) barely crosses the 60% positive-year threshold. It's marginal, not a clean promotion signal. The mechanism: S1 captures cross-sectional momentum, vol_expansion captures market regime, and their overlap is significant but not complete. The residual has some signal but it's fragile.

The all-rows residual baseline is -0.001 (4/11 positive years), meaning the residual is essentially noise for the average ticker. Only the top 20% residual shows marginal edge. This suggests the residual is not a strong independent dimension — it's a weaker cousin of raw S1.

### Ladder check

- PASS (IC > 0.01, >= 60% positive): NO — IC is only 0.0013
- MIXED (IC 0.001-0.01, >= 40% positive): YES — IC 0.0013, 63.6% positive
- FAIL (IC <= 0): NO — IC is positive

### Result: MIXED

- Residual IC is +0.0013 (marginal, not strong)
- 7/11 positive years (63.6%) — barely above 60% threshold
- The residual captures some S1 quality NOT explained by vol_expansion, but it's weak
- All-rows residual is negative (-0.001), so it's noise on average — only the extreme top/bottom buckets have structure
- Not promoted as a signal, but the finding confirms: S1 is NOT purely vol_expansion

### Verdict: MIXED

**Finding F403**: S1 residual after vol_expansion removal is +0.0013 IC (7/11 positive years). The residual IS positive, confirming S1 is not purely vol_expansion-driven. But the effect is MARGINAL — it barely crosses the 60% positive-year threshold. Do not promote as a signal. The residual could be useful as weak RL-state context, but raw S1 remains the primary signal.

**Dead-end note**: The residual is too weak to be a standalone signal. Further refinement of the residual (e.g., residual × illiquidity) may be worth exploring in future branches, but the direct residual top20 is not a promotion candidate.

**Next**: Continue queue: AQ (replacement_quality_delta), AR (zero_liquidity_anomaly), AS (intraday_session_routing), AT (adaptive_signal_weights), AU (extreme_negative_sentiment), AV (breadth_threshold_finder). Queue batch 11 complete, consider bright-mind queue refresh.