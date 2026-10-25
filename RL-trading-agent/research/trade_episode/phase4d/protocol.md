# Phase 4D — Supervised Fixed-Continuation Exit Test

**Experiment ID:** `rl-trade-episode-phase4d-supervised-exit-20261025`
**Protocol base:** Phase 4C report commit `c548ed53`.

## Hypotheses and scope

- **H6:** A supervised SELL-versus-HOLD model can turn the Phase 4A observation into a useful executable exit policy.
- If it beats fixed-entry mechanical and randomized controls while frozen PPO does not, that is evidence consistent with a PPO learning/credit-assignment limitation. It is not implied by beating PPO alone.
- No PPO is retrained. Full-policy PPO numbers are reused from the saved Phase 4B evaluation, whose manifest records the six Phase 4A checkpoint hashes. This comparison has different entries and is descriptive only.
- Also run an isolated entry-conditioned diagnostic on the frozen Phase 4A seed-1208 PPO entry dates from the saved trade log. Compare supervised and mechanical exits from each same entry, only when the 40-interval window fits in the split. Report per-trade results only; overlapping counterfactuals are not a chronological portfolio.
- The diagnostic uses the historical Phase 4A trade log at `/tmp/stock-rl-trade-episode-phase4a-20261025/phase4a_trades.csv`, policies `market_only` and `market_plus_s1_c16`, seed `1208`, and exploratory dates only. It is secondary and does not alter the primary fixed-entry result or H6 rule.

## Data and chronology

- Read shared data from `STOCKS_DATA_ROOT`; keep it read-only. Prepare only rows through **2025-12-31** using the existing Phase 4A causal loader.
- Train on ACB, BCG, FPT, GAS, HPG, MWG, PVD, REE, SSI, VCB, VIC, VNM, 2015–2019 only. DGC, MBB, VHC are never fit or threshold-selection data.
- Validation: 2020–2022, training tickers only for threshold selection. Exploratory: 2023–2025, all 15 stocks; this period is Alpha-selection-contaminated, not pristine. Validation results are also previously examined.
- Label inputs, feature inputs, all fills, and labels must remain within the same partition. Causal historical lookback is allowed; no 2026 observations/statistics enter preparation.

## Label, timing, and features

At decision close `t`, let entry fill be `open[t-a]`, where `a=t-entry_fill_index` is current holding age in trading-row intervals. Phase 4A's next-open action mask allows the earliest SELL when `a=2`, since the next fill is at least three fill-to-fill intervals after entry.

- SELL now fills at `open[t+1]`, with duration `a+1`.
- HOLD for three additional trading intervals, then SELL at `open[t+4]`, with duration `a+4`.
- Target: `delta_reward = R_hold - R_sell`, where `R(T)=(252/T)*ln(P_sell/P_entry)-ln(1.07)`. Positive favors HOLD; negative favors SELL. This is a fixed-three-interval continuation label, not an unrestricted Q-value.
- Use current 9 normalized market features, optional four Phase 4A S1/C16 value/availability features, all five Phase 4A agent-state fields, and log entry-time volatility. No ticker identity or future outcome enters model inputs. Missing alpha uses Phase 4A's 0.5 sentinel plus availability bit.
- Training/diagnostic states use current ages `[2,3,5,10,20,30,36]`, zero waiting, and immediate-entry episode age. Sample every 5 trading rows per ticker/age; future label windows are 4 intervals, so same-age labels do not overlap. Fit feature scaling on training rows only and weight ticker-year-age strata equally.

## Models and policy

- Constant training-mean and age-only Ridge baselines.
- Ridge (`alpha=25`, `StandardScaler` fit on train) and ExtraTrees (`64` trees, depth `5`, leaf minimum `50`, `max_features=0.8`, one worker, seed `6404`), each for market-only and market+S1/C16 inputs.
- Fixed-entry schedule: first in-split decision row, then every 42 trading rows; buy at next open only when legal. If a scheduled entry is unbuyable, skip it without shifting the schedule. Exit strategies share entry dates; report common-entry coverage and treat <90% shared coverage as inconclusive.
- Exit controller reevaluates daily after the next-open mask permits the minimum hold. SELL when predicted delta is below one threshold from `[-0.10,-0.05,0.00]`; choose threshold on validation training tickers by equal-ticker mean chronological CAGR, ties by fewer trades. Max holding cap is 40 fill-to-fill intervals; when the sell is untradable, keep it pending until the first legal open and disclose delay. Exit decisions use a 3-day fixed-continuation forecast but reevaluate daily; this approximation is intentional.
- Compare fixed 3/10/20-interval exits and 100 feature-blind randomized exits per model, drawing holding durations from that policy's validation training-ticker distribution (seed range 54000–54099). Random controls do not read observations.

## Evaluation and decision rule

Report predictive Spearman, MAE versus constant/age baselines, sign accuracy, and positive-label prevalence. Report chronological per-stock compounded return, CAGR, max drawdown, exposure, trades, waits, holds, and unfinished end positions; mark open positions to market, never fabricate SELL. Summarize by ticker, year, regime (causal VNINDEX trailing 126-session return: rising ≥10%, falling ≤−10%, otherwise sideways), and training/unseen group. Do not call the mean of stock paths a realizable portfolio.

Use 2,000 paired hierarchical bootstrap replicates (ticker clusters, then ticker-year blocks; seed `64045`) for strategy-minus-control annualized log-wealth differences. Randomized-control percentiles are reported separately. A duration match is adequate only when mean holding differs by ≤2 sessions and exposure by ≤5 percentage points from its supervised policy in both stock groups.

- **H6 supported:** at least one preregistered supervised policy beats each fixed mechanical and matched-random control by ≥2 percentage points annualized CAGR, with positive paired 95% intervals, in both training and unseen groups on exploratory dates, with adequate coverage/matching.
- **H6 contradicted under this protocol:** coverage, entry overlap, and duration/exposure matching are adequate, and for every supervised model the upper 95% interval excludes a 2 percentage-point annualized advantage over at least one required control in both training-universe and unseen groups. This is not proof of no skill.
- **H6 inconclusive:** coverage/matching or uncertainty prevents the comparison.
- Failure to reach statistical significance, by itself, is not evidence against H6; if uncertainty still permits the preregistered meaningful advantage, classify the result as inconclusive.

## Provenance and artifacts

Record run-code SHA, seed, model/config IDs and hashes, checkpoint hashes before/after, shared-file metadata and prepared-array fingerprints, software versions, split sample counts, thresholds, execution date, and source SHA. Freeze code/config before fitting. Version only configs, protocol, tests, JSON/CSV metrics, and report; keep joblib models in ignored isolated artifact storage, never commit checkpoints, caches, or data. No PPO training, GUI, plots, or shared-data writes.
