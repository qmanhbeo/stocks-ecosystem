"""Headless Phase 4A multi-stock feature ablation and evaluation."""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
import warnings
from pathlib import Path
from typing import Any

os.environ["MPLBACKEND"] = "Agg"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

SEEDS = (1208, 1209, 1210)
TIMESTEPS_PER_MODEL = 12_288
OUTPUT_DEFAULT = Path("/tmp/stock-rl-trade-episode-phase4a-20261025")
REGIME_YEARS = (2023, 2024, 2025)
BENCHMARK_P_GRID = tuple(index / 10 for index in range(11))

METRIC_FIELDS = (
    "mean_terminal_rl_reward",
    "median_terminal_rl_reward",
    "number_of_trades",
    "win_rate",
    "average_holding_duration",
    "median_holding_duration",
    "average_waiting_duration",
    "median_waiting_duration",
    "exposure_percentage",
    "total_calendar_return",
    "chronological_portfolio_cagr",
    "maximum_drawdown",
    "no_trade_episode_count",
    "no_trade_episode_frequency",
    "truncated_episode_count",
    "truncated_episode_frequency",
    "incomplete_episode_count",
    "episode_count",
    "first_action_buy_frequency",
    "immediate_buy_trade_frequency",
    "minimum_hold_exit_frequency",
    "open_position_truncated_episode_count",
    "final_mark_to_market_value",
    "evaluated_trading_intervals",
)


class MechanicalThreeDayPolicy:
    """Enter immediately and sell at the first legal three-interval opportunity."""

    def predict(self, observation, *, action_masks, deterministic=True, **kwargs):
        import numpy as np

        in_position = bool(float(np.asarray(observation).reshape(-1)[-5]) >= 0.5)
        if in_position:
            action = 0 if action_masks[0] else 1
        else:
            action = 1 if action_masks[1] else 0
        if not action_masks[action]:
            raise RuntimeError("Mechanical policy selected an invalid action")
        return np.asarray([action], dtype=np.int64), None


class RandomEntryFixedThreeDayPolicy:
    """Random legal entry, followed by a SELL at the first legal opportunity."""

    def __init__(self, probability: float, seed: int, max_steps: int) -> None:
        import numpy as np

        self.probability = float(probability)
        self.uniforms = np.random.default_rng(seed).random(max_steps + 2)
        self.decision_count = 0

    def predict(self, observation, *, action_masks, deterministic=True, **kwargs):
        import numpy as np

        draw = self.uniforms[min(self.decision_count, len(self.uniforms) - 1)]
        self.decision_count += 1
        in_position = bool(float(np.asarray(observation).reshape(-1)[-5]) >= 0.5)
        if in_position:
            action = 0 if action_masks[0] else 1
        else:
            action = 1 if action_masks[1] and draw < self.probability else 0
        if not action_masks[action]:
            raise RuntimeError("Random-entry policy selected an invalid action")
        return np.asarray([action], dtype=np.int64), None


def _json_default(value: Any):
    import numpy as np

    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _input_paths(data_root: Path, tickers: tuple[str, ...]) -> dict[str, Path]:
    from vn_stock_rl.trade_episode.data import stock_bars_path
    from vn_stock_rl.trade_episode.phase4a_data import UNSEEN_TICKERS
    from vn_stock_rl.trade_episode.signals import C16_ARTIFACT, S1_ARTIFACT

    all_tickers = sorted(set(tickers) | set(UNSEEN_TICKERS))
    result = {
        f"ohlcv_{ticker}": stock_bars_path(ticker, data_root=data_root) for ticker in all_tickers
    }
    result["vnindex"] = stock_bars_path("VNINDEX", data_root=data_root)
    result["tradability"] = data_root / "features" / "execution" / "tradability_daily.parquet"
    result["s1"] = data_root / S1_ARTIFACT
    result["c16"] = data_root / C16_ARTIFACT
    return result


