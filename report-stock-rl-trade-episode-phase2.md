# Stock RL Trade Episode — Phase 2 Readiness Report

**Date:** 2026-10-25  
**Worktree:** `/home/manh/stocks-ecosystem-worktrees/rl-trade-episode`  
**Branch:** `exp/stock-rl-trade-episode`

## 1. Executive summary

The isolated trade-episode environment now has a dedicated MaskablePPO entry point, causal OHLCV features, optional Alpha Lab features, paired baseline/alpha configurations, and a chronological evaluation helper. The original stock RL checkout and Alpha Lab files were not modified. Shared Parquet inputs are opened read-only; training outputs and Matplotlib cache are outside the repository and shared data root.

Two Alpha features were integrated as separate observation columns: S1 `xs_proba` and C16 `order_volume_ratio_rank`, each with an availability indicator. The S1 target column `actual` is never loaded. C23/C24 have higher reported ICs, but their state coverage and execution validation are incomplete and there is no maintained published time-series artifact to consume, so they are deferred.

The market-only and market-plus-alpha variants each passed a 64-step CPU smoke run at seed 1208. Gradients and model parameters remained finite, nonzero gradients and parameter updates were observed, mask-aware evaluation/reloaded rollouts selected no invalid actions, and periodic/final checkpoints were saved; both final models were reloaded. A real-history three-interval trade probe matched the specified terminal reward exactly. These results confirm wiring only; they do not estimate strategy quality.

**Recommendation: GO WITH PRECAUTIONS.** The implementation is ready for controlled exploratory training. Do not treat the configured 2023–2025 development test as out-of-sample: Alpha signal discovery and validation used that research period. The configs reserve 2026 onward as a possible final lockbox but do not load it. The Alpha Lab instruction says not to touch 2026 data until authorized, and C16's maintained artifact currently ends in 2025. A clean final evaluation therefore still needs an authorized, point-in-time Alpha refresh and confirmation that its period was not used for later signal selection.

## 2. Architecture and change boundary

The work was performed only in the stock RL experiment worktree on `exp/stock-rl-trade-episode`. The original `/home/manh/stocks-ecosystem` checkout remains on `main` with a clean working tree. No Alpha Lab source/output or shared data file was edited. `sb3-contrib` was already declared in `RL-trading-agent/pyproject.toml`; no dependency installation or packaging change was needed.

The shared-data alias `/home/manh/stocks` resolves to `/home/manh/stocks-ecosystem`; the data root used for the smoke runs was `/home/manh/stocks-ecosystem/data` (the same resolved root returned by `shared_data_root()`). The CLI accepts `STOCKS_DATA_ROOT` or `--data-root` and never copies the dataset.

| File | Change |
|---|---|
| [`environment.py`](/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/vn_stock_rl/trade_episode/environment.py:41) | Added seeded random training starts and an explicit `user_assumed_dividend_adjusted` price-basis label. Existing two-action, reward, and mask semantics remain. |
| [`data.py`](/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/vn_stock_rl/trade_episode/data.py:30) | Added bounded date-filtered, read-only OHLCV loading and bounded tradability joins. |
| [`market_features.py`](/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/vn_stock_rl/trade_episode/market_features.py:6) | Added eight causal daily OHLCV features. |
| [`signals.py`](/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/vn_stock_rl/trade_episode/signals.py:18) | Added exact-date S1/C16 joins; target labels are not requested and missingness is explicit. |
| [`features.py`](/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/vn_stock_rl/trade_episode/features.py:8) | Added train-only mean/std fitting and training-mean imputation for missing signal values. |
| [`training.py`](/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/vn_stock_rl/trade_episode/training.py:68) | Added config loading, split-safe data preparation, MaskablePPO training/evaluation callbacks, gradient checks, checkpoint reload, and chronological portfolio evaluation for non-smoke runs. |
| [`train_cli.py`](/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/vn_stock_rl/trade_episode/train_cli.py:15) | Added `python -m vn_stock_rl.trade_episode.train_cli` entry point; Matplotlib cache is set inside the experiment output root before Torch/SB3 imports. |
| [`evaluation.py`](/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/vn_stock_rl/trade_episode/evaluation.py:67) | Added chronological masked evaluation that compounds realized trade returns, records exposure and trade details, and marks an open final position without fabricating a sale. |
| [`baseline_market.json`](/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/configs/trade_episode/baseline_market.json:1), [`market_plus_alpha.json`](/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/configs/trade_episode/market_plus_alpha.json:1) | Added matched experiment configurations. |
| [`test_trade_episode.py`](/home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent/tests/test_trade_episode.py:1) | Expanded deterministic environment, feature, Alpha-join, chronology, and configuration tests. |

