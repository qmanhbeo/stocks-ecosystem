# Stock RL trade-episode research findings

**Archive status:** parked after Phase 4D on 2026-10-25. This summary is a synthesis of the phase reports, committed protocols/configurations, code, and saved metrics. It does not claim that any hypothesis was proven or that the strategy is investable.

## Chronological record

### Phase 1 — Environment feasibility

**Question and method.** Could a one-trade long-only episode be represented as a Gymnasium environment without changing the existing portfolio-choice environment? A new target-position `OUT/IN` environment was implemented with next-open fills, action masks, a three-interval minimum hold, terminal-only annualized log excess reward, and censoring through truncation.

**Result.** Twenty-nine deterministic synthetic tests passed. MaskablePPO mask discovery worked on the raw environment and `DummyVecEnv`. No model was trained and no real-data strategy result was produced.

**Interpretation and limits.** Mechanics were testable; real-data readiness was not established. Corporate-action adjustment and mask-aware training/evaluation remained unresolved at this point. The user later confirmed dividend-adjusted prices as the working assumption; no independent adjustment audit followed.

**References.** [Phase 1 report](../../../report-stock-rl-trade-episode-phase1.md); implementation captured in baseline commit [`a6d0ca89`](../../../RL-trading-agent/vn_stock_rl/trade_episode/environment.py); tests in [`test_trade_episode.py`](../../tests/test_trade_episode.py). The report and implementation are in one baseline commit, not a separate Phase 1 commit.

### Phase 2 — Alpha signals and PPO wiring

**Question and method.** Could S1 and C16 be loaded causally and used with MaskablePPO? S1 probability and C16 order-pressure rank were added with explicit availability indicators. A mask-aware trainer, evaluation callback, checkpoint reload, and isolated output paths were added.

**Result.** Market-only and market-plus-alpha FPT smoke runs each used seed 1208 and 64 steps. Gradients and parameter changes were finite/nonzero, masked rollouts selected no invalid actions, checkpoints were saved/reloaded, and a minimum-duration reward probe matched the formula. Thirty-seven focused tests passed at that phase.

**Interpretation and limits.** This established wiring and numerical sanity only, not learning or economic value. S1/C16 publication timestamps were not present in their artifacts; timing relied on producer documentation. The selected Alpha history also contaminated the later historical test periods.

**References.** [Phase 2 report](../../../report-stock-rl-trade-episode-phase2.md); configs [`baseline_market.json`](../../configs/trade_episode/baseline_market.json) and [`market_plus_alpha.json`](../../configs/trade_episode/market_plus_alpha.json); code in [`training.py`](../../vn_stock_rl/trade_episode/training.py) and [`signals.py`](../../vn_stock_rl/trade_episode/signals.py); baseline commit `a6d0ca89`. Smoke artifacts currently exist under `/tmp/stock-rl-trade-episode-phase2-smoke-final-20261025/`.

### Phase 3 — FPT-only learning comparison

**Question and method.** Did a small PPO run learn useful entry/exit behavior, and did S1/C16 help? Six models (two feature sets × seeds 1208–1210) trained on FPT for 5,120 steps each, then were compared on 2023–2025.

| Exploratory policy | Trades | Exposure | CAGR | Max drawdown |
|---|---:|---:|---:|---:|
| Market PPO | 69.3 | 66.0% | 13.45% | −27.69% |
| Market + S1/C16 PPO | 71.0 | 64.7% | 11.01% | −27.69% |
| Random valid actions | 121.7 | 66.0% | 7.20% | −34.43% |
| Immediate buy, minimum legal hold | 186 | 74.9% | 28.95% | −24.83% |
| Buy and hold | — | 99.9% | 24.33% | −34.61% |

**Interpretation and limits.** PPO exceeded the random policy but lagged simple immediate-entry trading and buy-and-hold; Alpha PPO lagged market-only. The result is one ticker in a rising exploratory period, not evidence of general skill. Alpha selection had examined 2023–2025. Runs took 31.2 seconds total; no extensive tuning was done.

**References.** [Phase 3 report](../../../report-stock-rl-trade-episode-phase3.md); [`phase3_experiment.py`](../../vn_stock_rl/trade_episode/phase3_experiment.py); baseline commit `a6d0ca89`. Config, metrics, comparison, trade log, and six checkpoints currently exist under `/tmp/stock-rl-trade-episode-phase3-20261025/`; the saved Phase 3 metrics do not record an exact run-code SHA.

### Phase 4A — Shared multi-stock policy and causal normalization

**Question and method.** Did the policy transfer beyond FPT, and could market normalization avoid full-period fitting? One ticker-agnostic MaskablePPO trained on 12 stocks with randomized ticker/start sampling. DGC, MBB, and VHC were excluded from training. Per-stock features use volatility through `t-1` over 60 sessions (0.005 floor), prior-window volume z-scores, bounded Alpha values and missingness bits, and five agent-state variables. Six models (two feature sets × three seeds) trained for 12,288 steps each; 44 tests passed.

