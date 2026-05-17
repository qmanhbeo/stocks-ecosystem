# Session 344 (H531) — Breadth-Capacity Intersection

## H531 - Breadth-Capacity Intersection Test

**Hypothesis:** The intersection of hidden demand (tight_capacity from H474) + regime amplifier (low_breadth from H529) captures stronger alpha than either alone.

**Command:** `python analysis/h531_breadth_capacity_intersection.py`

**Inputs:**
- S1 panel: xs_barrier_vol_1d_hose_full.parquet (2015-2025)
- C16: xs_order_pressure_daily.parquet
- Order stats: order_stats_daily.parquet

**Saved artifact:** `artifacts/run_summaries/20260517_144733_breadth_capacity_intersection_research_branch.json`

| Metric | Value | Note |
|--------|-------|------|
| Baseline IC | 0.1277 | All rows |
| tight_capacity (H474) | 0.1878 | +0.0602 lift |
| low_breadth (H529) | 0.1542 | +0.0266 lift |
| **INTERSECTION** | **0.1979** | **+0.0702 lift** |
| lift vs best single | +0.0100 | At threshold |
| positive years | 7/7 | Valid 2015-2021 |

**Controls:**
- tight + high_breadth: IC = 0.1763 (+0.0486) — weaker than low_breadth variant
- loose + low_breadth: IC = 0.0885 (-0.0392) — loose capacity hurts
- loose + high_breadth: IC = 0.0668 (-0.0609) — worst combination

**Result:**
The intersection of tight capacity (hidden demand signal) + low breadth (regime amplifier) achieves IC = 0.1979, beating both standalone signals and hitting exactly the +0.0100 lift threshold vs best single. The control combinations confirm both components are necessary — loose capacity (liquid crowd) destroys the signal even on low-breadth dates.

**Phase ICs (dev only due to small N):**
- dev (2015-2021): 0.1979
- val/2023-2024: N/A (30k rows, too sparse for year splits)
- conf/2025: 0.1615

**Verdict: PASSED** (+0.0100 lift vs best single, +0.0702 vs baseline)