def _stat_inputs(paths: dict[str, Path]) -> dict[str, dict[str, int]]:
    return {
        key: {"size_bytes": int(path.stat().st_size), "mtime_ns": int(path.stat().st_mtime_ns)}
        for key, path in paths.items()
    }


def _regime_labels(data_root: Path) -> dict[int, dict[str, Any]]:
    import numpy as np

    from vn_stock_rl.trade_episode.data import load_daily_stock_bars
    from vn_stock_rl.trade_episode.phase4a_data import DATA_CUTOFF

    index_bars = load_daily_stock_bars(
        "VNINDEX", data_root=data_root, start_date="2022-12-01", end_date=DATA_CUTOFF
    )
    if index_bars["time"].dt.normalize().max() > DATA_CUTOFF:
        raise RuntimeError("Post-cutoff VNINDEX data reached regime calculation")
    yearly: dict[int, dict[str, float]] = {}
    for year in REGIME_YEARS:
        rows = index_bars.loc[index_bars["time"].dt.year == year]
        if len(rows) < 30:
            raise ValueError(f"VNINDEX has insufficient data for {year} regime label")
        log_close = np.log(rows["close"].to_numpy(dtype=np.float64))
        returns = np.diff(log_close, prepend=np.nan)
        yearly[year] = {
            "index_total_return": float(rows["close"].iloc[-1] / rows["close"].iloc[0] - 1),
            "annualized_volatility": float(np.nanstd(returns, ddof=1) * np.sqrt(252.0)),
        }
    volatility_cut = float(np.median([row["annualized_volatility"] for row in yearly.values()]))
    for year, row in yearly.items():
        direction = "up" if row["index_total_return"] >= 0 else "down"
        volatility = "high_vol" if row["annualized_volatility"] >= volatility_cut else "low_vol"
        row["regime"] = f"{direction}_{volatility}"
    return yearly


def _train_one(
    stocks,
    *,
    include_alpha: bool,
    seed: int,
    timesteps: int,
    env_cfg: dict[str, Any],
    checkpoint: Path,
) -> tuple[Any, dict[str, Any]]:
    import torch
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    from vn_stock_rl.trade_episode.phase4a_data import TRAIN_TICKERS, make_multi_stock_train_env
    from vn_stock_rl.trade_episode.training import GradientAuditMaskablePPO, _seed_everything

    _seed_everything(seed)
    torch.set_num_threads(1)
    multi_env = make_multi_stock_train_env(
        stocks,
        tickers=TRAIN_TICKERS,
        env_cfg=env_cfg,
        include_alpha=include_alpha,
    )
    vec_env = DummyVecEnv([lambda: multi_env])
    model = GradientAuditMaskablePPO(
        "MlpPolicy",
        vec_env,
        gamma=1.0,
        learning_rate=3e-4,
        n_steps=256,
        batch_size=64,
        n_epochs=5,
        gae_lambda=0.95,
        ent_coef=0.01,
        seed=seed,
        policy_kwargs={"net_arch": [64, 64]},
        device="cpu",
        verbose=0,
    )
    initial_parameters = [parameter.detach().clone() for parameter in model.policy.parameters()]
    started = time.perf_counter()
    model.learn(total_timesteps=timesteps, progress_bar=False)
    runtime = time.perf_counter() - started
    audit_rows = model.gradient_audit
    if model.num_timesteps != timesteps:
        raise RuntimeError(f"Expected {timesteps} steps, got {model.num_timesteps}")
    if not audit_rows or not all(row["all_finite"] for row in audit_rows):
        raise RuntimeError("PPO gradient audit found missing or non-finite gradients")
    if not any(row["any_nonzero"] for row in audit_rows):
        raise RuntimeError("PPO gradient audit found no non-zero gradients")
    parameters_finite = all(bool(torch.isfinite(row).all()) for row in model.policy.parameters())
    parameters_updated = any(
        not torch.equal(before, after.detach())
        for before, after in zip(initial_parameters, model.policy.parameters(), strict=True)
    )
    if not parameters_finite or not parameters_updated:
        raise RuntimeError("PPO parameters are non-finite or unchanged")

    training_env = vec_env.envs[0]
    samples = {
        ticker: {
            "episodes_started": int(training_env.sample_counts[ticker]),
            "unique_start_dates": len(set(training_env.sampled_start_dates[ticker])),
        }
        for ticker in TRAIN_TICKERS
    }
    missing_tickers = [
        ticker for ticker, record in samples.items() if record["episodes_started"] == 0
    ]
    if missing_tickers:
        raise RuntimeError(f"Training seed {seed} did not sample tickers: {missing_tickers}")

    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(checkpoint.with_suffix("")))
    checkpoint_zip = checkpoint.with_suffix(".zip")
    if not checkpoint_zip.is_file():
        raise RuntimeError(f"Final checkpoint missing: {checkpoint_zip}")
    reloaded = MaskablePPO.load(str(checkpoint_zip), device="cpu")
    result = {
        "variant": "market_plus_s1_c16" if include_alpha else "market_only",
        "seed": seed,
        "algorithm": "MaskablePPO",
        "gamma": 1.0,
        "total_timesteps": int(model.num_timesteps),
        "rollout_steps": 256,
        "gradient_update_count": len(audit_rows),
        "all_gradients_finite": bool(all(row["all_finite"] for row in audit_rows)),
        "any_nonzero_gradient": bool(any(row["any_nonzero"] for row in audit_rows)),
        "parameters_finite": bool(parameters_finite),
        "parameters_updated": bool(parameters_updated),
        "runtime_seconds": runtime,
        "steps_per_second": float(model.num_timesteps / runtime),
        "sampled_tickers_and_starts": samples,
        "checkpoint_path": str(checkpoint_zip),
        "checkpoint_bytes": int(checkpoint_zip.stat().st_size),
        "observation_dimensions": int(multi_env.observation_space.shape[0]),
        "observation_feature_names": multi_env.observation_feature_names,
        "ticker_identity_in_observation": False,
    }
    vec_env.close()
    del model
    return reloaded, result


