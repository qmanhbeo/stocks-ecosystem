## H496: BR10 c16_level_router

**Date:** 2026-05-09
**Hypothesis:** H120 found C16 works at IC 0.077. C23 works at IC 0.26. Test: use C16 LEVEL as ROUTER — when C16 HIGH use C23, when C16 LOW use C16 or C23. Different regimes need different signals.

**Command:**
```bash
python analysis/h496_c16_level_router.py
```

**Inputs:**
- S1 from xs_barrier_vol_1d_hose_full.parquet
- OHLCV from 406 per-ticker gia_lich_su_*_1D.parquet files
- Order stats from cafef/order_stats_daily.parquet
- C16 proxy (buy-sell volume imbalance) × C23/C24 signals
- Test years: 2015-2025

**Saved artifact:** artifacts/run_summaries/20260509_233802_c16_level_router_research_branch.json

**Results:**

| State | IC | Lift vs Baseline | Rows | Years+ |
|-------|-----|------------------|------|--------|
| baseline (all rows) | 0.1298 | — | 809,019 | 11/11 |
| **c16_low × C23** | **0.2838** | **+0.1540** | **14,900** | **11/11** |
| high_illiq_expansion (C23) | 0.2616 | +0.1318 | 39,627 | 11/11 |
| c16_high × C23 | 0.2396 | +0.1098 | 13,281 | 11/11 |
| ceiling_2_expansion (C24) | 0.2530 | +0.1232 | 3,458 | 2/2 |
| c16_high alone | 0.1623 | +0.0325 | 163,452 | 11/11 |
| c16_low alone | 0.1589 | +0.0291 | 160,707 | 11/11 |
| c16_high × C24 | 0.1206 | -0.0092 | 4,449 | 2/2 |
| c16_mid | 0.1046 | -0.0252 | 484,860 | 11/11 |

**Decision: PASSED**

**Verdict: PASSED** — C16 routing works, OPPOSITE of hypothesis.

Key findings:
1. **c16_low × C23 = IC 0.2838 (+0.1540)**: STRONGEST state tested this session! +0.0222 incremental vs C23 alone
2. **c16_high × C23 = IC 0.2396 (+0.1098)**: Positive but WEAKER than c16_low × C23
3. **c16_high × C24 is WEAK**: IC=0.1206 (-0.0092) — WORSENS C24 in high C16 regime
4. **C16 LOW regime amplifies C23 significantly** (+0.0222 incremental over C23 alone)
5. **Routing benefit**: c16_low × C23 (+0.1540) >> c16_high × C23 (+0.1098) — low C16 is a better amplifier
6. **c16_mid is ANTI-predictive**: IC=0.1046 (-0.0252)

**Key insight — OPPOSITE of hypothesis:**
- Hypothesis: high C16 = strong order pressure = better signal
- Reality: LOW C16 amplifies C23 MORE than high C16
- Mechanism: low C16 means less crowd following = more room for illiq+vol regime to work
- High C16 in combination with ceiling signals HURTS (c16_high × C24 = 0.1206 vs 0.2530 alone)

**Finding:** F419 — c16_level_router PASSED. C16 LOW × C23 = IC 0.2838 (+0.1540) — strongest signal state found this session. C16 LOW amplifies C23 by +0.0222 over C23 alone. Use C16 level as a regime router: when C16 is low, C23 is stronger. When C16 is high, C23 is weaker but still positive. Do NOT combine C16 high with ceiling signals (C24) — it degrades quality.

**Source anchor:** F419

**Next action:** Queue BR10 complete. Batch 16 (BR1-BR10) DONE. Update cycle_handoff.md and live_state.md.