# Phase 4B preregistered protocol

**Experiment ID:** `rl-trade-episode-phase4b-20261025`

**Protocol basis commit:** `a6d0ca89` (Phase 4A implementation baseline)
**Run-code commit:** to be recorded from `HEAD` immediately before execution.

## Questions and frozen hypotheses

- **H1, exposure shortcut:** Phase 4A PPO performance is explained by its exposure and holding behavior rather than predictive timing.
- **H5, bull-market dependence:** Phase 4A PPO's apparent success depends on bullish drift and fails in unfavorable regimes.

No policy, reward, execution, match threshold, regime boundary, or classification rule will be changed after Phase 4B results are inspected. Phase 4A policies remain frozen; no PPO training is permitted.

## Policies and randomized controls

Load the six Phase 4A MaskablePPO checkpoints by their recorded SHA-256 hashes: market-only and market-plus-S1/C16, each with seeds 1208, 1209, and 1210. The Phase 4A run predates a committed source snapshot, so its generating Git SHA is unknown; the later baseline commit must not be represented as the checkpoint-training SHA.

For each ticker and feature variant, collect paired `(waiting_duration, holding_duration)` values from the three frozen policies' completed **2020–2022 validation** trades. A feature-blind control samples one pair with replacement at each episode start using its own deterministic RNG stream. It waits the sampled number of OUT decisions, enters on the first legal next-open fill, and exits at the sampled holding interval or first later legal next-open fill. It uses only position, elapsed duration, and action masks; it never reads market or Alpha observations. Validation-derived pairs are a behavioral calibration, not a clean independent test.

Run 50 randomized paths for each ticker × feature variant × chronological split, with seeds 42000–42049. Share seed numbers across variants for pairing; use ticker/variant/split offsets in the RNG key. Initial capital is 1 per stock path. Preserve next-day-open fills, the three-interval minimum, zero fees/slippage, dividend-adjusted-price assumption, and the Phase 4A terminal reward for PPO. Random controls receive no predictive reward or features.

Report test matching against the mean of the three PPO seeds. A group is considered adequately matched only if mean absolute exposure error is at most 5 percentage points, relative mean holding-duration error at most 20%, and mean waiting-duration error at most 2 trading days. Otherwise, matched-control inference is inconclusive. Report empirical duration distributions and ticker-level gaps as well as group means.

## Market regimes and chronology

Use VNINDEX close data only to label evaluation intervals; it is never added to policy observations. At decision close `t`, calculate the simple return from the index close 126 trading sessions earlier through close `t`. Labels are fixed: **rising** at `>= +10%`, **falling** at `<= -10%`, and **sideways** otherwise. The label uses only information available at decision time `t`; attribute the next transition's return to that label. No CAGR is reported for the non-contiguous regime subsets.

Keep 2015–2019 (training, in-sample), 2020–2022 (validation, previously examined), and 2023–2025 (exploratory, Alpha-selection-contaminated) distinct. Include 2020 and 2022 separately. Use no rows dated after 2025-12-31. The fixed regime rule yields rising, falling, and sideways intervals in each partition; minimum coverage is reported before interpreting any category.

All policies use identical stock/date coverage, execution conventions, price paths, initial capital, and compounding. Compare against the randomized controls, immediate-entry three-day mechanical trading, and buy-and-hold. Report independent per-stock paths; do not call their average a realizable portfolio.

## Inference and decision rules

Primary H1 comparison is 2023–2025 PPO versus behavior-matched randomized controls. Report full-period returns, control percentiles, and paired stock-year return differences. Use 5,000 hierarchical bootstrap replicates: resample tickers as clusters, then calendar-year blocks within each ticker; never resample trades as independent observations.

- **H1 contradicted:** matching is adequate in both ticker groups, the 95% clustered interval for PPO-minus-control annual block return is above zero in both groups, and at least two-thirds of tickers in each group beat their control median.
- **H1 consistent with evidence:** matching is adequate and both groups' median PPO percentile is at or below 50, or both groups' 95% interval upper bounds are at or below zero.
- **H1 inconclusive:** all other cases, including failed matching or broad uncertainty.

For H5, compare falling and sideways daily attribution separately against randomized controls, mechanical trading, and buy-and-hold. Use the same ticker-clustered bootstrap over year/regime blocks. **H5 is contradicted** only if PPO's excess over randomized controls has a positive 95% interval in both regimes and both ticker groups, with positive point estimates against both mechanical trading and buy-and-hold in each regime. **H5 is consistent with evidence** if there is adequate regime coverage but PPO has no positive interval in at least one unfavorable regime and does not exceed both market references there. Otherwise classify it as inconclusive.

Apply H1 and H5 criteria separately to market-only and market-plus-Alpha. Report the combined hypothesis as contradicted/consistent only if both variants receive that classification; otherwise the combined result is inconclusive. For regime bootstraps, use only stock-year-regime blocks with at least 30 classified intervals and report how many blocks remain.

## Provenance and outputs

Record the run-code commit SHA before loading the frozen checkpoints, Python/dependency versions, input file metadata, per-ticker prepared-input SHA-256 fingerprints, checkpoint paths/hashes, date cutoff, RNG seeds, and execution date. Re-hash checkpoints and record shared-input metadata after evaluation; abort if either changes unexpectedly. Version the protocol/config, focused tests, compact JSON/CSV metrics, trade records, final report, and checkpoint manifest; never commit checkpoints or datasets.