Installed versions used: Python 3.10, Gymnasium 0.29.1, Stable-Baselines3 2.4.1, sb3-contrib 2.4.0, and PyTorch 2.11.0+cu130. The RL package already declares Gymnasium, Stable-Baselines3, sb3-contrib, pandas, NumPy, and PyArrow.

## 3. Alpha Lab inventory and evidence

Verified source material includes `alpha-research-lab/notes/signal_library.md`, `notes/live_state.md`, `cross_sectional_wf.py`, and `data_tools/build_order_pressure_features.py`. The library reports mostly daily cross-sectional information coefficients against one-day barrier targets. Those ICs are Alpha Lab evidence, not evidence for this different single-stock trade-episode reward.

| Signal | Definition, frequency, coverage | Reported evidence and decision |
|---|---|---|
| **S1 / H93** | Daily cross-sectional XGBoost probability. Captures short-term relative momentum with volume features; artifact column `xs_proba` is emitted with `actual`. H93 uses a 1-day ±1% barrier target. Alpha reports 100% coverage on its 2015–2025 panel. | IC +0.149, p<0.001, 11/11 positive years. The walk-forward code trains each test-year model on rows from earlier years (`cross_sectional_wf.py:660–668`), so each year's probability is generated out of that year's fitting sample. The signal family was still selected/researched over 2015–2025, which contaminates RL holdouts in that span. **Integrated:** `xs_proba` only; `actual` is excluded. See `signal_library.md:64–96`. |
| **C16 / H356–H360** | Daily cross-sectional rank of `(buy_order_volume − sell_order_volume) / (buy_order_volume + sell_order_volume)` from CafeF posted order statistics. Same-day order flow; no rolling lookback in the rank itself. Alpha documents after-close availability and next-open use. Published artifact has `order_pressure_available`, `can_buy_next_open`, and H359 blend metadata; documented coverage 98.0431% in 2015–2025. | Standalone IC +0.0738, 11/11 positive years, correlation with S1 +0.0342; split ICs dev +0.0799, validation +0.0593, confirmation +0.0713. Execution tests were mixed before the scoped H359 version; it is `LAB_PROMOTED_PENDING_EXECUTION`, not a universal RL result. **Integrated:** raw rank and availability only. The H359 5% blended selector is not applied. See `signal_library.md:631–720`; builder formula at `build_order_pressure_features.py:122–128`. |
| **C4–C14 candidate atoms** | Daily features including 5-day overnight/intraday asymmetry (C4), sparse insider relative size (C5), sector-relative contrarian rank (C6), price-limit counts (C7), volume z-scores (C8), negated one-day reversal rank (C9), 20-day Amihud illiquidity rank (C10), lagged 60-day momentum rank (C11), gap absorption (C12), compression/blow-off state (C13), and volume-residual close-location rank (C14). Most are in the Alpha matrix or maintained daily feature tables; several are computed inline. | Usually ICs around +0.01 to +0.04, with varying year consistency; C5 is event-sparse (~3.39%). Examples: C4 +0.0225 (11/11), C6 +0.0299 (11/11), C9 +0.0284 after sign reversal (11/11), C13 +0.0351 (10/11). **Deferred:** many dimensions, weaker evidence, and high overlap/turnover relative to the two selected features. Definitions/evidence: `signal_library.md:102–598`. |
| **C15 news** | LLM news state features, nonzero coverage concentrated in 2016–2017. | Strong conditional pockets but only 0.19% overall nonzero coverage and no active-book coverage after 2017. **Deferred** as sparse and unavailable for the intended broad period (`signal_library.md:601–627`). |
| **C17/C18 order-flow derivatives** | C17 is the raw order-volume ratio; C18 is today's C16 rank minus the prior day's rank. Both daily. | C17 reports IC +0.077, 8/8 positive years; C18 reports IC +0.129 and 8/8 positive years, with 2023–2025 validation in the library. However, the live-state execution check classifies C17/C18 quick portfolio tests as fragile (5/11 and 6/11 positive folds). C18 is causally derivable from C16, but it is a high-churn derivative of an already included signal. **Deferred** for a separate ablation after the two-feature baseline is established. See `signal_library.md:770–859` and `live_state.md:129–141`. |
| **Q1 weak-signal quorum** | Composite of weak candidate votes, with component selection trained on earlier years in each fold. | IC +0.05826, 7/7 walk-forward years 2019–2025; it is a composite, not an independent primitive, and its components are themselves a broad selected library. **Deferred** to avoid importing a data-mined score as if it were an observation (`signal_library.md:724–763`). |
| **C23** | 20-day mean Amihud illiquidity rank ≥0.80 combined with top-20% 5-day volatility expansion. Daily, state-sparse. | IC +0.2029 for illiquidity state and +0.2616 for the combo, 11/11 positive years. High reported signal evidence, but execution readiness is `warn`, coverage is not normalized, and Alpha labels it `NEEDS_EXPORT`. No canonical C23 time-series artifact was found in the shared feature directory. **Deferred** rather than rebuilt. See `signal_library.md:1002–1043`; current Alpha status at `live_state.md:143–157`. |
| **C24** | Two or more +7% ceiling hits in three days with volume expansion. Daily, event-sparse. | IC +0.2353, 8/8 positive years; execution readiness `warn`, no normalized coverage audit, and `NEEDS_EXPORT`. No canonical C24 feature artifact was found. **Deferred**. See `signal_library.md:1047–1081`; `session_00118_log.md:19–32`. |
| **C25/C26** | C25 uses low VWAP-deviation rank plus volatility expansion; C26 uses positive order imbalance, illiquidity rank, and volatility expansion. | IC +0.1733 and +0.1889, respectively, each 11/11 positive years, but both are sparse, `warn`, and `NEEDS_EXPORT`; C25 needs VWAP computation. **Deferred** (`signal_library.md:1085–1157`). |
| **C27 implementation pain** | Inverts next-open tradability flags: cannot buy or cannot sell. | IC +0.1477, 10/10 positive years, but it is coupled to the execution/tradability target and could expose execution availability as a target proxy. **Deferred** pending a separate leakage/causal contract (`signal_library.md:1161–1186`). |

