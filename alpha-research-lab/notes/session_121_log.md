# Session 121 Log — 2026-05-08

## H472: liquidity_adjusted_return

**Decision: FAILED**

### Hypothesis
Return normalized by Amihud illiquidity (|return| / turnover) captures "quality of flow":
high ratio (return despite liquidity) = institutional demand; low ratio = fragile illiquid returns.
Test 5d return / 20d avg Amihud quintiles vs forward IC.

### Command / code
```bash
python analysis/h472_liquidity_adjusted_return.py
```

### Inputs
- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet` (start_year=2018)
- OHLCV: 406 per-ticker 1D files from `data/stock/gia_lich_su_*_1D.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`

### Saved artifact
`artifacts/run_summaries/20260508_193633_liquidity_adjusted_return_research_branch.json`

### Results

| State | IC | Lift vs Baseline | Positive Years |
|-------|-----|-------------------|----------------|
| all_rows (baseline) | 0.1194 | — | 8/8 |
| return_5d_pos_illiq | 0.1632 | **+0.0438** | 8/8 |
| mid_lar (Q3) | 0.1448 | +0.0254 | 8/8 |
| high_lar_expansion | 0.1343 | +0.0149 | 8/8 |
| low_lar_expansion | 0.1158 | -0.0036 | 8/8 |
| high_lar (Q5) | 0.0873 | **-0.0321** | 8/8 |
| low_lar (Q1) | 0.0809 | -0.0385 | 8/8 |
| return_5d_pos_liq | 0.0524 | **-0.0670** | 8/8 |

Panel: 646,982 rows, 2018–2025.

### Interpretation

**LAR ratio alone is anti-predictive**: high LAR (Q5) = IC 0.087 (-0.032 lift) —
investors chasing "efficient" stocks do worse. Mid LAR (Q3) is strongest at +0.025 lift.
This is the OPPOSITE of the hypothesis; "return despite liquidity" = crowd-following, not institutional depth.

**return_5d_pos_illiq = IC 0.163 (+0.044 lift)**: positive 5d return + low liquidity (high Amihud)
is the strongest state. This is the illiquid momentum / C23-style effect — stocks moving up in
thin markets, not "flow quality." Confirms H447 contrarian and H432/H463 patterns.

**return_5d_pos_liq = IC 0.052 (-0.067 lift)**: positive 5d return in liquid stocks is the WORST state.
"Real force" (liquid + rising) = crowd blowoff. Confirms D036.

**high_lar_expansion = IC 0.134 (+0.015)**: LAR works better with vol expansion, but not enough
to overcome the anti-predictive baseline effect.

**C23 reference**: 0.2616 vs this best at 0.163. LAR adds no incremental value over raw illiq.

### Result: FAILED

The LAR ratio is anti-predictive as a standalone ranker. The mechanism is inverted:
"high return + low Amihud" = liquid crowd chase (negative), while "high return + high Amihud"
= illiquid momentum (positive, aligns with C23). The ratio collapses two correlated effects
into one confusing metric that loses to the raw components.

**Key finding**: In VN market, illiquid stocks amplify everything. The Amihud LEVEL (C23) is
the signal, not the return/Amihud RATIO.

### Verdict: FAILED

**Next:** Queue item AL (liquidity_adjusted_return) is DEAD-END. Continue with AM (news_velocity_as_signal)
— 3d article count delta — using existing news features. Do not reopen LAR ratio as a standalone ranker.
The `return_5d_pos_illiq` state is a weak confirmation of C23 but not an independent signal.