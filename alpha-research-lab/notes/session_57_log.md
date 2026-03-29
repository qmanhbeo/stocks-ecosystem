# Session 57 Log

## Objective
Formalize the split between:
- selection alpha = choose the right names
- activation alpha = decide when the selector should be on or off

Then implement and run the deterministic activation-alpha wave on top of the frozen long-only selectors.

Hard rules remained unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch, not solved

## Build step

Built the canonical date-level activation artifact:
- `data/features/activation_state_daily.parquet`

Builder:
- `data_tools/build_activation_state_features.py`

Coverage:
- `2015-01-05` to `2025-12-31`
- `2,748` rows

The artifact includes:
- selector confidence / opportunity density features
- tradability / liquidity-opening breadth features
- breadth / dispersion regime features
- benchmark / macro regime features

## Frozen selectors

Primary selector:
- `full_library + k5_r5_eq`

Secondary contrast selector:
- `S1`-only `k5_r5_eq`

Reference always-on champion:
- `full_library + k5_r5_eq`
- `+769.71%` total
- `+346.40%` relative vs VNINDEX
- information ratio `0.81`
- max DD `-34.04%`

## H157 — Opportunity density gate

Best non-baseline full-library gate:
- `opp__spread_q70`
- `+652.12%` total
- `+286.05%` relative
- information ratio `0.71`
- max DD `-26.51%`

Reading:
- confidence-style gating can reduce drawdown somewhat
- but it gives up too much return and does not beat the always-on selector

## H158 — Tradability breadth gate

Best non-trivial reading:
- `trad__top10_buyable_ge5` matched always-on exactly, which means it was effectively always true
- strongest actual uplift appeared on the weaker `S1` selector, not on the champion

Notable `S1` result:
- `trad__liq_breadth_all_ge10`
- `+688.19%` total
- `+304.56%` relative
- information ratio `0.71`

Reading:
- tradability breadth matters for weak selectors
- but it does not improve the champion selector enough to matter branch-wise

## H159 — Market regime gate

Best full-library gate:
- `mkt__credit_risk_on_ge2`
- `+614.63%` total
- `+266.81%` relative
- information ratio `0.68`
- max DD `-28.32%`

Reading:
- market regime clearly affects the selector
- but the broad risk-on gate still underperforms always-on `full_library`

## H160 — Breadth / dispersion gate

Best full-library gate:
- `bd__disp_q60`
- `+378.70%` total
- `+145.71%` relative
- information ratio `0.53`
- max DD `-32.01%`

Reading:
- cross-sectional structure matters some
- but not nearly enough to justify turning the selector off most of the time

## H161 — Recent efficacy / cooldown gate

Nearest full-library miss of the whole wave:
- `recent__prev_cycle_gt_m02`
- `+706.77%` total
- `+314.10%` relative
- information ratio `0.76`
- max DD `-38.96%`

Reading:
- recent selector efficacy is the strongest activation family so far
- but it still does not beat always-on `full_library`
- worse, it actually increases drawdown versus always-on

## H162 — Composite activation score

Best result was on the weaker `S1` selector:
- `comp__score_q70`
- `+209.28%` total
- `+58.75%` relative
- information ratio `0.24`
- max DD `-16.68%`

Reading:
- the composite helps `S1`
- it still does not challenge always-on `full_library`

## Verdict

The repo is stronger at **selection alpha** than **activation alpha**.

What is now known:
- the always-on `full_library + k5_r5_eq` selector remains the long-only champion
- deterministic binary on/off activation does not improve it
- activation gates can help weaker selectors, especially `S1`, but not enough to dethrone the champion

So the architectural conclusion is:
- selection alpha is real
- activation alpha is not solved
- binary deterministic gating is now a tested branch, not an open assumption

## Branch decision

Return the active branch to selection-side work:
1. `H151`: narrow tradability-conditioned composite
2. `H152`: tradability-conditioned alpha search

Park activation alpha for now.
If it is revisited later, do not start with another binary gate sweep.
Require a material design change first, such as:
- partial exposure sizing
- a more structural timing model
- selector-specific activation that is not just on/off thresholding

## Artifacts

Activation summaries:
- `artifacts/run_summaries/latest_portfolio_activation_opportunity_density.json`
- `artifacts/run_summaries/latest_portfolio_activation_tradability_breadth.json`
- `artifacts/run_summaries/latest_portfolio_activation_market_regime.json`
- `artifacts/run_summaries/latest_portfolio_activation_breadth_dispersion.json`
- `artifacts/run_summaries/latest_portfolio_activation_recent_efficacy.json`
- `artifacts/run_summaries/latest_portfolio_activation_composite.json`

Detailed outputs:
- `artifacts/portfolio_baselines/20260329_131205_h157_opportunity_density_gate_results.parquet`
- `artifacts/portfolio_baselines/20260329_131237_h158_tradability_breadth_gate_results.parquet`
- `artifacts/portfolio_baselines/20260329_131237_h159_market_regime_gate_results.parquet`
- `artifacts/portfolio_baselines/20260329_131237_h160_breadth_dispersion_gate_results.parquet`
- `artifacts/portfolio_baselines/20260329_131330_h161_recent_efficacy_cooldown_gate_results.parquet`
- `artifacts/portfolio_baselines/20260329_131329_h162_composite_activation_score_results.parquet`
