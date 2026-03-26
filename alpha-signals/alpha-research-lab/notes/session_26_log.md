# Session 26 Log - H87 Combination Test + Execution + Cost Reality + Live Validation (2026-03-19)

## Objectives
- Test whether combining the best Session 25 Sharpe improvers can push Sharpe above 10 while keeping avg_edge above 24%.
- Run the dedicated executable H78 holding-period simulation with T+1-open entry prices.
- Quantify the break-even round-trip cost for the current H54 no-VIX production system.
- Turn H87(alpha=0.7) into a first-class saved artifact and test whether it is actually a better executable alternative than H54.
- Re-run 2026 live validation on the current no-VIX H54 specification and save it as a first-class artifact.
- Turn the "H54 daily vs H87 weekly" higher-cost fallback question into an explicit saved decision rule.
- Keep the result in the permanent artifact flow: saved parquet, saved run summaries, session log, and promoted finding.

## System State (entering)
- Current champion: H54 - +25.52% avg edge, Sharpe 9.17, 11/11 positive years
- Honest benchmark: H52 - +11.64% avg edge, Sharpe 1.83
- Open issue: execution realism and transaction costs still matter more than small backtest improvements

## Experiments

### H87a - Combined Classifier (H77 dormant + H86 fundamentals)
**Hypothesis:** Combining dormant features and XS fundamentals should preserve H54-like IC while smoothing year-to-year variance enough to improve portfolio Sharpe.

**Command / code:**
- `conda run -n stocks python cross_sectional_wf.py --use-dormant-features --use-xs-fundamentals --barrier-pct 0.01 --threshold 0.05 --save-all-probas data/features/xs_barrier_h87_dormant_fundamentals_hose_full.parquet`
- `conda run -n stocks python analysis/h40_rank_portfolio.py --probas data/features/xs_barrier_h87_dormant_fundamentals_hose_full.parquet --no-vix-filter`

**Inputs:**
- 394-stock HOSE universe
- 49 features
- 1.0% barrier
- 5d horizon
- no external VIX filter at portfolio stage

**Saved artifact:**
- `data/features/xs_barrier_h87_dormant_fundamentals_hose_full.parquet`
- `artifacts/run_summaries/20260319_152614_X10_xs_barrier0.01_thr_0.05_cross_sectional.json`
- `artifacts/run_summaries/20260319_153010_h40_rank_portfolio_xs_barrier_h87_dormant_fundamentals_hose_full_portfolio.json`

| Metric | Value | Note |
|--------|-------|------|
| Avg overall acc | 55.89% | Cross-sectional WF summary |
| FPT avg edge | +1.62% | Not the decision metric for this portfolio system |
| Avg IC | +0.1502 | Slightly below H54 (+0.1515) |
| Avg Q5-Q1 spread | +21.12% | Ranking signal remains strong |
| Portfolio avg edge | +24.75% | Clears the >24% Session 26 floor |
| Portfolio Sharpe | 9.42 | Improves on H54 by +0.25 but misses >10 target |
| Positive years | 11/11 | Stable, but not a champion replacement |

**Result:** The raw H77+H86 feature combination is a mild Sharpe smoother, not a new predictive breakthrough. It preserves strong rank quality but loses too much edge to replace H54.

**Verdict: NEUTRAL**

### H87b - Regressor Blend on Top of H87a
**Hypothesis:** Adding the H82 classifier-regressor blend on top of H87a should push Sharpe above 10 while keeping edge above 24%.

**Command / code:**
- `conda run -n stocks python analysis/h82_regressor_ensemble.py --clf-probas data/features/xs_barrier_h87_dormant_fundamentals_hose_full.parquet --reg-scores data/features/xs_regressor_scores_hose_full.parquet`

**Inputs:**
- H87a classifier probas
- `data/features/xs_regressor_scores_hose_full.parquet`
- alpha sweep: 1.0, 0.7, 0.5, 0.3, 0.0

**Saved artifact:**
- `artifacts/run_summaries/20260319_153043_h82_regressor_ensemble_xs_barrier_h87_dormant_fundamentals_hose_full_regressor_blend.json`

