# Stock RL Trade-Episode Experiment — Phase 1 Report

**Date:** 2026-10-25  
**Scope:** isolated worktree, experimental environment, and deterministic tests only. No model training, data preprocessing, dependency installation, commit, or push was performed.

## 1. Executive summary

Created branch `exp/stock-rl-trade-episode` in a linked sparse worktree at `/home/manh/stocks-ecosystem-worktrees/rl-trade-episode`. The original checkout remains on `main` at its previous commit and retains its pre-existing untracked audit reports. The experiment worktree excludes `data/`; it is about 2.1 MiB and reads the canonical shared dataset through the existing `STOCKS_DATA_ROOT` registry contract. The loader requires that variable to be explicitly set, opens Parquet files read-only, and has no data-writing path.

Added an isolated Gymnasium environment with target-position actions, close-time observations, next-open execution, three fill-to-fill minimum holding intervals, `action_masks()` support, terminal-only annualized log excess reward, and censored truncation handling. Added train-only feature standardization, chronological split boundaries, output-path guards, Parquet readers, and a calendar-metric summarizer. **29 deterministic synthetic tests pass; focused Ruff checks pass.** MaskablePPO action-mask discovery was verified for both a raw environment and `DummyVecEnv`; no model was trained.

**Recommendation: GO WITH CHANGES.** The environment mechanics are ready for review and synthetic experimentation. A real-data training smoke test is not ready: current OHLCV adjustment provenance is unresolved, and the existing trainer/evaluator does not yet route to MaskablePPO and its mask-aware evaluation callback. Decide those points before authorizing training.

## 2. Worktree and repository isolation

| Item | Verified result |
|---|---|
| Git root/original checkout | `/home/manh/stocks-ecosystem` |
| Original branch and HEAD | `main`, `3b7201f8d4fedcf690178368cef8e9a2b0d993bb` |
| Experiment branch | `exp/stock-rl-trade-episode` |
| Experiment worktree | `/home/manh/stocks-ecosystem-worktrees/rl-trade-episode` |
| Sparse checkout paths | `RL-trading-agent`, `shared-recommendation`, `shared-market-rules`, `docs` |
| Shared data in worktree | No `data/` directory materialized; no dataset copied |
| Worktree size | About 2.1 MiB at final inspection; shared dataset excluded |
| Filesystem free space | 496 GiB available on the ext4 filesystem at check time |
| Original status | Still `main`; only the five pre-existing untracked audit reports are present |

The new worktree shares Git object storage with the original repository. No existing branch or uncommitted file was overwritten. Source and tests below are untracked in the experiment branch because this phase did not commit anything.

The environment resolver uses the existing registry in `shared-recommendation/shared_recommendation/artifacts.py:36-54`. Because a sparse worktree has no local `data/` directory, the experimental loaders fail clearly unless `STOCKS_DATA_ROOT` points to the canonical shared root. The expected invocation setting is:

```bash
export STOCKS_DATA_ROOT=/home/manh/stocks-ecosystem/data
```

The package reads through `open("rb")` and writes no shared-data files. No OS-level read-only bind mount was installed, so the filesystem itself remains writable to unrelated processes. Training should use a read-only mount or ensure no producer refresh runs concurrently if hard enforcement is required.

## 3. Existing RL architecture and reuse assessment

### Existing environment and state

The only environment class present in `RL-trading-agent/vn_stock_rl/env/` is `PortfolioChoiceEnv` (`portfolio_choice.py:25`). Its action space is `MultiDiscrete`, selecting ticker slots/cash, and its observation in `portfolio_choice.py:534-545` concatenates the current signal-feature tensor, current portfolio weights, and cash weight. The signal columns are caller-configured; there is no single fixed signal list in the environment.

