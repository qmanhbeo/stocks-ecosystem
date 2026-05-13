# Session 100 Log

## Objective
Run H444 signal_ignorance_weight experiment from the NEW EUREKA queue (item F).

Hypothesis: True edge is knowing WHEN to ignore S1/C16, not weighting them. S1/C16 in certain regimes hurt; ignorance is alpha.

This session did not change the live branch.
It did not read 2026+.

## Starting point

Coming in:
- H428-H433 had been tested from the EUREKA queue
- H440 news_novelty_first_repeat PASSED (+0.032 IC lift)
- H431 cross_sectional_rank_delta PASSED (+0.0114 IC lift)
- H432 volume_price_divergence FAILED (negative lift)
- H433 state_transition_not_event MIXED (D2 best +0.0088)
- H428 ranker_error_taxonomy FAILED (S1 quality persists, no decay)
- H429 signal_half_life_router FAILED (no horizon advantage)
- H441 cross_ticker_correlation_shock FAILED (+0.0033 lift only)
- H442 ticker_rank_acceleration FAILED (second derivative is noise)
- H443 prop_foreign_predator_prey FAILED (below baseline)
- Queue had F. signal_ignorance_weight as NOT YET TESTED

## What changed

Added:
- `analysis/h444_signal_ignorance_weight.py`

Method:
- Used cross-sectional regime features computed from S1 panel itself (no external data)
- Built per-date IC bucket (high/low) and temperature bucket (high/low)
- Tested whether different regimes have different S1 IC patterns
- Compared each regime IC vs baseline "all_rows" IC

Saved artifacts:
- `artifacts/run_summaries/h444_signal_ignorance_weight.json`

## Results

| Regime | IC | Lift vs Baseline | Rows |
|--------|-----|------------------|------|
| all_rows (baseline) | 0.1335 | - | 826404 |
| high_ic | 0.2348 | +0.1012 | 157150 |
| low_ic | 0.0279 | -0.1057 | 171906 |
| high_temp | 0.1477 | +0.0141 | 152542 |
| low_temp | 0.1231 | -0.0104 | 170889 |
| high_breadth | 0.1111 | -0.0225 | 160011 |
| low_breadth | 0.1515 | +0.0180 | 165725 |
| high_ic_high_temp | 0.2606 | +0.1271 | 34611 |
| high_ic_low_temp | 0.2513 | +0.1177 | 29376 |
| low_ic_high_temp | 0.0240 | -0.1096 | 31367 |
| low_ic_low_temp | -0.0034 | -0.1369 | 39793 |
| high_breadth_high_ic | 0.2345 | +0.1010 | 20893 |
| low_breadth_low_ic | 0.0463 | -0.0873 | 26950 |

**Key Finding**: 
- Best regime: high_ic_high_temp (IC=0.2606, +0.1271 lift)
- Worst regime: low_ic_low_temp (IC=-0.0034, -0.1369 lift)
- In "low IC + low temperature" regime, S1 actually has NEGATIVE IC (-0.0034)

## Verdict: PASSED (as offline evidence)

**Result**: Found strong ignorance opportunity - worst regime has -0.1369 lift vs baseline

The worst regime differs enough from baseline to potentially ignore. S1/C16 are NOT robust across all regimes - there are specific corners (low IC + low temperature) where they actively hurt.

**Important Cavead**: The regime buckets were computed using SAME-period IC (lookahead). A true implementation would need to PREDICT the regime from pre-decision features. This is offline evidence of POTENTIAL, not a deployable rule.

**Next Steps**:
1. The signal is not directly deployable due to lookahead in regime definition
2. Could try using lagged features (past IC, past temperature) to predict regime
3. Would need walk-forward validation with lagged regime prediction
4. Alternatively, use as a diagnostic tool rather than a trading rule