| Metric | Value | Note |
|--------|-------|------|
| alpha=1.0 edge | +24.73% | Baseline H87a after 393-ticker merge with regressor file |
| alpha=1.0 Sharpe | 9.39 | Matches direct portfolio eval closely |
| alpha=0.7 edge | +25.03% | Best edge in the sweep |
| alpha=0.7 Sharpe | 10.25 | Clears Session 26 target |
| alpha=0.5 edge | +24.94% | Planned target alpha |
| alpha=0.5 Sharpe | 9.94 | Narrow miss: below 10 by 0.06 |
| alpha=0.3 edge | +24.52% | Higher Sharpe than raw classifier, but weaker than alpha=0.7 on edge |
| Positive years | 11/11 | All non-reg-only blends stay positive every year |

**Result:** The exact planned blend `alpha=0.5` narrowly misses the Sharpe >10 target, but a classifier-heavy `alpha=0.7` clears it while keeping edge above 25%. This gives a better edge/Sharpe tradeoff than the Session 25 H82 result if the objective is "Sharpe > 10 without dropping below 25% edge."

**Verdict: MIXED**

### H78 E=1 - Dedicated T+1-Open Holding-Period Grid
**Hypothesis:** In the executable framework, H=2 should beat H=1 because lower turnover should save more cost than the signal loses from holding stale names.

**Command / code:**
- `conda run -n stocks python analysis/h78_holding_period_grid.py --probas data/features/xs_barrier_all_probas_hose_full.parquet --entry-delay 1 --no-vix-filter`

**Inputs:**
- H54 saved probabilities
- 393-stock HOSE universe
- `TOP_N=5`
- `MIN_PROBA=0.55`
- no external VIX filter
- executable return basis: signal at T close, returns measured from T+1 open onward

**Saved artifact:**
- `artifacts/run_summaries/20260319_155704_h78_hold_grid_e1_xs_barrier_all_probas_hose_full_holding_period.json`

| Variant | Gross/day | Trades/yr | Net/yr @0.30% RT | Note |
|--------|-----------|-----------|------------------|------|
| H=1 | +0.542% | 2246 | +66.32% | Best executable variant |
| H=2 | +0.348% | 1180 | +50.98% | Lower turnover, but alpha decay still dominates |
| H=3 | +0.216% | 796 | +29.82% | Further decay |
| H=5 | +0.151% | 475 | +23.27% | Too stale |
| H=3 + K-band | +0.540% | 2246 | +66.03% | Effectively identical to H=1 |

**Result:** The dedicated executable test overturns the Session 24 inference. Once returns are measured correctly from T+1 open, H=1 still dominates H=2 on both gross/day and net/year. The signal decays fast enough that turnover reduction does not compensate for stale holdings.

**Verdict: FAIL** for the H=2 hypothesis. PASS for closing the execution-realism question.

### H63 - Cost Stress for Current H54 (No VIX Filter)
**Hypothesis:** The current H54 no-VIX production system should remain net positive at realistic HOSE round-trip costs, and the break-even point should be explicitly measurable.

**Command / code:**
- `conda run -n stocks python analysis/h63_cost_stress.py --probas data/features/xs_barrier_all_probas_hose_full.parquet --no-vix-filter`

**Inputs:**
- H54 saved probabilities
- executable E=1 open-to-open returns
- current production ranking settings
- no external VIX filter
- cost sweep: 0.00% to 2.00% RT

**Saved artifact:**
- `artifacts/run_summaries/20260319_160504_h63_cost_stress_xs_barrier_all_probas_hose_full_cost_stress.json`

| Strategy | Gross/trade | Trades/yr | Exact breakeven RT | Net annual @0.30% RT |
|--------|-------------|-----------|--------------------|----------------------|
| Daily H=1 | +0.539% | 246.8 | **0.54%** | **+59.02%** |
| Weekly H=5 | +0.643% | 50.2 | 0.64% | +17.20% |

**Additional observations:**
- Daily H=1 stays positive through 0.50% RT, but turns clearly negative by 0.70% RT.
- Weekly H=5 improves cost tolerance only modestly (+0.10% RT) while sacrificing a large amount of annual net edge.
- For the current no-VIX H54 configuration, the practical safety range is `<= 0.50%` RT. Above that, the edge becomes fragile.

**Result:** Current H54 is economically robust at realistic large-cap and many mid-cap cost levels, but not at thin-stock cost levels. The no-VIX production setup is still worth trading if real all-in RT costs stay below roughly 0.5%.

**Verdict: PASS**

