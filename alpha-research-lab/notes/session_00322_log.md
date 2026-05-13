# Session 322 - 2026-05-08

## H440-H442 Batch Summary: Final Queue Items

The H43x-H44x hypothesis queue is now fully tested. Here's the complete summary:

### Results Summary Table

| H# | Hypothesis | Result | Key Finding |
|----|------------|--------|-------------|
| H434 | signal_strength_gating | PASSED | High strength Q5 vs Q1 = +0.0111 IC lift |
| H435a | volume_adjusted_price_momentum | PASSED | volume_z_q5 = IC 0.157, best state |
| H435b | candidate_rank_actual_gap | FAILED | Q5 gap predicts WORSE (-0.82 IC) |
| H436 | signal_ignorance_weight | FAILED | Ignoring signal HURT performance (0.053 vs 0.120) |
| H437 | replacement_quality_revival | FAILED | Entering tickers weaker than exiting |
| H438 | news_consensus_divergence | MIXED | Consensus works (0.10), divergence doesn't |
| H439 | volatility_regime_transition | MIXED | High vol is strong (0.17-0.20), transition is weak |
| H440 | news_novelty_first_repeat | PASSED | first_in_5d IC=0.123 vs repeat=0.091 (+0.032 lift) |
| H441 | cross_ticker_correlation_shock | FAILED | High vs low corr only +0.003 lift |
| H442 | ticker_rank_acceleration | FAILED | Second derivative is noise (+0.0009 lift) |

### Key Confirmed Findings

1. **H440 news novelty is real**: First-in-5d news is stronger than repeat coverage (+0.032 IC lift). Combined with strong C16 flow, first+flow achieves IC=0.161 (best state).

2. **H434 signal strength gating works**: High S1×C16 product has +0.011 IC lift. Works strongest in stress years (2020 +0.055, 2021 +0.071). Use as dynamic position sizing, not ranker replacement.

3. **H435 volume levels matter**: High volume_z (Q5) alone has IC=0.157, stronger than any volume-return combination. This is why H413 additive works (0.1×Vol + 0.9×S1 = +0.135).

4. **H436 signal ignorance FAILS**: S1/C16 are robust across all tested regime conditions. Composite degradation indicators capture nothing useful. Do not use as cash/veto signal.

5. **H441 correlation shock is weak**: Date-level cross-sectional correlation doesn't predict forward IC changes (+0.003 only).

6. **H442 rank acceleration is noise**: Second derivative of rank doesn't predict. H431 rank delta worked because it correlates with rank level, not as independent second-order signal.

### Data-Gated Items (Requires 1H data)

- M. opening_auction_leakage
- S. time_of_day_momentum_session

These require intraday 1H data from CafeF which is not currently available in the historical surface.

### Queue Status: EXHAUSTED

All testable hypotheses from the 2026-05-08 bright-mind queue have been tested. The remaining items either:
1. Require new data (1H intraday)
2. Are already confirmed signals in the library
3. Have been tested and failed

**Next action**: The queue is exhausted. Await new bright-mind ideas or data acquisition before resuming.

---

## Previous Sessions Recap

**Session 321** (H442): ticker_rank_acceleration - FAILED. Second derivative of rank is noise (+0.0009 lift). C16 rank LEVEL dominates (IC=0.158 vs acceleration=0.120).

**Session 320** (H441): cross_ticker_correlation_shock - FAILED. Primary shock signal too weak (+0.003 lift). Secondary finding: C16 flow works better in high-corr dates, first-news prefers low-corr.

**Session 319** (H440): news_novelty_first_repeat - PASSED. first_in_5d IC=0.123 vs repeat=0.091 (+0.032 lift, 8/8 pos years). first_strong_flow IC=0.161 is best state.

**Session 318** (H439): volatility_regime_transition - MIXED. High vol states strong (0.17-0.20), transition effect weak. Confirm vol level matters, not transition.

**Session 317** (H438): news_consensus_divergence - MIXED. Consensus beats divergence (-0.009 lift). Consensus states ~0.10 IC, divergence doesn't work as alpha.

**Session 316** (H437): replacement_quality_revival - FAILED. Entering tickers weaker (IC=0.066) than exiting (0.126), stable (0.079). Opposite of hypothesis.

**Session 315** (H436): signal_ignorance_weight - FAILED. Ignoring signal in degrade-state HURT (IC=0.053 vs 0.120). S1/C16 robust across all regimes.

**Session 314** (H435b): candidate_rank_actual_gap - FAILED. Q5 gap predicts WORSE (-0.82 IC vs Q1 0.64). Higher prediction error = worse returns.

**Session 313** (H435a): volume_adjusted_price_momentum - PASSED. volume_z_q5 = IC 0.157 (8/8 pos years). Volume level is the key, not return/volume ratio.

**Session 312** (H434): signal_strength_gating - PASSED. High strength Q5 vs Q1 = +0.0111 IC lift. Works strongest in stress years.

---

**Verdict**: The H43x-H44x queue is fully tested and exhausted. Document in live_state.md and update findings_compact with confirmed results.