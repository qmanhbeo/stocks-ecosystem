# Stock RL Phase 4C — Predictive Evidence Audit

## Findings

Prior Alpha Lab evidence establishes short-horizon cross-sectional signal: S1 H93 reported mean one-day IC **0.1491, positive in 11/11 annual walk-forward folds** for close-to-close relative direction; C16 H356 reported IC **0.0738, positive in 11/11 years**, with residual IC 0.0687 in H357. H359 passed its own execution-aware static-selector gate, while H412 found C16 alone near zero under a different construction. These studies do not establish profitable RL entry/exit behavior. Phase 4B PPO also failed to beat the mechanical benchmark reliably, but that does not isolate feature usefulness.

## Target-aligned extension

Before implementation, protocol `34134088` specified within-ticker/year associations to the exact Phase 4A next-open reward at 3/10/20 intervals and SELL-now versus HOLD-longer reward differences. The read-only run used 12 training-universe stocks and 3 unseen stocks, with 2015–19/2020–22/2023–25 partitions. It computed 44,394 ticker-year correlations and 1,692 summaries; no model was fit or trained. The maximum prepared date was 2025-12-31, no later observations were used, and shared-data metadata was unchanged.

For the 2020–22 validation period, S1 association with 3-interval entry reward was weak: **ρ=.030** (95% hierarchical interval −.003,.068) on training stocks and **.039** (−.019,.104) on unseen stocks. Prior 1-day return versus that reward was modestly negative (−.053 training; −.066 unseen). For SELL-versus-HOLD at entry age 3 and a further 3-interval hold, S1 was more informative: **ρ=.185** (.142,.223) training and **.166** (.116,.217) unseen. C16 was **.097** (.034,.158) training and .075 (−.009,.131) unseen. In 2023–25, S1 entry ρ was .059 training/.081 unseen; treat this as exploratory because those years informed Alpha Lab selection.

## H2 verdict and next step

**Contradicted for the claim that the current observation contains no useful decision-relevant predictive information.** S1, C16, recent returns, and unrealized-return state show associations with the specified trade targets, including SELL-versus-HOLD. This does **not** prove profitability or explain PPO’s failure: associations are not policy tests, Alpha Lab periods were repeatedly examined, no multiple-comparison adjustment was applied, and only three unseen tickers were available. Synthetic exit states assume zero waiting duration.

Do not add features or increase PPO training yet. Next, test decision-level learnability with a small teacher/supervised benchmark on the same observations, masks, and exact reward labels, then compare against PPO on chronological validation.

## Provenance

Evidence inventory: [evidence_inventory.json](RL-trading-agent/research/trade_episode/phase4c/evidence_inventory.json). Detailed results: [phase4c_metrics.json](RL-trading-agent/research/trade_episode/phase4c/results/phase4c_metrics.json) and [phase4c_feature_associations.csv](RL-trading-agent/research/trade_episode/phase4c/results/phase4c_feature_associations.csv). Run code SHA: `797a0c32d65f06666ac20c48027da590a37a0bfb`; results commit `bc7cc9f0ccc1dc4e628fe19031f7605e572ddb2d` was pushed to `origin/exp/stock-rl-trade-episode`. This report is committed afterward; final branch SHA and final push verification are included in the handoff.

Verification: **48 relevant Phase 4A, trade-episode, and Phase 4C tests passed**; Ruff and Python compile checks passed. No PPO training was run.