### H87c - Operationalized Alpha=0.7 Blend Artifact
**Hypothesis:** If H87(alpha=0.7) is turned into a real saved signal artifact, it may outperform H54 on executable economics and deserve promotion beyond "research reference."

**Command / code:**
- `conda run -n stocks python analysis/h82_regressor_ensemble.py --clf-probas data/features/xs_barrier_h87_dormant_fundamentals_hose_full.parquet --reg-scores data/features/xs_regressor_scores_hose_full.parquet --alpha 0.7 --save-blend data/features/xs_blend_h87_alpha0.7.parquet`
- `conda run -n stocks python analysis/h40_rank_portfolio.py --probas data/features/xs_blend_h87_alpha0.7.parquet --rank-col blend_score --min-proba-col xs_proba --no-vix-filter`
- `conda run -n stocks python analysis/h63_cost_stress.py --probas data/features/xs_blend_h87_alpha0.7.parquet --rank-col blend_score --min-proba-col xs_proba --no-vix-filter`

**Saved artifact:**
- `data/features/xs_blend_h87_alpha0.7.parquet`
- `artifacts/run_summaries/20260319_161721_h82_regressor_ensemble_xs_barrier_h87_dormant_fundamentals_hose_full_regressor_blend.json`
- `artifacts/run_summaries/20260319_161925_h40_rank_portfolio_xs_blend_h87_alpha0.7_portfolio.json`
- `artifacts/run_summaries/20260319_162004_h63_cost_stress_xs_blend_h87_alpha0.7_cost_stress.json`

| Metric | H54 | H87(alpha=0.7) | Note |
|--------|-----|----------------|------|
| Backtest avg edge | +25.52% | +25.03% | H54 still higher |
| Backtest Sharpe | 9.17 | **10.25** | H87 still better on label-space Sharpe |
| E=1 gross/trade (daily H=1) | +0.539% | **+0.546%** | Tiny executable uplift |
| Exact breakeven RT | 0.54% | **0.55%** | Essentially the same |
| Annual net @0.30% RT | +59.02% | **+59.19%** | Economically almost identical |
| Weekly H=5 breakeven RT | 0.64% | **0.74%** | H87 helps more in the slower fallback mode |

**Result:** H87(alpha=0.7) is now a real saved artifact and reproduces the earlier portfolio result. But once translated into executable cost terms, it is only marginally different from H54 on the main daily H=1 strategy. It does not justify replacing H54 as the primary production system. Its most interesting advantage is as a higher-cost or slower-hold fallback, not as a decisive new champion.

**Verdict: NEUTRAL**

### H75 - 2026 Live Validation for Current H54 (No VIX Filter)
**Hypothesis:** The current H54 production configuration should still show live cross-sectional skill in 2026, and its executable E=1 portfolio should remain gross positive even if early-year costs still dominate the realized net.

**Command / code:**
- `conda run -n stocks python analysis/h75_2026_holdout.py --no-vix-filter --save-probas data/features/xs_live_validation_h54_2026.parquet`

**Inputs:**
- current H54 feature/model specification
- train years: 2012-2025
- live test slice: 2026-01-05 to 2026-03-11
- 389 tickers, 43 trading days
- current production portfolio contract: `TOP_N=5`, `MIN_PROBA=0.55`, no external VIX filter
- executable return basis: signal at T close, enter at T+1 open, exit at T+2 open

**Saved artifact:**
- `data/features/xs_live_validation_h54_2026.parquet`
- `artifacts/run_summaries/20260319_163950_h75_2026_holdout_h54_live_validation.json`

| Metric | Value | Note |
|--------|-------|------|
| 2026 IC | **+0.1323** | 43 daily cross-sections, 389 tickers |
| 2025 IC | +0.1201 | Live IC is stronger than the last full backtest year |
| Equal-weight gross/trade | **+0.155%** | 42 live trades |
| Equal-weight net/trade @0.30% RT | -0.145% | Cost still dominates early-year realized P&L |
| Square-weight gross/trade | **+0.198%** | Better than equal weight, as expected |
| Square-weight net/trade @0.30% RT | -0.102% | Still slightly negative so far |

**Result:** The live signal is clearly still present in ranking space: IC remains strong and is above 2025. Executable gross returns are positive for both equal-weight and square-weight implementations. But 2026 YTD realized net is still slightly negative at `0.30%` RT, so the honest interpretation remains "signal alive, costs first-order, sample still short." This is monitor-only evidence, not a license to tune on 2026.