The current portfolio environment represents investment through weights and cash. It tracks holding ages internally, but the observation does not include average holding age, entry price, or entry-relative unrealized return. It is therefore not a suitable state machine for this binary one-stock experiment without semantic changes. The single- and multi-stock files currently imported by `env/__init__.py:3-7`, and `execution_model.py` imported by `portfolio_choice.py`, are absent from this checkout. I did not reconstruct or alter those legacy modules; the new experiment lives in `vn_stock_rl/trade_episode/` and does not import `vn_stock_rl.env`.

`PortfolioChoiceEnv` executes target weights at next opens, accrues daily open-to-open portfolio returns, and may apply configurable turnover costs/tax, benchmark-relative reward, and drawdown penalty (`portfolio_choice.py:600-696`). Its episodes end at the sampled data boundary rather than on a sell. Its training mode samples windows, while validation/test use chronological boundaries. The existing portfolio observation/reward and episode semantics are intentionally unchanged.

### Trainer, framework, dependencies, and paths

The current runner imports SB3 `PPO` and `sb3-contrib` `RecurrentPPO`, plus the regular `EvalCallback` (`training/runner.py:14-18`). Feed-forward MLP construction uses standard `PPO` (`runner.py:1390-1405`); current default MLP `gamma` is 0.99 (`config/defaults.py:14-23`). Installed versions are Gymnasium 0.29.1, Stable-Baselines3 2.4.1, and `sb3-contrib` 2.4.0. The project already declares Gymnasium, SB3, and sb3-contrib dependencies (`pyproject.toml:11-17`).

The existing trainer is not mask-aware and its regular `EvalCallback` is not a drop-in masked evaluator. The new `TradeEpisodeConfig` records `algorithm="MaskablePPO"`, `policy="MlpPolicy"`, and `gamma=1.0`; it does not launch or wire a trainer. `TradeEpisodePaths` isolates future `models`, `logs`, `evaluations`, `cache`, `configs`, and `tmp` directories under `/home/manh/stocks-ecosystem-runs/rl-trade-episode`. It rejects roots inside the shared Git checkout, experiment worktree, or data root, and creates directories only when `ensure_created()` is explicitly called. No training output directories were created.

## 4. New state and action definition

The environment accepts a row-aligned matrix of caller-supplied market features. Those features must be causal and finite; `FeatureStandardizer.fit()` must be applied to the training slice only, then reused unchanged for validation/test. The environment does not invent or silently select legacy indicators/signals.

The observation is the supplied market feature row followed by:

| Added field | Meaning and normalization |
|---|---|
| `position_in` | 0 OUT / 1 IN |
| `holding_intervals_normalized` | Current close index minus entry-fill index, divided by configured maximum holding intervals |
| `entry_relative_unrealized_log_return_scaled` | `log(current close / entry fill) / 0.10`; zero while OUT; not clipped |
| `waiting_steps_normalized` | Number of WAIT actions before entry, divided by maximum wait steps |
| `episode_steps_normalized` | Elapsed actions divided by maximum episode steps |

All observations are `float32` and checked for finite values. Dates, future prices, and terminal rewards are not observation fields. `chronological_splits()` produces disjoint train/validation/test row slices; actual feature selection, date ranges, and episode sampling remain caller decisions.

Actions are `Discrete(2)`: `0=OUT`, `1=IN`. OUT+OUT waits; OUT+IN buys; IN+IN holds; IN+OUT sells. A direct invalid masked action raises `ValueError`.

## 5. Execution, reward, and boundaries

### Execution and the three-interval rule

The implementation follows the shared contract in `docs/execution_reality.md:7-28`: observe features through close `t`, decide after close `t`, and execute at open `t+1`. For an entry at open index `b`, an exit order is eligible only when its next-open fill index is at least `b+3`; that gives `T = sell_fill_index - buy_fill_index >= 3`. Thus, after entry at open `b`, the sell action first becomes available at close `b+2`, where the submitted sale fills at open `b+3`. This is the earliest legal fill-to-fill interval under the repository’s close/next-open convention.