def _metric_row(
    result: dict[str, Any],
    *,
    policy: str,
    variant: str,
    seed: int | None,
    split: str,
    ticker: str,
    ticker_group: str,
    regime: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "row_type": "stock_evaluation",
        "policy": policy,
        "variant": variant,
        "seed": seed,
        "split": split,
        "ticker": ticker,
        "ticker_group": ticker_group,
        "market_regime": regime,
    }
    row.update({name: result.get(name) for name in METRIC_FIELDS})
    row["action_counts"] = json.dumps(result.get("action_counts", {}), separators=(",", ":"))
    row.update(extra or {})
    return row


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _append_trade_rows(
    destination: list[dict[str, Any]],
    result: dict[str, Any],
    *,
    policy: str,
    variant: str,
    seed: int | None,
    split: str,
    ticker_group: str,
    market_regime: str | None = None,
) -> None:
    for trade in result["trades"]:
        destination.append(
            {
                "policy": policy,
                "variant": variant,
                "seed": seed,
                "split": split,
                "ticker": trade["ticker"],
                "ticker_group": ticker_group,
                "market_regime": market_regime,
                **trade,
            }
        )


def _buy_hold_metrics(env) -> dict[str, Any]:
    import numpy as np

    intervals = env.n_rows - 1
    curve = np.ones(env.n_rows, dtype=np.float64)
    curve[1:] = env.close_prices[1:] / env.open_prices[1]
    drawdown = curve / np.maximum.accumulate(curve) - 1.0
    return {
        "number_of_trades": 0,
        "mean_terminal_rl_reward": None,
        "median_terminal_rl_reward": None,
        "win_rate": None,
        "average_holding_duration": None,
        "median_holding_duration": None,
        "average_waiting_duration": None,
        "median_waiting_duration": None,
        "exposure_percentage": float((env.n_rows - 1) / env.n_rows * 100.0),
        "total_calendar_return": float(curve[-1] - 1.0),
        "chronological_portfolio_cagr": float(curve[-1] ** (252 / intervals) - 1.0),
        "maximum_drawdown": float(drawdown.min()),
        "no_trade_episode_count": 0,
        "no_trade_episode_frequency": None,
        "truncated_episode_count": 0,
        "truncated_episode_frequency": None,
        "incomplete_episode_count": 0,
        "episode_count": 0,
        "final_mark_to_market_value": float(curve[-1]),
        "evaluated_trading_intervals": intervals,
        "trades": [],
        "action_counts": {},
    }