**Verdict: WEAK PASS**

### H88 - Higher-Cost Fallback Rule (H54 Daily vs H87 Weekly)
**Hypothesis:** H54 daily should remain the best default strategy at normal costs, but H87(alpha=0.7) weekly should become preferable once round-trip costs rise enough.

**Command / code:**
- `conda run -n stocks python analysis/h88_fallback_compare.py`

**Inputs:**
- H54 daily cost summary from `20260319_160504_h63_cost_stress_xs_barrier_all_probas_hose_full_cost_stress.json`
- H87(alpha=0.7) weekly cost summary from `20260319_162004_h63_cost_stress_xs_blend_h87_alpha0.7_cost_stress.json`

**Saved artifact:**
- `artifacts/run_summaries/20260319_164010_h88_h54_daily_vs_h87_weekly_fallback_compare.json`

| RT cost | H54 daily ann. net | H87 weekly ann. net | Winner |
|--------|---------------------|---------------------|--------|
| 0.30% | **+59.01%** | +21.71% | H54 daily |
| 0.50% | +9.65% | **+11.80%** | H87 weekly |
| 0.70% | -39.71% | **+1.89%** | H87 weekly |

**Key threshold:** crossover at **~0.49% RT**

**Result:** The fallback question is now explicit and closed. H54 daily remains the correct default below about `0.49%` RT. Once costs are around `0.50%` RT or higher, H87(alpha=0.7) weekly becomes the better operating rule and stays positive much longer.

**Verdict: PASS**

## Session Conclusions
1. H54 remains the production edge champion.
2. H77 + H86 alone is not enough to dethrone H54; the gain is mostly variance smoothing.
3. Adding the regressor on top of the combined classifier improves the Pareto point: `alpha=0.7` reaches +25.03% edge and Sharpe 10.25.
4. H87 is a useful research result because it creates a Sharpe-optimized near-champion, even though it does not beat H54 on raw edge.
5. H78 E=1 closes the intermediate-hold question: daily rebalancing remains optimal even in executable T+1-open terms.
6. H54 no-VIX cost tolerance is now quantified: break-even is about 0.54% RT, with a practical safe zone at or below 0.50% RT.
7. H87(alpha=0.7) is now operationalized, but it does not beat H54 decisively once executable cost reality is applied.
8. The current H54 signal is still alive in 2026 live validation: IC remains strong and executable gross returns are positive, but net remains slightly negative so far at `0.30%` RT.
9. The deployment fallback rule is now explicit: use H54 daily below about `0.49%` RT, and use H87 weekly above that threshold.

## Findings To Promote
- `F47`: Combined H77+H86+H82 does not beat H54 on edge, but `alpha=0.7` creates a Sharpe-optimized near-champion (+25.03% edge, Sharpe 10.25).
- `F48`: Dedicated H78 E=1 simulation overturns the earlier inference; H=1 remains optimal in executable T+1-open terms.
- `F49`: Current H54 no-VIX cost stress shows exact break-even at ~0.54% RT; weekly H=5 only modestly improves cost tolerance and is not worth the annual net sacrifice.
- `F50`: H87(alpha=0.7) can be operationalized as a saved artifact, but executable economics are almost identical to H54 on daily H=1. Keep it as an alternate reference, not the new default.
- `F51`: Current H54 no-VIX live validation on 2026 YTD keeps strong IC (+0.1323) and positive executable gross returns, but net remains slightly negative so far at `0.30%` RT.
- `F52`: The H54 daily vs H87 weekly crossover sits near `0.49%` RT. Below that, H54 daily is better; above that, H87 weekly is the better deployment fallback.

## Production System After This Session
- H54 remains the production champion by raw edge.
- H87(alpha=0.7) is the leading Sharpe-optimized alternate and now has a saved tradable artifact.
- H54 daily rebalancing remains the correct execution reference; H=2 is not an improvement.
- H54 is economically viable if real all-in RT costs stay below roughly 0.5%.
- H87(alpha=0.7) weekly is the first explicit higher-cost fallback once costs move above roughly 0.49% RT.

## Next Session Priority
- Freeze the current 2026 live-validation artifact as monitor-only evidence. Do not tune on 2026 without explicit user approval.
- If deploying across mixed-liquidity names, map actual RT costs by name and apply the H54-daily vs H87-weekly split accordingly.