| Policy group, exploratory 2023–25 | Mean stock CAGR | Exposure | Mean max drawdown |
|---|---:|---:|---:|
| Market PPO, 12 training stocks | 16.6% | 94.1% | −35.8% |
| Market + S1/C16 PPO, 12 training stocks | 17.8% | 97.2% | −36.2% |
| Market PPO, 3 unseen-to-training stocks | 14.0% | 93.9% | −36.9% |
| Market + S1/C16 PPO, 3 unseen-to-training stocks | 14.1% | 96.9% | −37.5% |
| Buy-and-hold, training / unseen | 17.9% / 15.7% | — | — |
| Mechanical three-day, training / unseen | 18.7% / 22.8% | — | — |

**Interpretation and limits.** PPO produced functioning, high-exposure policies but did not consistently beat the simple mechanical strategy. Alpha gains appeared in only 17/36 paired training stock-seed results and 3/9 unseen results. A fixed-three-day random policy could not match PPO exposure: its theoretical ceiling was about 75%, versus 95.6% PPO target exposure. Results are equal-weight averages of independent stock paths, not a portfolio. BCG adds some inactive-history coverage but does not eliminate survivorship bias.

**References.** [Phase 4A report](../../../report-stock-rl-trade-episode-phase4a.md); [`phase4a_data.py`](../../vn_stock_rl/trade_episode/phase4a_data.py); implementation and report are in `a6d0ca89`. The run took 167 seconds; its config, metrics, comparison, trade log, and checkpoints currently reside under `/tmp/stock-rl-trade-episode-phase4a-20261025/`. The Phase 4B manifest verifies six checkpoint hashes but records `phase4a_generating_git_sha: null`; the nearby baseline commit is not asserted to be the training SHA.

### Phase 4B — Exposure controls and regime falsification

**Question and method.** Were Phase 4A outcomes explained by exposure/holding behavior (H1), or by bull-market drift (H5)? Frozen checkpoints were evaluated with validation-calibrated feature-blind controls, mechanical three-day trading, buy-and-hold, and causal VNINDEX regimes. PPO was not retrained. The protocol used 50 randomized paths per ticker/variant/split and clustered uncertainty.

**Results.** H1 and H5 were both **inconclusive**. The randomized controls did not pass the H1 matching gate: mean holding-duration errors were 40–63%, beyond the 20% limit. On 2023–2025, PPO-minus-control returns on training stocks were −3.36 percentage points (95% interval −28.39 to +6.39) market-only and +1.96 pp (−4.13 to +13.25) Alpha. On unseen stocks they were −0.33 pp (−12.64 to +9.77) and −0.89 pp (−10.00 to +6.78). In falling regimes, all reported PPO-minus-control intervals crossed zero; on falling training-stock blocks PPO also trailed the three-day mechanical policy by 5.58 pp and 6.07 pp.

**Interpretation and limits.** The invalid matching prevents a clean exposure-shortcut conclusion. Unfavorable-regime outperformance was not demonstrated, but H5 was not falsified because uncertainty was broad and validation/exploratory dates were previously examined. The checkpoint-generating Phase 4A SHA is unknown; checkpoint hashes are preserved.

**References.** [Phase 4B report](../../../report-stock-rl-trade-episode-phase4b.md); [pre-registered protocol](phase4b/protocol.md); [config](../../configs/trade_episode/phase4b_falsification.json); [metrics and stock-period/regime/control CSVs](phase4b/results/phase4b_metrics.json); runner commit `37a145ca`, results commit `0fea0b0c`, report commit `9ad102d2`.

### Phase 4C — Predictive-information audit

**Question and method.** Did Phase 4A observations associate with entry reward and SELL-versus-HOLD outcomes? A predeclared, no-model-fit audit measured within-ticker/year rank associations at fixed next-open horizons. It produced 44,394 ticker-year correlations and 1,692 summaries across 12 training and three unseen-to-training tickers.

**Results.** S1's validation association with the three-interval entry reward was weak: `rho=.030` on training stocks (95% interval −.003 to .068) and `.039` on unseen stocks (−.019 to .104). For SELL-now versus holding three more intervals at the minimum eligible age, S1 reached `.185` (`.142,.223`) on training and `.166` (`.116,.217`) on unseen stocks; C16 was `.097` (`.034,.158`) and `.075` (`−.009,.131`) respectively. Prior Alpha Lab studies reported one-day cross-sectional ICs of `.1491` for S1 and `.0738` for C16, but those are different targets.

**Interpretation and limits.** H2 was classified as **contradicted only for the narrow “no decision-relevant predictive association in these observations” claim**. The audit establishes association, not profitable entry or exit decisions. It had no multiple-comparison adjustment; 2023–2025 informed Alpha selection; only three unseen tickers were available; and synthetic exit states assumed zero waiting duration.

**References.** [Phase 4C report](../../../report-stock-rl-trade-episode-phase4c.md); [evidence inventory](phase4c/evidence_inventory.json); [target protocol](phase4c/target_alignment_protocol.md); [metrics and associations](phase4c/results/phase4c_metrics.json); run-code commit `797a0c32`, results commit `bc7cc9f0`, report commit `c548ed53`.

