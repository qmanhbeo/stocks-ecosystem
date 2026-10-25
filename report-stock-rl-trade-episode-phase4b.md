# Stock RL Phase 4B — Falsification Results

**Experiment:** `rl-trade-episode-phase4b-20261025`

**Run-code SHA:** `37a145ca60a255bc161e22029b1805bb322e4dfb`

**Results commit:** `0fea0b0c275cd41876955e17366464ea1f635f45` — pushed to `origin/exp/stock-rl-trade-episode`.

## Findings

| Hypothesis | Finding | Evidence |
|---|---|---|
| H1: exposure shortcut | **Inconclusive** | On exploratory 2023–25, PPO minus feature-blind control return was market-only −3.36pp (95% ticker/year CI −28.39 to +6.39) and Alpha +1.96pp (−4.13 to +13.25) on training stocks; unseen stocks were −0.33pp (−12.64 to +9.77) and −0.89pp (−10.00 to +6.78). Controls failed the preregistered test matching gate: mean holding-duration errors were 40–63%, above the 20% limit. These are not valid matched-control conclusions.
| H5: bull-market dependence | **Inconclusive** | In falling regimes, PPO minus randomized-control return on trained stocks was +0.88pp (−1.96 to +3.82) market-only and +0.22pp (−2.13 to +2.40) Alpha; on unseen stocks it was −4.03pp (−17.68 to +5.13) and −3.97pp (−14.77 to +2.44). All intervals crossed zero. In falling trained-stock blocks PPO also lagged mechanical three-day trading by 5.58pp and 6.07pp respectively. Neither policy showed a reproducible unfavorable-regime advantage.

Exploratory-period mean **per-stock CAGR** (independent paths, not a portfolio):

| Policy | Trained stocks | Unseen stocks |
|---|---:|---:|
| Market-only PPO | 16.55% | 14.03% |
| Alpha PPO | 17.81% | 14.06% |
| Mechanical three-day | 18.67% | 22.81% |
| Buy-and-hold | 17.95% | 15.67% |

PPO remained highly exposed (94–97%). Average holds ranged from 55 to 118 trading intervals for market-only and 45 to 60 for Alpha; trade counts averaged 12–14 per stock path. The feature-blind controls did not reproduce this test-period duration behavior. Stock-level CAGR averages must not be read as an investable combined portfolio.

## Protocol, verification, and limits

Frozen Phase 4A checkpoints only; no PPO training. Evaluated 12 training-universe and 3 unseen tickers; regimes used causal VNINDEX 126-session returns (rising ≥10%, falling ≤−10%, otherwise sideways). 2015–19 was in-sample, 2020–22 previously examined validation, and 2023–25 exploratory and Alpha-selection-contaminated. No post-2025 observations entered; maximum date was 2025-12-31. The Phase 4A reference reproduced exactly across 1,730 non-null metric comparisons; 70 nulls were skipped. Dataset and checkpoint hashes were unchanged. Focused suite: **54 passed**.

The checkpoint-generation Git SHA is unavailable; recorded checkpoint hashes/configuration are preserved. A summary-only reference-row count was corrected after the run (180 rows); policy values and recorded run-code SHA are unchanged. Results, controls, regime blocks, and trades are in `RL-trading-agent/research/trade_episode/phase4b/results/`.

**Recommendation:** Do not train more PPO yet. First improve and validate the feature-blind duration matching on held-out data, then test on a future untouched period.