def _regime_eval_mask(stock, year: int) -> Any:
    import numpy as np

    return stock.split_masks["test"] & np.asarray(stock.dates.year == year, dtype=bool)


def _mean_stock_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import numpy as np

    summaries = []
    groups = sorted({(row["split"], row["ticker_group"], row["variant"]) for row in rows})
    for split, ticker_group, variant in groups:
        selected = [
            row
            for row in rows
            if row["row_type"] == "stock_evaluation"
            and row["split"] == split
            and row["ticker_group"] == ticker_group
            and row["variant"] == variant
            and row["policy"] == "MaskablePPO"
        ]
        if not selected:
            continue
        summary: dict[str, Any] = {
            "row_type": "mean_across_stock_backtests",
            "policy": "MaskablePPO",
            "variant": variant,
            "split": split,
            "ticker_group": ticker_group,
            "ticker": None,
            "seed": None,
            "aggregation": "mean_per_stock_per_seed_not_portfolio",
            "stock_backtest_count": len(selected),
            "distinct_ticker_count": len({row["ticker"] for row in selected}),
        }
        for field in METRIC_FIELDS:
            values = [
                float(row[field])
                for row in selected
                if row.get(field) is not None and np.isfinite(float(row[field]))
            ]
            summary[field] = None if not values else float(np.mean(values))
        summaries.append(summary)
    return summaries


