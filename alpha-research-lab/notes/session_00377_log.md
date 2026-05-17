# Session 377 — 2026-05-17

## H80 - Capacity × Breadth Regime Interaction

**Hypothesis:** Test OR of tight+low_breadth AND active+low_breadth vs each component alone to see if broader coverage captures additional alpha.

**Source:** H565 tight+low_breadth (0.2062), H528 active+low_breadth (0.2013). Hypothesis: capacity and active are DIFFERENT mechanisms, not redundant.

**Command / code:** Inline Python test using S1 panel + order_pressure panel

**Inputs:**
- S1 panel: xs_barrier_vol_1d_hose_full.parquet
- C16 panel: xs_order_pressure_daily.parquet
- Years: 2015-2025

**Saved artifact:** None (inline test)

| Metric | Value | Note |
|--------|-------|------|
| all_rows baseline | IC=0.1277 (n=821,764) | |
| tight+low_breadth (H565) | IC=0.1993 (n=23,515) | |
| active+low_breadth (H528) | IC=0.2026 (n=15,126) | |
| OR (tight+low OR active+low) | IC=0.1993 (n=23,518) | |
| OR vs tight+low | -0.0000 | No lift |
| OR vs active+low | -0.0033 | Negative lift |
| Positive years | 10/11 | 2022 negative |

**Set overlap analysis:**
- tight+low only: 8,392
- active+low only: 3
- both (intersection): 15,123
- OR (union): 23,518
- Overlap: 64.3%

**Result:**
FAILED. The OR provides NO additional value. The two signals are essentially the same mechanism:
- active state (C16 <= 0.2) is almost entirely a subset of tight capacity (Q1 order_volume_ratio)
- 15,123 of 15,126 (99.98%) active+low stocks are already in tight+low
- The OR adds only 3 net new rows (8,392 tight-only + 3 active-only = 8,395 new vs 15,123 in intersection)
- The hypothesis that "capacity and active are different mechanisms" is falsified

**Verdict: FAILED (Dead-end D080)**

**Key structural insight:** H474 tight_capacity and active state (C16 <= 0.2) capture the same underlying phenomenon - they're not independent amplifiers. The active state is just a stricter filter on the tight capacity mechanism. This is consistent with H535 which found tight_capacity redundant when combined with active+low_breadth.

**Next action:** Move to H81 (Market Breadth Trend as Forward Signal) - tests 3-5d cumulative breadth trajectory.