Other C19–C22 families are also marked `NEEDS_EXPORT` in Alpha's live state. A tested `C17+S1` additive ranker uses `0.90*S1 + 0.10*volume_rank`; it is a combined prediction score, not a raw market observation. It was deliberately not substituted for observations (`signal_library.md:801–827`).

## 4. Observation and availability definition

The environment observation is the following causal sequence, with five state fields appended by the Phase 1 environment:

| Feature(s) | Calculation at decision close `t` | Availability / preprocessing |
|---|---|---|
| `market_log_return_1d`, `_5d`, `_20d` | Log close-to-close returns using close at `t` and earlier closes. | Available after close `t`; 20-session warmup rows are dropped. |
| `market_intraday_log_return` | `log(close[t] / open[t])`. | Available after close `t`. |
| `market_overnight_gap_log_return` | `log(open[t] / close[t-1])`. | Available at close `t`. |
| `market_high_low_range_log` | `log(high[t] / low[t])`. | Available after close `t`. |
| `market_realized_volatility_20d` | Rolling sample standard deviation of daily log returns through `t`. | Uses current day's close only after it is observed. |
| `market_volume_zscore_20d` | `log1p(volume[t])` versus mean/std of the *prior* 20 daily log volumes. | Current volume is known after close; reference window is shifted one day. |
| `alpha_s1_xs_proba`, `alpha_s1_available` | Exact `(time,ticker)` match to S1 output; no forward fill. | Only `time,ticker,xs_proba` are requested from Parquet. `actual` is never loaded. No inference timestamp is stored; causal validity relies on Alpha's documented yearly walk-forward construction and close-to-next-open timing. |
| `alpha_c16_order_volume_ratio_rank`, `alpha_c16_available` | Exact `(time,ticker)` match to published C16 feature. | Published after the day per Alpha documentation. The artifact has a date, not a publication-time field; execution assumes it is available before the next-open order. Missing/unavailable ranks remain missing with a 0/1 indicator. |
| `position_in` | OUT/IN flag. | Current environment state. |
| `holding_intervals_normalized` | Fill-to-fill trading intervals divided by max holding horizon. | Current environment state. |
| `entry_relative_unrealized_log_return_scaled` | `log(close[t] / entry_fill_price) / 0.10`. | Uses observed close `t` and known entry fill. |
| `waiting_steps_normalized`, `episode_steps_normalized` | Current counters divided by their configured horizons. | Current environment state. |