def run_experiment(
    *,
    output_root: Path = OUTPUT_DEFAULT,
    timesteps: int = TIMESTEPS_PER_MODEL,
) -> dict[str, Any]:
    import numpy as np
    import torch

    from vn_stock_rl.trade_episode.evaluation import evaluate_chronological_policy
    from vn_stock_rl.trade_episode.phase4a_data import (
        DATA_CUTOFF,
        PHASE4A_TICKERS,
        TRAIN_TICKERS,
        UNSEEN_TICKERS,
        make_stock_env,
        prepare_stock,
    )

    output_root = output_root.expanduser().resolve()
    if output_root.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {output_root}")
    if timesteps < 256 or timesteps % 256:
        raise ValueError("PPO budget must be a positive multiple of 256 rollout steps")
    data_root_raw = os.environ.get("STOCKS_DATA_ROOT")
    if not data_root_raw:
        raise RuntimeError("STOCKS_DATA_ROOT must identify the shared read-only dataset")
    data_root = Path(data_root_raw).expanduser().resolve()

    from vn_stock_rl.trade_episode.config import TradeEpisodePaths

    TradeEpisodePaths(root=output_root)  # validate output isolation without creating directories
    stocks = {ticker: prepare_stock(ticker, data_root=data_root) for ticker in PHASE4A_TICKERS}
    if any(stock.dates.max() > DATA_CUTOFF for stock in stocks.values()):
        raise RuntimeError("Post-cutoff observations reached prepared stock data")
    feature_dimensions = {
        "market_only": {stock.feature_matrix(False)[0].shape[1] + 5 for stock in stocks.values()},
        "market_plus_alpha": {
            stock.feature_matrix(True)[0].shape[1] + 5 for stock in stocks.values()
        },
    }
    if any(len(dimensions) != 1 for dimensions in feature_dimensions.values()):
        raise RuntimeError("Ticker feature dimensions differ")

    input_paths = _input_paths(data_root, PHASE4A_TICKERS)
    input_stats_before = _stat_inputs(input_paths)
    regime_labels = _regime_labels(data_root)
    env_cfg = {
        "min_holding_intervals": 3,
        "annualization_intervals": 252,
        "annual_benchmark": 0.07,
        "max_episode_steps": 756,
        "max_wait_steps": 252,
        "max_holding_intervals": 756,
    }

    output_root.mkdir(parents=True, exist_ok=False)
    (output_root / "models").mkdir()
    (output_root / "cache" / "matplotlib").mkdir(parents=True)
    os.environ["MPLCONFIGDIR"] = str(output_root / "cache" / "matplotlib")
    import matplotlib

    matplotlib.use("Agg", force=True)
    matplotlib.interactive(False)
    torch.set_num_threads(1)

    config_payload = {
        "experiment": "stock_rl_trade_episode_phase4a",
        "worktree_branch": "exp/stock-rl-trade-episode",
        "data_root": str(data_root),
        "shared_data_read_only": True,
        "cutoff": str(DATA_CUTOFF.date()),
        "loaded_row_filter": "exact in-memory date filter after Parquet read and before features",
        "historical_feature_lookback_start": "2014-09-01",
        "training_tickers": list(TRAIN_TICKERS),
        "unseen_tickers": list(UNSEEN_TICKERS),
        "sectors_and_selection_note": (
            "Diversified bank, technology, energy, materials, retail, utilities, brokerage, "
            "real estate, and consumer stocks; BCG retained for ended/suspended-history coverage."
        ),
        "ticker_observation_encoding": False,
        "splits": {
            name: {
                "start": str(stock_meta["split_dates"][name]["start"]),
                "end_min": min(stocks[t].metadata["split_dates"][name]["end"] for t in stocks),
                "end_max": max(stocks[t].metadata["split_dates"][name]["end"] for t in stocks),
            }
            for name in ("train", "validation", "test")
            for stock_meta in [stocks[next(iter(stocks))].metadata]
        },
        "training": {
            "algorithm": "MaskablePPO",
            "gamma": 1.0,
            "seeds": list(SEEDS),
            "timesteps_per_model": timesteps,
            "total_models": 6,
            "total_timesteps": timesteps * 6,
            "n_steps": 256,
            "batch_size": 64,
            "n_epochs": 5,
            "learning_rate": 0.0003,
            "gae_lambda": 0.95,
            "ent_coef": 0.01,
            "net_arch": [64, 64],
            "device": "cpu",
            "workers": 1,
            "tensorboard": False,
            "progress_bar": False,
            "ticker_sampling": "uniform randomized cycles, one visit per ticker per shuffled cycle",
            "start_sampling": (
                "uniform over legal tradable starts inside each ticker's train period"
            ),
        },
        "random_three_day_benchmark": {
            "entry_probability_grid": list(BENCHMARK_P_GRID),
            "probability_calibrated_on": "validation only; fixed for test",
            "exposure_match_note": (
                "A one-position policy with a three-interval hold and next-open re-entry "
                "has a theoretical maximum exposure near 75%; matching higher PPO exposure "
                "is infeasible."
            ),
        },
        "environment": env_cfg,
        "normalization": {
            "method": "per-stock causal rolling, no fit stage or global statistics",
            "volatility_window": 60,
            "volatility_estimate": "daily log-return std through t-1",
            "daily_volatility_floor": 0.005,
            "return_scaling": (
                "1d/5d/20d log returns divided by lagged daily vol times sqrt(horizon)"
            ),
            "intraday_gap_range_scaling": "divide by lagged daily vol",
            "realized_volatility": (
                "log of current causal 20d realized vol and log of lagged absolute 60d vol"
            ),
            "volume": "existing causal prior-20d log-volume z-score",
            "alpha": (
                "bounded S1 probability/C16 rank preserved; availability bits binary; "
                "missing values use 0.5 sentinel"
            ),
            "unrealized_return": (
                "entry-relative log return divided by entry-time lagged vol times "
                "sqrt(holding intervals)"
            ),
            "clipping": False,
        },
        "feature_dimensions": {name: sorted(values) for name, values in feature_dimensions.items()},
        "stock_metadata": {ticker: stock.metadata for ticker, stock in stocks.items()},
        "vnindex_regimes": regime_labels,
        "input_file_stats_before": input_stats_before,
        "reward": "252/T * ln(Psell/Pbuy) - ln(1.07)",
        "price_adjustment_basis": "user_assumed_dividend_adjusted",
        "2026_rows_used": False,
        "alpha_selection_contamination": (
            "2023-2025 is exploratory; Alpha feature family was selected using that panel."
        ),
    }
    (output_root / "phase4a_config.json").write_text(
        json.dumps(config_payload, indent=2, default=_json_default, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    train_summaries: list[dict[str, Any]] = []
    models: dict[tuple[str, int], Any] = {}
    total_started = time.perf_counter()
    for variant, include_alpha in (("market_only", False), ("market_plus_s1_c16", True)):
        for seed in SEEDS:
            model, train_result = _train_one(
                stocks,
                include_alpha=include_alpha,
                seed=seed,
                timesteps=timesteps,
                env_cfg=env_cfg,
                checkpoint=output_root / "models" / f"{variant}_seed{seed}",
            )
            train_summaries.append(train_result)
            models[(variant, seed)] = model

    comparison_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    stock_results: list[dict[str, Any]] = []
    regime_results: list[dict[str, Any]] = []
    benchmark_summaries: list[dict[str, Any]] = []
    random_entry_probabilities: dict[str, float] = {}
    ticker_group = {
        ticker: "unseen_ticker" if ticker in UNSEEN_TICKERS else "training_universe"
        for ticker in stocks
    }

    for split in ("validation", "test"):
        for ticker, stock in stocks.items():
            per_agent: list[tuple[str, int, dict[str, Any]]] = []
            for variant in ("market_only", "market_plus_s1_c16"):
                include_alpha = variant == "market_plus_s1_c16"
                for seed in SEEDS:
                    env = make_stock_env(
                        stock,
                        stock.split_masks[split],
                        env_cfg=env_cfg,
                        include_alpha=include_alpha,
                    )
                    result = evaluate_chronological_policy(
                        models[(variant, seed)], env, seed=seed, deterministic=True
                    )
                    if any(trade["holding_duration"] < 3 for trade in result["trades"]):
                        raise RuntimeError(f"{ticker}: evaluator observed a sub-minimum trade")
                    row = _metric_row(
                        result,
                        policy="MaskablePPO",
                        variant=variant,
                        seed=seed,
                        split=split,
                        ticker=ticker,
                        ticker_group=ticker_group[ticker],
                    )
                    comparison_rows.append(row)
                    stock_results.append(row)
                    per_agent.append((variant, seed, result))
                    _append_trade_rows(
                        trade_rows,
                        result,
                        policy="MaskablePPO",
                        variant=variant,
                        seed=seed,
                        split=split,
                        ticker_group=ticker_group[ticker],
                    )
                    env.close()

            target_exposure = float(
                np.mean([result["exposure_percentage"] for _, _, result in per_agent])
            )
            mechanical_env = make_stock_env(
                stock, stock.split_masks[split], env_cfg=env_cfg, include_alpha=False
            )
            mechanical = evaluate_chronological_policy(
                MechanicalThreeDayPolicy(), mechanical_env, seed=1208, deterministic=True
            )
            comparison_rows.append(
                _metric_row(
                    mechanical,
                    policy="mechanical_immediate_entry_3day_exit",
                    variant="benchmark",
                    seed=None,
                    split=split,
                    ticker=ticker,
                    ticker_group=ticker_group[ticker],
                )
            )
            benchmark_summaries.append(
                {
                    "policy": "mechanical_immediate_entry_3day_exit",
                    "split": split,
                    "ticker": ticker,
                    **{field: mechanical.get(field) for field in METRIC_FIELDS},
                }
            )
            _append_trade_rows(
                trade_rows,
                mechanical,
                policy="mechanical_immediate_entry_3day_exit",
                variant="benchmark",
                seed=None,
                split=split,
                ticker_group=ticker_group[ticker],
            )
            mechanical_env.close()

            hold_env = make_stock_env(
                stock, stock.split_masks[split], env_cfg=env_cfg, include_alpha=False
            )
            hold = _buy_hold_metrics(hold_env)
            hold_row = _metric_row(
                hold,
                policy="buy_and_hold",
                variant="benchmark",
                seed=None,
                split=split,
                ticker=ticker,
                ticker_group=ticker_group[ticker],
            )
            comparison_rows.append(hold_row)
            benchmark_summaries.append(
                {
                    "policy": "buy_and_hold",
                    "split": split,
                    "ticker": ticker,
                    **{field: hold.get(field) for field in METRIC_FIELDS},
                }
            )
            hold_env.close()

            best_random: dict[str, Any] | None = None
            best_probability: float | None = random_entry_probabilities.get(ticker)
            best_distance = float("inf")
            random_seed = (
                810_000
                + sum(ord(char) for char in ticker)
                + (0 if split == "validation" else 10_000)
            )
            probabilities = BENCHMARK_P_GRID if split == "validation" else (best_probability,)
            for probability in probabilities:
                if probability is None:
                    raise RuntimeError(f"No validation-calibrated random policy for {ticker}")
                random_env = make_stock_env(
                    stock, stock.split_masks[split], env_cfg=env_cfg, include_alpha=False
                )
                random_result = evaluate_chronological_policy(
                    RandomEntryFixedThreeDayPolicy(probability, random_seed, random_env.n_rows),
                    random_env,
                    seed=random_seed,
                    deterministic=True,
                )
                difference = abs(random_result["exposure_percentage"] - target_exposure)
                if difference < best_distance:
                    best_distance = difference
                    best_random = random_result
                    best_probability = probability
                random_env.close()
            assert best_random is not None and best_probability is not None
            if split == "validation":
                random_entry_probabilities[ticker] = best_probability
            random_row = _metric_row(
                best_random,
                policy="fixed_3day_exit_exposure_fit_diagnostic",
                variant="benchmark",
                seed=random_seed,
                split=split,
                ticker=ticker,
                ticker_group=ticker_group[ticker],
                extra={
                    "target_exposure_percentage": target_exposure,
                    "exposure_match_error_pp": best_distance,
                    "random_entry_probability": best_probability,
                    "random_probability_calibration_split": "validation",
                    "is_randomized_policy": best_probability < 1.0,
                },
            )
            comparison_rows.append(random_row)
            benchmark_summaries.append(
                {
                    "policy": "fixed_3day_exit_exposure_fit_diagnostic",
                    "split": split,
                    "ticker": ticker,
                    "target_exposure_percentage": target_exposure,
                    "random_entry_probability": best_probability,
                    "random_probability_calibration_split": "validation",
                    "is_randomized_policy": best_probability < 1.0,
                    "exposure_match_error_pp": best_distance,
                    **{field: best_random.get(field) for field in METRIC_FIELDS},
                }
            )
            _append_trade_rows(
                trade_rows,
                best_random,
                policy="fixed_3day_exit_exposure_fit_diagnostic",
                variant="benchmark",
                seed=random_seed,
                split=split,
                ticker_group=ticker_group[ticker],
            )

    for year in REGIME_YEARS:
        regime = regime_labels[year]["regime"]
        for ticker, stock in stocks.items():
            mask = _regime_eval_mask(stock, year)
            if mask.sum() < 30:
                continue
            for variant in ("market_only", "market_plus_s1_c16"):
                include_alpha = variant == "market_plus_s1_c16"
                for seed in SEEDS:
                    env = make_stock_env(stock, mask, env_cfg=env_cfg, include_alpha=include_alpha)
                    result = evaluate_chronological_policy(
                        models[(variant, seed)], env, seed=seed, deterministic=True
                    )
                    row = _metric_row(
                        result,
                        policy="MaskablePPO",
                        variant=variant,
                        seed=seed,
                        split=f"regime_{year}",
                        ticker=ticker,
                        ticker_group=ticker_group[ticker],
                        regime=regime,
                    )
                    regime_results.append(row)
                    comparison_rows.append(row)
                    _append_trade_rows(
                        trade_rows,
                        result,
                        policy="MaskablePPO",
                        variant=variant,
                        seed=seed,
                        split=f"regime_{year}",
                        ticker_group=ticker_group[ticker],
                        market_regime=regime,
                    )
                    env.close()

    mean_stock_rows = _mean_stock_summaries(stock_results)
    comparison_rows.extend(mean_stock_rows)
    macro_summary = {
        "interpretation": (
            "unweighted averages of independent stock backtests, not a portfolio return"
        ),
        "rows": mean_stock_rows,
    }
    input_stats_after = _stat_inputs(input_paths)
    if input_stats_before != input_stats_after:
        raise RuntimeError("A shared source file size/mtime changed during the experiment")

    total_runtime = time.perf_counter() - total_started
    metrics_payload = {
        "completed": True,
        "runtime_seconds": total_runtime,
        "training": train_summaries,
        "stock_level_results": stock_results,
        "regime_year_results": regime_results,
        "benchmarks": benchmark_summaries,
        "stock_level_macro_summary": macro_summary,
        "integrity": {
            "input_file_stats_unchanged": True,
            "max_observation_date_used": max(
                stock.dates.max() for stock in stocks.values()
            ).strftime("%Y-%m-%d"),
            "cutoff": str(DATA_CUTOFF.date()),
            "post_cutoff_rows_used_for_features_or_training": False,
            "causal_normalization_no_global_fit": True,
            "ticker_identity_in_observation": False,
            "all_tickers_sampled_each_training_seed": all(
                record["episodes_started"] > 0
                for training_result in train_summaries
                for record in training_result["sampled_tickers_and_starts"].values()
            ),
            "all_completed_holdings_at_least_3_intervals": True,
            "terminal_reward_changed": False,
            "gui_or_interactive_output": False,
        },
        "caveats": [
            "Alpha signal family selection used 2015-2025 research history; "
            "2023-2025 results are exploratory.",
            "Three held-out tickers test ticker generalization, not a fully untouched "
            "Alpha signal-selection period.",
            "BCG price history ends 2025-10-08; its exploratory test coverage is partial.",
            "S1/C16 publication-time fields are not present in the artifacts; existing "
            "after-close causal contract is assumed.",
            "Per-stock CAGRs are averaged only as diagnostics; no capital-allocation "
            "rule or portfolio is modeled.",
            "The fixed three-day baseline cannot match higher PPO exposure because its "
            "cycle limit is about 75%.",
        ],
    }
    (output_root / "phase4a_metrics.json").write_text(
        json.dumps(metrics_payload, indent=2, default=_json_default, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_csv(output_root / "phase4a_comparison.csv", comparison_rows)
    _write_csv(output_root / "phase4a_trades.csv", trade_rows)
    summary = {
        "completed": True,
        "runtime_seconds": total_runtime,
        "output_root": str(output_root),
        "training_runs": len(train_summaries),
        "stock_evaluations": len(stock_results),
        "regime_evaluations": len(regime_results),
        "trade_rows": len(trade_rows),
    }
    return {**metrics_payload, "terminal_summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--timesteps", type=int, default=TIMESTEPS_PER_MODEL)
    args = parser.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        result = run_experiment(output_root=args.output_root, timesteps=args.timesteps)
    print(json.dumps(result["terminal_summary"], separators=(",", ":")))


if __name__ == "__main__":
    main()
