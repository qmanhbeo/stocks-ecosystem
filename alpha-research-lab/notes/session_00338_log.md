# Session 338 - 2026-05-17

### H525 - Cross-Sectional Breadth as Regime Signal
**Hypothesis:**
Test if date-level active-stock density (% of market in C23/C24) predicts forward IC. When many stocks activate together, it may be a regime signal.

**Command / code:**
`python analysis/h525_cross_sectional_breadth.py`

**Inputs:**
- S1 panel (xs_barrier_vol_1d_hose_full.parquet) 2015-2025
- C16 signals (xs_order_pressure_daily.parquet): order_volume_ratio_rank

**Saved artifact:**
- `artifacts/run_summaries/20260517_141225_cross_sectional_breadth_research_branch.json`

| Metric | Value | Note |
|--------|-------|------|
| Baseline IC | 0.1277 | all rows |
| High breadth IC | 0.1149 | top 20% dates |
| Low breadth IC | 0.1454 | bottom 20% dates |
| Lift (high - low) | -0.0305 | OPPOSITE of hypothesis |
| Lift vs baseline (high) | -0.0127 | worse than baseline |
| Lift vs baseline (low) | +0.0177 | better than baseline |
| High breadth phase ICs | dev=0.1099, val=0.1370, conf=0.1027 | degrades in 2025 |

**Result:**
- **FAILED**: High breadth dates have WORSE signal quality, opposite of hypothesis
- Low breadth (sparse activation) dates have BETTER signal quality (+0.0177 lift)
- Quintiles showed uniform IC (0.1454), suggesting breadth is binary (high/low matters, not gradations)
- Interpretation: When many stocks are in active state, it's a crowded regime with weaker IC

**Verdict: FAILED (as hypothesis) but found opposite effect**

**Next step:**
- Try next Eureka idea: Exit Timing Discovery (holding duration effects)
- Or note this as a regime filter: avoid high-breadth dates