Baseline observations have **13** values (8 market + 5 state); Alpha observations have **17** (8 market + 4 Alpha + 5 state). Entry price itself is not exposed; its current relative return is. The Phase 1 observation never included an actual volume of shares or a position size because the environment is all-in/all-out with normalized capital 1.

All market and Alpha columns are standardized with mean/std fitted only on the configured training rows. Missing Alpha values are imputed to that training mean, yielding zero after scaling; availability indicators remain separate. No clipping is applied. The tests perturb future OHLCV rows and confirm earlier feature rows do not change.

Decision timing is: observe information through close `t`, choose target OUT/IN, execute at the next available open `t+1`. A BUY fills at next open; the earliest legal SELL action fills at the open three trading-day intervals after entry. The user-confirmed dividend-adjusted assumption is recorded as `user_assumed_dividend_adjusted`; no independent corporate-action verification was performed or required.

## 5. Actions, reward, masks, and episode boundaries

The discrete action space remains `0=OUT`, `1=IN`: OUT while flat waits, IN while flat buys, IN while invested holds, and OUT while invested sells. A valid SELL terminates the one-trade episode. Shared next-open tradability flags are also honored.

The reward is unchanged:

```text
(252 / T) * (log(P_sell) - log(P_buy)) - log(1.07)
```

All intermediate rewards remain zero. No transaction costs, reward shaping, clipping, or reward normalization were added. The configured algorithm is MaskablePPO with `gamma=1.0`. The environment's `action_masks()` excludes SELL unless the next-open fill would be at least three intervals after BUY; the same environment masks are used by MaskablePPO rollout collection, `MaskableEvalCallback`, and post-reload prediction.

Only a valid SELL returns `terminated=True`. Data end and wait/episode/holding time limits return `truncated=True`, no fabricated trade reward, and an open position's mark-to-market value in `info`. `DummyVecEnv` passes the truncation marker and terminal observation to SB3; SB3's on-policy rollout code bootstraps time-limit truncations. The trade can still be incomplete at a time limit, so the bootstrapped value is not a realized sale return.

Training resets sample seeded starts within the training split; an episode cannot cross into validation/test rows. Validation uses fixed starts. A no-buy episode can truncate with zero reward. During chronological evaluation, a cash-only timeout starts another finite episode at the next date; an open position at data end is marked, not sold.

## 6. Training and evaluation design

The dedicated command is:

```bash
cd /home/manh/stocks-ecosystem-worktrees/rl-trade-episode
STOCKS_DATA_ROOT=/home/manh/stocks PYTHONPATH=RL-trading-agent \
  /home/manh/miniforge3/envs/stocks/bin/python \
  -m vn_stock_rl.trade_episode.train_cli \
  --config RL-trading-agent/configs/trade_episode/baseline_market.json
```

Use `market_plus_alpha.json` for the Alpha condition. The default output root is `/home/manh/stocks-ecosystem-runs/rl-trade-episode`; the CLI also accepts `--output-root`. `TradeEpisodePaths` rejects roots inside the worktree, workspace, or shared data. Models, periodic checkpoints, TensorBoard files, evaluation NPZ/JSON, copied config, and Matplotlib cache use separate output subdirectories.

Both configs share the same seed (1208), environment, reward, data cutoff, chronological split, and PPO parameters: 100,000 configured steps, `gamma=1`, CPU, learning rate 3e-4, 256 rollout steps, batch 64, 5 epochs, GAE lambda 0.95, entropy coefficient 0.01, and a 64×64 MLP. These settings were **not** run as a full experiment.

The non-smoke chronological evaluation helper reports calendar CAGR, maximum drawdown, exposure, trade count, waiting/holding duration, win rate, buy-and-hold CAGR, 7% benchmark value, and trade-level annualized reward separately. It compounds actual trade returns through idle cash. This distinction matters: maximizing expected annualized excess log return *per trade* is not the same as maximizing calendar-time wealth. The former ignores how long the agent waits in cash and can favor a short high-annualized trade that contributes little to full-period wealth.

## 7. Configured splits and leakage checks

Both primary configs use:

| Role | Dates |
|---|---|
| Train | 2015-01-01 through 2019-12-31 |
| Validation | 2020-01-01 through 2022-12-31 |
| Historical development test | 2023-01-01 through 2025-12-31 |
| Reserved candidate final lockbox | 2026-01-01 onward; marked `reserved_not_loaded` and requires user unlock plus Alpha coverage |

The historical split is chronological and disjoint. The scaler is fit only on train rows. Per-year S1 model predictions are generated from prior-year training data. However, Alpha signal-family discovery/retention and much of the reported validation used the 2015–2025 panel. Therefore the 2020–2025 RL validation/test periods are **selection-contaminated for claims about the value of these selected Alpha features**. They remain useful as development diagnostics only. The configs do not evaluate the reserved lockbox.

The Alpha README for agents explicitly says not to touch 2026 rows until authorized. No 2026 observations were used in the smoke training or feature construction, which was capped at 2020-12-31. One qualification: an earlier schema/date inventory found that the FPT OHLCV Parquet file has a single row group whose metadata spans into 2026. A subsequent inventory read requested only rows through 2025 via a PyArrow row filter; no 2026 values were returned to feature code or analyzed, but the row-group layout means Arrow may physically decode data before applying that filter. I cannot guarantee that the underlying 2026 bytes were never read. No 2026 row was used in preprocessing or training. Future lockbox access should use a physically bounded pre-2026 file or row groups/partitioning that cannot read the held-out rows.

The reserved 2026+ lockbox is a candidate, not yet verified as clean against every later Alpha research activity. The latest inspected `live_state.md` was dated 2026-05-18, while the Alpha rule forbids checking 2026 without authorization. It also cannot currently support the Alpha condition because the published C16 artifact documents coverage only through 2025-12-31. Confirm freeze/coverage before unsealing.

## 8. Smoke test and verification results

Each variant ran on FPT daily data capped at 2020-12-31. The runtime input split was 500 training rows (2018-01-02–2019-12-31), 121 validation rows (2020-01-02–2020-06-30), and 131 prepared smoke-test rows (2020-07-01–2020-12-31). Only the train segment updated the policy; `MaskableEvalCallback` used the validation segment. The smoke-test segment was not scored as a strategy test.

