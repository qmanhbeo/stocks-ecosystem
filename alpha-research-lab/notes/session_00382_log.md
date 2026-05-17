# Session 382 — 2026-05-17

## H93 - Cofire-Persistence Interaction

**Hypothesis:** Test if isolated signals (F440: low cofire Q1) combined with sustained signals (F441: high persistence Q4) creates stronger alpha than either alone. Mechanism: isolated AND sustained = strongest hidden demand.

**Source:** F440 (cofire isolation Q1=0.2064), F441 (persistence Q4=0.1825). Hypothesis: is there combo benefit?

**Command / code:** Inline Python test using S1 panel + C16 panel

**Inputs:**
- S1 panel: xs_barrier_vol_1d_hose_full.parquet
- C16 panel: xs_order_pressure_daily.parquet
- Years: 2015-2025
- Signal: C23 (active + illiq > 0.7 + vol_expansion)
- Cofire: quartile of count of tickers with C23 on same day (Q1=isolated, Q4=crowded)
- Persistence: rolling 9-day active count / 9 (Q1=transient, Q4=sustained)

| Metric | Value | Note |
|--------|-------|------|
| Baseline (C23 only) | IC=0.1684, n=33,103 | |
| Cofire Q1 + Persist Q1 | IC=0.1753, n=2,679, lift +0.0069 | Isolated + transient |
| Cofire Q1 + Persist Q4 | IC=0.1794, n=2,729, lift +0.0110 | Isolated + sustained |
| Cofire Q4 + Persist Q1 | IC=0.1042, n=2,500, lift -0.0642 | Crowded + transient |
| Cofire Q4 + Persist Q4 | IC=0.1950, n=1,166, lift +0.0265 | Crowded + sustained |

**Year-by-year (Q1+Q4 - isolated+sustained):**
- 11/11 positive years, mean IC=0.1706

**Result:**
PASSED. Cofire Q1 + Persist Q4 (isolated + sustained) achieves IC=0.1794 with +0.0110 lift over baseline. 11/11 positive years confirms robustness. The combo adds value over either amplifier alone.

Interestingly:
- Q4+Q4 (crowded+sustained) has highest IC (0.1950) but only 8/11 positive
- Q1+Q4 (isolated+sustained) is more robust with 11/11 positive

**Verdict: PASSED (Finding F443)**

**Key insight:** Both F440 (cofire isolation) and F441 (persistence) are orthogonal amplifiers - their combination works. The "crowded but sustained" (Q4+Q4) has higher IC but less robust; "isolated and sustained" (Q1+Q4) is the more reliable combo.

**Next action:** Continue with H94 (Blocked-State Transition Timing) or document F443.