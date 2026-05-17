# Session 379 — 2026-05-17

## H82 - Co-fire Degree as Hidden Demand Signal

**Hypothesis:** Test if ticker-level cofire degree (how many other tickers share signal on same day) predicts signal quality. Low cofire = isolated alpha (fewer competitors) = stronger signal.

**Source:** H137 (sector cofire strong), H543 composite, H507 family structure.

**Command / code:** Inline Python test using S1 panel + order_pressure panel

**Inputs:**
- S1 panel: xs_barrier_vol_1d_hose_full.parquet
- C16 panel: xs_order_pressure_daily.parquet
- Years: 2015-2025
- Signal: C23 (active + high illiq + vol expansion)
- Cofire quartile per date based on average cofire degree

**Saved artifact:** None (inline test)

| Metric | Value | Note |
|--------|-------|------|
| all_rows baseline | IC=0.1277 (n=821,764) | |
| signal (all dates) | IC=0.1564 (n=68,133) | |
| signal + isolated (Q1) | IC=0.2064 (n=10,427) | +0.0500 lift |
| signal + crowded (Q4) | IC=0.1259 (n=21,475) | -0.0305 lift |
| isolated vs crowded | +0.0805 | Strong separation |

**Year-by-year (Q1 isolated):**
- 2015-2025: 11/11 positive years
- Mean IC: 0.1774

**Result:**
PASSED with strong effect! Cofire degree is a significant signal conditioner:
- Isolated signals (few competitors) are significantly stronger
- Crowded signals (many competitors) are weaker than baseline
- The +0.0805 lift between Q1 vs Q4 is well above +0.01 threshold
- 11/11 positive years confirms robustness

**Verdict: PASSED (Finding F440)**

**Key insight:** This is a new regime signal - "cofire isolation" captures the difference between truly hidden demand (your signal is unique that day) vs crowded hidden demand (many others have the same signal). The mechanism is competitive crowding at the signal-detection level.

**Next action:** This is a promotion-worthy finding. Need to add to signal_library.md as a new conditioner. Continue with H83 (Tight Capacity × Sector Breadth Divergence) or document F440.