| Check | Market-only | Market + Alpha |
|---|---:|---:|
| Timesteps / seed / device | 64 / 1208 / CPU | 64 / 1208 / CPU |
| Gradient audits | 4 update checks; finite and nonzero | 4 update checks; finite and nonzero |
| Policy parameters | finite; changed during optimization | finite; changed during optimization |
| Reloaded masked rollout | completed SELL; 0 invalid actions | completed SELL; 0 invalid actions |
| Checkpoints | 32-step, 64-step, final, and best saved; final reloaded | 32-step, 64-step, final, and best saved; final reloaded |
| Observation values | finite; 13-dimensional | finite; 17-dimensional |
| Alpha availability in smoke rows | — | S1 99.73%; C16 96.81% |

The real-history minimum-duration probe bought 2018-01-03 at 15.82 and sold 2018-01-08 at 15.59 after exactly 3 intervals; its reward was -1.2978621071 and matched the specified formula. This is a deterministic code-path check, not a result estimate. The post-reload validation episodes also completed with finite rewards. SB3 emitted a non-fatal warning that its evaluation environment was not wrapped in `Monitor`; the raw environment has no wrapper that alters rewards or episode lengths.

Verification run after the final code changes:

```text
37 passed (RL-trading-agent/tests/test_trade_episode.py)
ruff check: all checks passed
```

Smoke artifacts (about 1.1 MiB total) are isolated under `/tmp/stock-rl-trade-episode-phase2-smoke-final-20261025/`. No long training or full test-period performance run was started.

## 9. Learning pathologies and remaining issues

1. **No-trade policy:** waiting or never entering can produce zero episode reward, which can beat a negative trade. The maximum wait horizon makes each episode finite but does not remove this incentive; chronological evaluation can restart cash episodes repeatedly. Do not add a wait penalty without a separate design decision. Monitor zero-trade rate, exposure, and calendar CAGR.
2. **Short-duration magnification:** the required `252/T` annualization magnifies small short-horizon moves; with the three-interval minimum, the multiplier can be 84. This is the specified objective, but it can create large terminal targets and noisy value estimates. No reward clipping was added.
3. **Sparse terminal credit:** most steps have zero reward. PPO/GAE has to assign a terminal trade result backward through a variable-length wait/hold trajectory. Smoke confirms numerical stability at 64 steps only, not learning quality.
4. **Variable episode lengths:** PPO aggregates rollout timesteps, so longer episodes can contribute more state/action samples while only one terminal reward is produced. `gamma=1` avoids time discounting but does not remove this weighting effect. Compare episode-level and chronological metrics and run several seeds before interpreting results.
5. **Open-position truncation:** PPO bootstraps a truncated open state's value, while training auto-resets into a new episode. The chronological evaluator instead marks an open final position. Full evaluation should report truncations and incomplete trades separately.
6. **Signal timestamp contract:** C16's artifact stores a date but no publication time. Its after-close availability is supported by Alpha documentation, not independently timestamp-verified. S1 also lacks a stored inference timestamp; validity rests on the walk-forward producer.
7. **Historical selection contamination:** current 2015–2025 test dates are not a clean Alpha-feature test. The candidate 2026+ lockbox remains unopened and its Alpha coverage/freeze status is unresolved.
8. **Price adjustment:** adjusted prices are accepted as the user's working assumption. No independent audit of split/dividend factors was performed.

## 10. Recommendation for full training

The code is ready for later controlled training runs, but the present configurations should first be treated as engineering and development scaffolding. Before making performance claims:

1. Obtain authorization to use a clean post-2025 lockbox and verify it was not used by later Alpha discovery.
2. Publish or otherwise provide C16/S1 point-in-time values through the same lockbox, with explicit availability timestamps; ensure the data loader physically excludes forbidden dates.
3. Freeze this two-signal set and the reward/environment protocol before unsealing that period.
4. Run the same seed/split/algorithm for baseline and Alpha variants, then report chronological CAGR/drawdown/exposure/trades separately from the terminal per-trade objective. Use multiple seeds only after the bounded smoke has passed.

No full training run was launched in this phase.