The mask blocks BUY when the aligned `can_buy_next_open[t]` flag is false, and blocks SELL until the three-fill-interval minimum and `can_sell_next_open[t]` are both satisfied. WAIT and HOLD remain valid. For synthetic tests, omitted tradability arrays default to all-true; real-data callers must supply the shared daily flags. `load_daily_tradability_flags()` reads and aligns the existing `tradability_daily.parquet` by ticker and decision date.

### Capital and reward

Each episode begins OUT with cash/capital 1. A BUY uses the full normalized capital to hold `1 / entry_price` shares. There is no leverage, shorting, partial sizing, fee, tax, or slippage. On SELL, cash becomes shares times the next-open exit price and the episode terminates.

All BUY, HOLD, and WAIT transitions return exactly zero. A valid SELL returns the specified, unclipped reward:

```text
(252 / T) * (log(P_sell) - log(P_buy)) - log(1.07)
```

`T` is measured between actual next-open fills. Info includes entry/exit dates and prices, waiting and holding intervals, raw trade return, annualized log trade return, terminal reward, cash, position value, and marked portfolio value. The raw-return and calendar-performance fields are diagnostic; they do not alter the reward.

### Termination and truncation

- Valid SELL: `terminated=True`, reason `sell`, terminal reward once.
- Data boundary, max episode steps, max waiting, or max holding: `truncated=True`, zero environment reward, a distinct reason, no forced sale.
- An open position at truncation reports `truncated_open_position_value` and marked-to-market equity using the last close. It does not set an exit price or terminal trade reward.
- No-BUY and BUY-without-SELL paths are separately visible through entry/exit fields and termination reason.

Default finite caps are 252 episode actions, 252 WAIT actions, and 252 holding intervals; each can be configured. If a cap and data end coincide, data-end reason takes precedence. PPO/SB3’s installed `DummyVecEnv` marks truncations as `TimeLimit.truncated` and supplies a terminal observation; `OnPolicyAlgorithm` then adds `gamma * V(terminal_observation)` to the rollout reward. With `gamma=1`, that bootstrap is unscaled. This is not a fabricated environment SELL reward, but the value bootstrap can still influence returns at a data boundary. A training integration must decide whether to accept this censoring bootstrap or provide a tested boundary-specific policy while retaining the requested `truncated=True` API.

## 6. Data, evaluation, and learning risks

### Price adjustment and leakage

The shared ACB Parquet metadata has columns `time, open, high, low, close, volume` and no adjustment factor/metadata. The VCI fetch call in `alpha-research-lab/data_tools/fetch_stock.py:111-115` invokes `stock.quote.history(...)` without an explicit adjustment argument. This does **not** prove the prices are unadjusted, but it leaves split/dividend treatment unresolved. The new loader labels data `price_basis="unverified"`; `TradeEpisodeEnv` rejects that label and requires `price_basis="verified_adjusted"` or `"synthetic"`. A human or authoritative provider contract must establish whether the chosen price basis covers splits and dividends before real prices are used.

The shared daily tradability artifact is available at `data/features/execution/tradability_daily.parquet` with `time`, `ticker`, volume/price-limit flags, and `can_buy_next_open` / `can_sell_next_open`. The experiment reads those flags; it does not regenerate them. Market features are caller-provided, so their point-in-time timestamps and feature-builder leakage must be reviewed before training.

### Reward objective and pathologies

The requested reward maximizes expected annualized log excess return **per completed trade**, not chronological portfolio wealth. It ignores waiting time before entry, cash intervals between trades, compounding across trades, and the number of opportunities completed per year. Calendar-time CAGR depends on the realized sequence of returns and idle days. The included `summarize_calendar_performance()` separately prepares chronological CAGR, max drawdown, exposure, trade count, average wait/hold, win rate, buy-and-hold CAGR, and the 7% annual comparator. No policy or baseline was evaluated.

