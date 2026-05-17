# Session 369 - H575 Foreign Flow Regime as C27 Conditioner

**Date**: 2026-05-17

**Hypothesis**: C27 (blocked stocks) works differently in foreign-up vs foreign-down regimes. Foreign accumulation strengthens hidden demand, making blocked + foreign_up the strongest state.

**Command**: `python analysis/h575_foreign_flow_c27_conditioner.py`

**Saved artifact**: `artifacts/run_summaries/20260517_162326_foreign_flow_regime_c27_conditioner_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| **blocked_foreign_down** | **0.2243** | 6,551 | **6/6** |
| blocked_either (C27 raw) | 0.1477 | 15,848 | 10/10 |
| foreign_up_regime | 0.1387 | 498,660 | 11/11 |
| liquid_foreign_up | 0.1349 | 493,181 | 11/11 |
| all_rows | 0.1302 | 826,404 | 11/11 |
| liquid | 0.1266 | 817,782 | 11/11 |
| liquid_foreign_down | 0.1174 | 324,601 | 11/11 |
| blocked_foreign_up | 0.1146 | 9,297 | 8/8 |

## Key Finding: OPPOSITE - C27 is stronger in FOREIGN-DOWN, not foreign-up

- C27 × foreign-down: IC=0.2243 (+0.0977 vs baseline, +0.0766 vs raw C27)
- C27 × foreign-up: IC=0.1146 (-0.0156 vs baseline, -0.0331 vs raw C27)
- **C27 lift in foreign-down: +0.1069**, C27 lift in foreign-up: -0.0203
- **Differential: -0.1272** — hypothesis FAILED in opposite direction

**Mechanism (speculative)**: When foreign investors are SELLING (foreign-down), blocked stocks capture the void they leave — domestic demand fills the gap more strongly. When foreigners are buying, the signal is diluted by their large flows. The blocked pain signal is amplified when the market is absorbing foreign selling pressure.

**Caveat**: Only 6/6 positive years (sparse). Liquid control shows similar direction (liquid_down=0.1174 < liquid_up=0.1349), but the BLOCKED effect is much larger (+0.1069 vs +0.0175 for liquid).

## Verdict: FAILED (opposite direction) — Dead-end D074

- Hypothesis was opposite: foreign-down strengthens C27, not foreign-up
- The effect is real and large, but the mechanism contradicts the hypothesis
- Foreign-up regime actually WEAKENS C27 (blocked_foreign_up=0.1146 < liquid=0.1266)
- This is NOT a new signal to export — it's a regime caveat on C27

**Next**: #80 C27 × Capacity Amplifier (blocked + tight_capacity)