# Session 118 Log — 2026-05-08

## H466: crowd_exhaustion_reversal

**Decision: PASSED**

### Hypothesis
H445 showed exhaustion (high repeat + high attention) is WORST (-0.0474 IC). After exhaustion, mean-reversion might kick in.

### Results
- two_days_exhaustion: IC=0.2013 (+0.0711 lift, 3/3 positive years with 2026 confirmation NaN) — **STRONG**
- exhaustion_today: IC=0.1104 (confirms H445 worst state)
- was_top20_not_today: IC=0.0882 (-0.0420 lift) — dropped C16 stocks are WORSE than baseline
- post_exhaustion_non_top: IC=0.0857 (-0.0445 lift) — exhaustion recovery doesn't work as next-day buy

### Key insight
**Two consecutive days of top-C16 + high-return is the strongest continuation signal (+0.0711)**, NOT a reversal. The "exhaustion" hypothesis (mean-reversion after crowd peak) is WRONG. The correct mechanism: momentum AMPLIFIES after sustained crowd conviction. Two consecutive days of C16 crowding = sustained demand pressure = strong next-day continuation.

### H467: price_limit_ceiling_count_regime

**Decision: PASSED**

### Results
- limit_2_of_3: IC=0.2353 (+0.1052 lift, 8/8 positive years) — **NEW SIGNAL C24: multi_day_ceiling_pressure**
- near_limit_expansion: IC=0.2163 (+0.0862)
- near_limit (C22): IC=0.2162
- ceiling_exhaustion: IC=0.2119 (+0.0818)
- limit_1_of_3: IC=0.2117 (+0.0816)
- at_limit (+6.5%+): IC=0.1605 (+0.0304)

### Key insight
**Hitting the +7% limit 2+ times in last 3 days is a very strong signal** — IC=0.2353, even stronger than single-day near-limit (C22: 0.2162). This is a "buildup" signal: sustained limit-hitting creates queue pressure that releases upward.

### H468: market_breadth_regime_signal

**Decision: MIXED**

### Results
- vol_expansion_in_breadth_bottom20: IC=0.1936 (+0.0635) — vol_expansion works best in NARROW markets
- vol_expansion_in_breadth_top20: IC=0.1588 (+0.0287) — vol_expansion weaker in broad markets
- breadth_bottom20: IC=0.1441 (+0.0140) — narrow market itself is positive
- breadth_top20: IC=0.1101 (-0.0199) — broad market is NEGATIVE
- c16_top20_in_breadth_top20: IC=0.0607 (very weak)
- c16_top20_in_breadth_bottom20: IC=0.1100

### Key insight
**Narrow market (breadth bottom 20%) is a regime amplifier.** vol_expansion works better in narrow markets (0.1936) than in broad markets (0.1588). But the effect is not strong enough for standalone promotion — it's a soft regime filter, not a hard gate.

### Session 118 summary
- H466 PASSED (with inversion): two_days_exhaustion IC=0.2013 — but mechanism is CONTINUATION not reversal
- H467 PASSED: limit_2_of_3 = multi-day ceiling pressure, NEW SIGNAL C24
- H468 MIXED: narrow market amplifies vol_expansion, broad market weakens it

### Key findings for findings.md
- C24: multi_day_ceiling_pressure (hit limit 2+ times in last 3d, IC=0.2353, +0.1052 lift)
- two_days_exhaustion (IC=0.2013) is CONTINUATION, not reversal — inversion of H445 exhaustion hypothesis
- narrow market is a soft regime amplifier for vol_expansion signals
- breadth_top20 (broad market) is NEGATIVE for S1 signal quality (-0.0199)