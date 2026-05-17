# Session 345 (H532) — Breadth-Triggered Entry Decay Detection

## H532 - Breadth-Triggered Entry Decay Detection

**Hypothesis:** Signal quality rebounds after high-breadth spike days. Compare IC 1d/3d/5d post-high-breadth.

**Command:** `python analysis/h532_breadth_triggered_decay.py`

**Inputs:**
- S1 panel: xs_barrier_vol_1d_hose_full.parquet (2015-2025)
- C16: xs_order_pressure_daily.parquet

**Saved artifact:** `artifacts/run_summaries/20260517_145111_breadth_triggered_decay_research_branch.json`

| Metric | Value | Note |
|--------|-------|------|
| Baseline IC | 0.1277 | All rows |
| Same-day high breadth | 0.1085 | -0.0191 lift (crowded) |
| Post-highbreadth 1d | 0.1158 | -0.0119 vs baseline |
| Post-highbreadth 3d | 0.1170 | -0.0107 vs baseline (best post) |
| Post-highbreadth 5d | 0.1128 | -0.0149 vs baseline |
| **lowbreadth_post_spike** | **0.1982** | **+0.0706 vs baseline** |

**Analysis:**
- Post-spike alone (best 0.1170) still below baseline (-0.0107)
- Post-spike vs same-day high-breadth: +0.0084 lift (below +0.01 threshold)
- **Key finding**: Low breadth + post-spike combo achieves IC=0.1982, even stronger than H531's 0.1979!

**Result:**
The standalone hypothesis FAILED — post-spike alone doesn't beat baseline. But the LOW BREADTH + POST-SPike combo is a new strong signal (IC=0.1982), confirming that low breadth is the key driver.

**Phase ICs (combo):** dev=0.2036, val=0.1804, conf=0.1430, 6/6 positive years

**Verdict: MIXED** — post-spike alone lifts vs high-breadth but < +0.01 threshold and still below baseline. Combo is strong.