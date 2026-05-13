# Session 137 - 2026-05-10

## Batch 17: cross_signal_day_complementarity (BU4)

**Hypothesis:** C23/C24/C25/C26 fire on different days. Route to whichever fires that day vs always-using-best-single. Different from D041 (COMBO kill) - this is SELECTIVE ROUTING.

**Test:** signal_day_union (any of C23/C24/C25/C26 fires that day) vs always-C23 vs cofire_2

**Results:**

| Metric | Value | Note |
|--------|-------|------|
| Baseline IC | 0.1302 | All S1 rows |
| Always C23 IC | 0.2176 | +0.0874 lift |
| Any signal (union) IC | 0.1753 | +0.0451 lift |
| Co-fire 2+ IC | 0.2069 | +0.0767 lift |
| Decision | PASSED | |

**Key findings:**
- Always-C23 remains STRONGEST at +0.0874 IC lift (IC 0.2176)
- Any-signal union is WEAKER than always-C23 (+0.0451 vs +0.0874)
- Co-fire 2+ is strong (+0.0767, IC 0.2069) - confirms F412 regime strength
- Signal routing does NOT beat always-C23

**Batch 17 status:**
- BU1 (market_wide_vol): MIXED - market-level works but weaker than ticker-level
- BU2 (c17_standalone): FAILED - raw C17 worse than ranked C16 (D049)
- BU3 (multi_day_c23): MIXED - 2d marginally best, 3d degrades
- BU4 (cross_signal_day_complementarity): PASSED but confirms C23 alone is best

**Next:**
- BU5 pending (sector_vol_regime)
- AS pending (intraday gating)

---