### Phase 4D — Supervised fixed-continuation exit test

**Question and method.** Could a supervised SELL-versus-HOLD predictor convert the Phase 4C association into a useful executable exit policy (H6)? Four Ridge/ExtraTrees variants used market-only or market-plus-S1/C16 inputs, alongside constant and age-only prediction baselines. They fit 20,129 sampled states from 12 training tickers (2015–2019); thresholds used training-ticker validation data (2020–2022); DGC/MBB/VHC were excluded from fitting and threshold selection. The label was the exact reward difference between SELL at the next open and HOLD three more intervals then sell; it is a fixed-continuation decision value, not a full Q-function. Evaluation used common scheduled entries every 42 trading rows, daily exit reevaluation, a 40-interval cap, and 100 feature-blind randomized exit paths per model. PPO was frozen.

| Exploratory exit policy | 12 training stocks | 3 unseen-to-training stocks |
|---|---:|---:|
| ExtraTrees + S1/C16 | 1.45% CAGR, 25.8% exposure | 3.01%, 25.7% |
| Matched random mean | 0.59% | −0.28% |
| Mechanical 20-interval exit | 6.19% | 4.55% |

ExtraTrees Spearman on exploratory labels was `.464` market-only and `.469` with Alpha; MAE changed from `.531` to `.529`. ExtraTrees + Alpha matched random mean duration within 1.2 intervals and exposure within 2.7 pp. Its paired CAGR difference versus random was +0.86 pp (95% interval −5.17 to +6.45) on training stocks and +3.29 pp (−5.99 to +12.50) on unseen stocks. Both intervals include zero. H6 is **inconclusive**: uncertainty allows meaningful gains, Ridge controls failed the match gate, and the best supervised policy did not beat all mechanical controls.

Frozen PPO full-policy CAGRs (16.6–17.8% training; 14.0% unseen) used different entries and 94–97% exposure, so they are descriptive, not an exit-only comparison. The separate PPO-entry exit diagnostic is overlapping per-trade analysis, not a compounded portfolio. One failed run and a final JSON serialization failure are explicitly preserved in `phase4d_metrics.json`; finalization used saved CSVs without retraining or replay.

**References.** [Phase 4D report](../../../report-stock-rl-trade-episode-phase4d.md); [protocol](phase4d/protocol.md); [configuration](../../configs/trade_episode/phase4d_supervised_exit.json); [metrics and compact results](phase4d/results/phase4d_metrics.json); successful evaluation code SHA `501f6c2c`; metrics-finalizer commit `e3b84c63`; results/report commit `30ab5120`. Model files remain ignored under `/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/artifacts/trade_episode/phase4d-20261025-run2/`; their hashes are in the metrics JSON.

## Synthesis

### Established by the saved evidence

- The isolated Gymnasium environment, legal-action masks, next-open execution, causal observation construction, and multi-stock ticker-agnostic sampling are implemented and covered by deterministic tests.
- PPO produced finite, functioning policies on the tested budgets. It did **not** demonstrate repeatable superiority over simple mechanical strategies; observed policies often remained invested 94–97% of the time.
- The existing state has measurable associations with some reward targets, especially short-horizon SELL-versus-HOLD labels. Supervised prediction quality alone did not yield a robust chronological economic advantage.
- The per-trade annualized log excess objective is not equivalent to maximizing chronological portfolio wealth: it omits time spent waiting in cash and the frequency/sequence of completed trades. Phase 4D's 20-interval mechanical exit exceeded the tested supervised CAGRs.

### Plausible explanations, not established causes

Sparse terminal reward, high variance in short-horizon annualized targets, PPO exploration/credit assignment, limited training budgets, and high exposure are all plausible contributors to the gap versus simple controls. Phase 4B's failed matching means exposure cannot be isolated as the cause. No phase conducted a systematic PPO optimization study.

### Still unanswered

Whether the features support a robust policy after realistic costs and on a genuinely untouched period; whether the S1/C16 availability contract is point-in-time complete; what economic objective is actually desired; and whether PPO can learn a reliable policy with sufficient exploration and a better-aligned reward. These experiments do **not** prove that RL is unsuitable for stock trading, nor that profitable alpha cannot exist.

## Provenance and reproduction cautions

Phase 4B–4D protocols/configs/results are versioned. Phase 4B and Phase 4D record run code commits, seeds, data/checkpoint fingerprints, and model references. Phase 4C records its code SHA, protocol/config hashes, date cutoff, and prepared-input fingerprints. Phase 2 smoke, Phase 3, and Phase 4A model bundles are currently present under `/tmp`, which is not durable archival storage. Phase 3 metrics do not contain a run-code SHA. The Phase 4A checkpoint manifest explicitly lacks its generating SHA, although its six checkpoint hashes currently verify. The shared Parquet dataset is external to Git; Phase 4A/4B/4C/4D metadata and prepared-array fingerprints are recorded to identify the inputs used. There is no independent audit of dividend-adjustment factors.
