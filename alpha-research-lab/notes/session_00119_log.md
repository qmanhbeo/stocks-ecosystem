# Session 119 Log — 2026-05-08

## H469: foreign_flow_momentum

**Decision: MIXED**

### Results
- ff_decel_exp: IC=0.1376 (+0.0074 lift, 11/11 pos years) — best
- all_rows: IC=0.1302 (baseline)
- ff_strong_buy_exp: IC=0.1280 (-0.0022)
- ff_accel_exp: IC=0.1243 (-0.0059)
- ff_strong_sell_exp: IC=0.1196 (-0.0107)

### Key insight
Foreign flow momentum (acceleration/deceleration) adds only modest signal.
`ff_decel_exp` (foreign decelerating in vol expansion) is marginally positive (+0.0074),
but no state beats C16 by more than +0.01. Direction-based states (strong buy/sell)
are all negative. H443 already killed raw direction variants. Momentum doesn't rescue it.
This is a soft filter only, not a promotion candidate.

---

## H470: vwap_deviation_regime

**Decision: PASSED**

### Results
- vwap_below_10_exp: IC=0.1733 (+0.0431 lift, 11/11 pos years) — **NEW SIGNAL C25: vwap_below_illiquid_expansion**
- vwap_below_20_exp: IC=0.1668 (+0.0366)
- vwap_dev_bot10: IC=0.1610 (+0.0308)
- vwap_dev_bot20: IC=0.1531 (+0.0229)
- vwap_above_90_exp: IC=0.1473 (+0.0171)
- all_rows: IC=0.1302 (baseline)

### Key insight
**VWAP far below average + vol expansion is a strong signal** (C25: IC=0.1733, +0.0431 lift).
Stocks trading far below their daily VWAP in expanding-volume markets are the strongest
new signal since C23 (illiq_expansion: IC=0.2616). Mechanism: VWAP below = stock is "cheap"
vs day's average; under-followed/illiquid stocks amplify this effect (similar to C23).
C25 beats C16 baseline by +0.0431 IC with 11/11 positive years.

---

## H471: order_flow_microstructure_regime

**Decision: PASSED**

### Results
- buy_heavy_illiq_exp: IC=0.1889 (+0.0587 lift, 11/11 pos years) — **NEW SIGNAL C26: buy_heavy_illiq_expansion**
- sell_heavy_illiq_exp: IC=0.1828 (+0.0526)
- buy_heavy_exp: IC=0.1680 (+0.0378)
- buy_heavy_exp_no_illiq: IC=0.1556 (+0.0254)
- buy_heavy_no_regime: IC=0.1498 (+0.0196)
- all_rows: IC=0.1302 (baseline)

### Key insight
**Buy-heavy order flow + illiquidity + vol expansion is the strongest order-flow signal** (C26: IC=0.1889, +0.0587 lift).
Buy-pressure imbalance in illiquid stocks during vol expansion is a powerful combination.
Mechanism: institutional hidden demand accumulates in illiquid names during volatile markets.
Both buy_heavy and sell_heavy work with illiq+expansion (different mechanisms:
buy = accumulation, sell = forced-sell rebound). Large order size + vol expansion is neutral.

---

## Session 119 Summary

**Batch 9 (sessions 119): H469 MIXED, H470 PASSED (C25 new signal), H471 PASSED (C26 new signal)**

### New signals:
- **C25**: `vwap_below_10_exp` — VWAP far below + vol expansion + illiquidity; IC=0.1733 (+0.0431 lift, 11/11)
- **C26**: `buy_heavy_illiq_exp` — Buy order imbalance + illiquidity + vol expansion; IC=0.1889 (+0.0587 lift, 11/11)

### Pattern discovered:
All strong signals share a common structure: **specific behavior + illiquidity + vol_expansion**.
- C23 (illiq_expansion): illiquidity × vol_expansion
- C24 (multi_day_ceiling_pressure): ceiling count × vol_expansion (multi-day beats single-day)
- C25 (vwap_below_illiq_expansion): VWAP deviation + illiquidity + vol_expansion
- C26 (buy_heavy_illiq_expansion): order flow + illiquidity + vol_expansion

### D041 implication (CONFIRMED):
Signals are NOT orthogonal — they share vol_expansion + illiquidity as the universal amplifier.
Do NOT combine as composite entries. Each signal captures a different facet of the same regime.

### Next session: session 120
Propose next batch: H472 (price_range_compression_regime), H473 (market_regime_duration_combo), H474 (session_timing_signal)