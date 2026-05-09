# Session 131: H482 sentiment_scope_filter

**Date:** 2026-05-09
**Hypothesis:** Ultra_negative (bottom 5% prob_neg from H480) identifies noise states where S1 quality fails. Test S1 IC WITH ultra_negative vs WITHOUT.

**Command:**
```bash
python analysis/h482_sentiment_scope_filter.py
```

**Inputs:**
- S1 from xs_barrier_vol_1d_hose_full.parquet (default)
- PhoBERT sentiment from phobert_ticker_day_sentiment.parquet
- Test years: 2015-2025

**Saved artifact:** artifacts/run_summaries/h482_sentiment_scope_filter_summary.json

**Results:**
| State | IC | Lift vs Baseline | Rows |
|-------|-----|------------------|------|
| S1 WITH ultra_negative | 0.1006 | -0.0032 | 6,737 |
| S1 WITHOUT ultra_negative | 0.1040 | +0.0001 | 167,421 |
| Positive sentiment (top 30%) | 0.1058 | +0.0019 | 53,119 |
| Baseline (all with news) | 0.1038 | - | 174,158 |

**Filter effect:** +0.0034 (S1 WITHOUT ultra_negative slightly better than WITH)
- ultra_negative (bottom 5%) filter: +0.0034
- extreme_negative (bottom 10%) filter: -0.0027
- moderate_negative (10-30%) filter: -0.0089

**Verdict: FAIL** — No significant filter benefit. The filter effect (+0.0034) is below the +0.01 threshold. Ultra_negative does NOT identify noise states where S1 quality fails.

**Finding:** F409 - Sentiment extremes (ultra_negative) do NOT filter S1 quality. S1 is robust across sentiment regimes. The original hypothesis that "sentiment extremes identify noise states" is NOT supported. S1 quality is similar whether the ticker has ultra-negative news or not.

**Source anchor:** F409

---

## H485: floor_pressure_symmetry (BG queue)

**Date:** 2026-05-09
**Hypothesis:** C24 tests CEILING (+7%), never tested FLOOR (-7%). Multi-day floor pressure = forced sell capitulation = reversal? Test floor_count >= 2 × vol_expansion vs C24 ceiling analog.

**Command:**
```bash
python analysis/h485_floor_pressure_symmetry.py
```

**Inputs:**
- S1 from xs_barrier_vol_1d_hose_full.parquet (default)
- Order stats with price_change_raw for floor/ceiling detection
- Test years: 2015-2025

**Saved artifact:** artifacts/run_summaries/20260509_232014_floor_pressure_symmetry_research_branch.json

**Results:**

| State | IC | Lift vs Baseline | Rows | Years+ |
|-------|-----|------------------|------|--------|
| ceiling_2_expansion | 0.2442 | +0.1141 | 3,516 | 2/2 |
| ceiling_2_of_3 (C24) | 0.2353 | +0.1052 | 8,933 | 8/8 |
| near_floor_expansion | 0.1610 | +0.0309 | 17,276 | 11/11 |
| near_floor | 0.1550 | +0.0249 | 29,128 | 11/11 |
| at_ceiling | 0.1605 | +0.0304 | 23,159 | 11/11 |
| at_floor | 0.1428 | +0.0127 | 18,934 | 11/11 |
| floor_1_of_3 | 0.1550 | +0.0249 | 40,685 | 11/11 |
| **floor_2_of_3** | 0.0818 | **-0.0483** | 7,553 | 5/5 |
| **floor_2_expansion** | 0.0575 | **-0.0726** | 2,325 | 1/1 |
| baseline (all rows) | 0.1301 | - | 824,801 | 11/11 |

**Verdict: FAIL** — Floor pressure is NOT symmetric to ceiling pressure.

- `floor_2_of_3`: IC=0.0818 (BELOW baseline 0.1301 by -0.0483)
- `floor_2_expansion`: IC=0.0575 (BELOW baseline by -0.0726)
- `ceiling_2_of_3` (C24): IC=0.2353 (+0.1052 lift) — confirmed

**Finding:** Floor pressure does NOT produce reversal. Multi-day floor pressure (hitting -7% limit 2+ times) is anti-predictive — stocks that hit the floor repeatedly tend to continue underperforming. The mechanism "capitulation at daily floor = reversal" is NOT supported. Floor is fundamentally different from ceiling: ceiling pressure = queue buildup → release (works), floor pressure = continued weakness (does NOT work).

**Dead-end:** D045 — floor_pressure_symmetry fails. Do NOT test floor pressure as reversal signal.

**Source anchor:** F410

**Next action:** Queue BG complete, move to BJ (lagged_signal_decay) next.

---

## H486: lagged_signal_decay (BJ queue)

**Date:** 2026-05-09
**Hypothesis:** C23 works at 1d (IC 0.26), C24 multi-day works. Test if signal effectiveness DECAYS or IMPROVES at longer horizons. C24 multi-day showed temporal structure works. Mechanism: signals have natural holding periods.

**Command:**
```bash
python analysis/h486_lagged_signal_decay.py
```

**Inputs:**
- S1 from xs_barrier_vol_1d_hose_full.parquet
- C23 (high_illiq × vol_expansion), C24 (ceiling_2 × vol_expansion)
- 1d, 2d, 3d barrier labels computed via shift

**Saved artifact:** artifacts/run_summaries/20260509_232208_lagged_signal_decay_research_branch.json

**Results:**

| Signal | 1d IC | 2d IC (lift) | 3d IC (lift) |
|--------|-------|--------------|--------------|
| baseline (all) | 0.1334 | 0.0289 (-0.1045) | 0.0032 (-0.1302) |
| C23 (illiq×exp) | 0.0844 | 0.0323 (-0.0520) | 0.0044 (-0.0800) |
| C24 (ceiling×exp) | 0.2291 | -0.0302 (-0.2593) | -0.0338 (-0.2629) |

**Verdict: FAIL** — Both C23 and C24 DECAY massively at longer horizons.

- C24: 1d IC=0.2291 → 2d IC=-0.0302 (MASSIVE decay: -0.2593!)
- C23: 1d IC=0.0844 → 2d IC=0.0323 (-0.0520)
- Best horizon for both: 1d

**Finding:** Signals do NOT improve at longer horizons. The hypothesis that "signals have natural holding periods" is NOT supported. C24 multi-day (C24 is already multi-day in its definition) works because it captures multi-day BUILDUP, but the payoff is still at 1d. The signal decays rapidly after T+1.

**Dead-end:** D046 — lagged_signal_decay fails. Do NOT test C23/C24 at 2d/3d horizons.

**Source anchor:** F411

**Next action:** BJ complete, BK (floor_pressure_contrarian) was already killed by BG result, move to next eureka items.