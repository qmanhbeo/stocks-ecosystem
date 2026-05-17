# Session 378 — 2026-05-17

## H81 - Market Breadth Trend as Forward Signal

**Hypothesis:** Test 3-5d cumulative breadth trajectory. Low breadth after contracting vs V-shape vs sustained low. Mechanism: cumulative trend captures de-congestion vs re-congestion.

**Source:** H525 (level: high=bad), H542 (transition: tied), H562 (velocity: noise). None tested cumulative 3-5d trajectory.

**Command / code:** Inline Python test using S1 panel + order_pressure panel

**Inputs:**
- S1 panel: xs_barrier_vol_1d_hose_full.parquet
- C16 panel: xs_order_pressure_daily.parquet
- Years: 2015-2025
- 3-day breadth delta computed from active count per date

**Saved artifact:** None (inline test)

| Metric | Value | Note |
|--------|-------|------|
| all_rows baseline | IC=0.1277 (n=821,764) | |
| raw low_breadth | IC=0.1546 (n=130,208) | |
| low_breadth + contracting | IC=0.1554 (n=83,877) | +0.0008 lift |
| low_breadth + expanding | IC=0.1629 (n=36,501) | +0.0084 lift |

**Result:**
MIXED / FAILED. The effect goes OPPOSITE to hypothesis:
- Hypothesis: contracting (fewer active = de-congestion) = stronger signal
- Reality: expanding (more active) is STRONGER (+0.0084) than contracting (+0.0008)
- Both lifts are below +0.01 threshold - not actionable
- 11/11 positive years for both conditions

**Key insight:** The direction of recent breadth change adds no actionable value beyond raw low_breadth level. H525/H542/H562 already established this - breadth level matters, not the path.

**Verdict: FAILED (Dead-end D081)**

**Next action:** Move to H82 (Co-fire Degree as Hidden Demand Signal)