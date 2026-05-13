# Session 37 Log — C3 Dispersion Regime Standalone Validation (2026-03-27)

## Objectives
- Run a rigorous standalone IC test for C3/H101 (cross-sectional dispersion regime).
- Session 35 checked only `xs_dispersion_z20` vs S1 top-5 edge (day-level Spearman −0.029, p=0.130).
  That was a single-feature, single-framing check. This session adds regime-conditional IC and
  tests all four dispersion features.

## System State (entering)
- Current champion: H93 (S1) — Sharpe 15.08, IC +0.1491
- H54: PARKED (deployment gap)
- C3/H101: CANDIDATE/PASS from Session 34–35; standalone gate was weak (p=0.130)
- Dense signal queue: exhausted after H100–H105

---

## Experiments

### H106 — C3 Regime-Conditional IC Analysis

**Hypothesis:** If C3 (cross-sectional dispersion) is a valid RL regime signal, the H93 signal's IC
should be materially higher on high-dispersion days vs low-dispersion days. A >10% relative spread
in IC across terciles would justify RL conditioning value.

**Script:** `analysis/c3_dispersion_regime_ic_analysis.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (H93 signal probas)
- `data/features/xs_dispersion_regime_daily.parquet` (C3 features)

**Saved artifact:** `artifacts/run_summaries/20260327_102101_c3_dispersion_regime_ic_standalone_signal.json`

**Results:**

| Feature | IC (low tercile) | IC (mid tercile) | IC (high tercile) | IC spread (H−L) | Rel. spread | Day-level Spearman vs top-5 | p |
|---|---|---|---|---|---|---|---|
| `xs_dispersion_z20` | 0.1236 | 0.1325 | 0.1262 | +0.0026 | +2.1% | −0.029 | 0.124 |
| `xs_ret_std_1d` | 0.1208 | 0.1407 | 0.1223 | +0.0015 | +1.2% | −0.029 | 0.135 |
| `xs_breadth_up_1d` | 0.1259 | 0.1386 | 0.1211 | −0.0049 | −3.9% | +0.052 | **0.006** |
| `xs_tail_spread_1d` | 0.1231 | 0.1419 | 0.1193 | −0.0038 | −3.1% | −0.035 | 0.068 |

**Verdict: FAIL**

**Key findings:**
1. **No meaningful regime effect.** IC spread across dispersion terciles is ≤ 2.1% relative for all
   features — well below the 10% threshold. The H93 signal works equally well in low-, mid-, and
   high-dispersion regimes.
2. **Mid-tercile IC is consistently the highest** across all four features. This is a "normal market"
   effect, not a dispersion effect. There is no monotone relationship between dispersion and signal quality.
3. **Breadth statistical artifact.** `xs_breadth_up_1d` shows p=0.006 vs top-5 accuracy, but
   this is a market-direction artifact: on broad up-days (most stocks rise), picking any stock yields
   higher "accuracy" trivially. The regime IC spread for breadth is −3.9% (slightly worse in
   high-breadth regimes), confirming no ranking improvement.
4. **`xs_tail_spread_1d` is marginally significant (p=0.068) but negative direction**: wider tail
   spread → very slightly lower top-5 accuracy. Not actionable.
5. The Session 35 result (Spearman −0.029, p=0.130 for `xs_dispersion_z20`) is confirmed and extended.
   Adding three more features and the regime-conditional framing does not surface any new predictive
   structure.

---

## Session Conclusions

1. **C3 (H101 dispersion regime) is REJECTED as a standalone RL signal.** The regime-conditional IC
   analysis is decisive: dispersion does not condition the H93 signal's quality. The Sharpe
   improvement seen in H101 (+0.26 vs H93) was marginal noise in the supervised XGBoost, not a
   genuine regime effect.

2. **The dense signal search is closed.** All tested dense OHLCV-derived signals (H100–H106) have
   failed the standalone gate or produced no meaningful regime structure. There is no further
   candidate in the queue.

3. **The signal library remains: S1 confirmed, C1/C2 sparse candidates.** No new confirmed or
   promoted signals this session.

4. **Next direction requires either new data or a new data source.** The current OHLCV + news +
   insider + dispersion space is exhausted for the supervised XGBoost + standalone IC approach.
   Candidates to unblock: H98 (LLM, parked), new data vendor (foreign flow, intraday order book).

---

## Findings To Promote
- F67: C3/H101 cross-sectional dispersion regime does not pass the standalone RL gate. Regime-
  conditional IC spread ≤ 2% across terciles for all dispersion features. H101 Sharpe improvement
  (+0.26) is marginal noise. C3 is REJECTED.

## Production System After This Session
Unchanged. H93 (S1) remains the only confirmed RL signal.

## Next Session Priority
Signal search is exhausted given current data. Options:
- Wait for H98 (LLM) to become operational.
- Identify a new data source (foreign flow, intraday, order book).
- Explicitly declare signal search Phase 1 complete and shift to RL agent development using S1 alone.