The three-interval floor prevents a zero-duration denominator, but annualization still magnifies short trades; with zero trading costs, small price moves can receive large per-trade reward. Preserve the requested formula, and report raw return and duration beside it. A no-BUY or censored-zero-reward episode can be preferable to a negative completed trade, so a wait-to-truncation policy may abstain. Report no-trade and censored rates, not only statistics conditional on completed trades.

With `gamma=1`, variable episode length no longer discounts the terminal reward, but longer paths contribute more zero-reward transitions to fixed PPO rollouts and fewer completed outcomes per environment step. GAE/value estimates can have high variance when the only signal arrives at SELL. The implementation intentionally adds no shaping; monitor completion rates and compare against no-trade, fixed entry/first-legal-exit, buy-and-hold, and the 7% benchmark.

## 7. Files created and tests

All source changes are new files in the experimental branch; no existing source or configuration was edited.

| File | Purpose |
|---|---|
| `RL-trading-agent/vn_stock_rl/trade_episode/environment.py` | Gymnasium environment, masks, accounting, reward, truncation, step info |
| `RL-trading-agent/vn_stock_rl/trade_episode/config.py` | Experiment defaults and guarded isolated output paths |
| `RL-trading-agent/vn_stock_rl/trade_episode/data.py` | `STOCKS_DATA_ROOT` OHLCV and tradability readers using read-only file handles |
| `RL-trading-agent/vn_stock_rl/trade_episode/features.py` | Train-only standardizer and chronological split slices |
| `RL-trading-agent/vn_stock_rl/trade_episode/evaluation.py` | Pure chronological metric summarizer; does not run evaluation |
| `RL-trading-agent/vn_stock_rl/trade_episode/__init__.py` | Experimental package exports |
| `RL-trading-agent/tests/test_trade_episode.py` | Deterministic synthetic unit tests |
| `report-stock-rl-trade-episode-phase1.md` | This report |

**Verification:**

- `29 passed` in the focused `tests/test_trade_episode.py` run.
- `ruff check --no-cache vn_stock_rl/trade_episode tests/test_trade_episode.py`: all checks passed.
- MaskablePPO’s `is_masking_supported()` and `get_action_masks()` returned expected masks for the raw environment and `DummyVecEnv`.
- Tests cover action meanings, next-open BUY, HOLD, three-interval SELL boundary, early SELL rejection, buy/sell masks, terminal formula and positive/zero/negative returns, zero-reward WAIT, data/max-duration truncations, no-buy/no-sell, observations, no same-close execution, split/scaler behavior, output-path isolation, and hash-stable read-only OHLCV/tradability loading.
- Pytest emitted 14 deprecation warnings from installed Matplotlib/PyParsing dependencies; no test failed.
- No long test suite, model initialization, training, preprocessing, or real-data episode was run.

## 8. Open questions before a training smoke test

1. What authoritative price series and corporate-action contract should be used: split-adjusted prices or total-return adjusted prices including cash dividends?
2. Should a dataset-boundary truncation bootstrap the critic under SB3’s default behavior, or should a boundary-specific rollout treatment be added and verified?
3. Which first-run features should be supplied: a small causal OHLCV-derived set or selected lab signals? Any model-generated signals need historical point-in-time training validation.
4. Should the 252-action / wait / holding caps stand as defaults, and how should training choose start indices within the chronological training slice? The environment accepts an explicit `reset(options={"start_index": ...})`; no sampler is included.
5. Should zero-reward no-trade/censored episodes remain valid outcomes? The requested reward makes abstention preferable to negative trades in some cases.

## 9. Readiness and recommendation

**GO WITH CHANGES.** The isolated environment and deterministic mechanics are implemented and tested. It is **not yet ready for a real-data training smoke test** because price adjustment treatment remains unverified and the existing training/evaluation runner does not integrate MaskablePPO plus mask-aware evaluation. Once those choices are resolved, the next step should be a small, isolated masked-PPO smoke run with `gamma=1.0`, a train-only feature scaler, chronological validation, and the no-trade/buy-and-hold/7% baselines. No training was started in this phase.
