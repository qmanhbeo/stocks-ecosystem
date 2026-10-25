"""Run the bounded, headless Phase 3 paired feature ablation."""

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
for _thread_var in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_var] = "1"

PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_DIR / "configs" / "trade_episode"
DEFAULT_OUTPUT = Path("/tmp/stock-rl-trade-episode-phase3-20261025")
SEEDS = (1208, 1209, 1210)
DEFAULT_TIMESTEPS = 5120
DATA_CUTOFF = "2025-12-31"


class RandomValidActionPolicy:
    """Uniform random action selection over the environment's legal mask."""

    def __init__(self, seed: int) -> None:
        import numpy as np

        self.rng = np.random.default_rng(seed)

    def predict(self, observation, *, action_masks, deterministic=True, **kwargs):
        import numpy as np

        mask = np.asarray(action_masks, dtype=bool)
        valid = np.flatnonzero(mask)
        if valid.size == 0:
            raise RuntimeError("Environment provided an empty action mask")
        return np.asarray([self.rng.choice(valid)], dtype=np.int64), None


class ImmediateBuyMinimumHoldPolicy:
    """Buy as soon as allowed, then SELL at the first legal opportunity."""

    def predict(self, observation, *, action_masks, deterministic=True, **kwargs):
        import numpy as np

        mask = np.asarray(action_masks, dtype=bool)
        in_position = bool(float(np.asarray(observation).reshape(-1)[-5]) >= 0.5)
        if in_position:
            action = 0 if mask[0] else 1
        else:
            action = 1 if mask[1] else 0
        if not mask[action]:
            raise RuntimeError("Deterministic benchmark selected an invalid action")
        return np.asarray([action], dtype=np.int64), None


def _json_default(value: Any):
    import numpy as np

    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot JSON encode {type(value).__name__}")


def _stat_inputs(data_root: Path) -> dict[str, dict[str, int]]:
    from vn_stock_rl.trade_episode.data import stock_bars_path
    from vn_stock_rl.trade_episode.signals import C16_ARTIFACT, S1_ARTIFACT

    paths = {
        "ohlcv": stock_bars_path("FPT", data_root=data_root),
        "tradability": data_root / "features" / "execution" / "tradability_daily.parquet",
        "s1": data_root / S1_ARTIFACT,
        "c16": data_root / C16_ARTIFACT,
    }
    result = {}
    for name, path in paths.items():
        info = path.stat()
        result[name] = {"size_bytes": int(info.st_size), "mtime_ns": int(info.st_mtime_ns)}
    return result


def _assert_matched_inputs(baseline, alpha) -> None:
    import numpy as np

    for name in ("dates", "opens", "closes", "can_buy", "can_sell"):
        left, right = getattr(baseline, name), getattr(alpha, name)
        if not np.array_equal(left, right):
            raise RuntimeError(f"Baseline and Alpha data differ in {name}")
    for name in ("train", "validation", "test"):
        if not np.array_equal(baseline.split_masks[name], alpha.split_masks[name]):
            raise RuntimeError(f"Baseline and Alpha {name} masks are not identical")
    if baseline.metadata["split_dates"] != alpha.metadata["split_dates"]:
        raise RuntimeError("Baseline and Alpha split dates differ")
    if baseline.dates.max() > __import__("pandas").Timestamp(DATA_CUTOFF):
        raise RuntimeError("Loaded dates extend beyond the authorized 2025 cutoff")


def _train_one(
    data,
    env_cfg: dict[str, Any],
    seed: int,
    total_timesteps: int,
    model_path: Path,
) -> tuple[Any, dict[str, Any]]:
    import torch
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    from vn_stock_rl.trade_episode.training import (
        GradientAuditMaskablePPO,
        _make_env,
        _seed_everything,
    )

    training = {
        "algorithm": "MaskablePPO",
        "gamma": 1.0,
        "learning_rate": 3e-4,
        "n_steps": 256,
        "batch_size": 64,
        "n_epochs": 5,
        "gae_lambda": 0.95,
        "ent_coef": 0.01,
        "net_arch": [64, 64],
        "total_timesteps": total_timesteps,
        "seed": seed,
        "device": "cpu",
        "workers": 1,
        "tensorboard": False,
        "progress_bar": False,
    }
    _seed_everything(seed)
    torch.set_num_threads(1)
    train_env = DummyVecEnv(
        [lambda: _make_env(data, data.split_masks["train"], env_cfg, random_start=True)]
    )
    model = GradientAuditMaskablePPO(
        "MlpPolicy",
        train_env,
        gamma=training["gamma"],
        learning_rate=training["learning_rate"],
        n_steps=training["n_steps"],
        batch_size=training["batch_size"],
        n_epochs=training["n_epochs"],
        gae_lambda=training["gae_lambda"],
        ent_coef=training["ent_coef"],
        seed=seed,
        policy_kwargs={"net_arch": training["net_arch"]},
        device="cpu",
        verbose=0,
    )
    initial_parameters = [parameter.detach().clone() for parameter in model.policy.parameters()]
    start = time.perf_counter()
    model.learn(total_timesteps=total_timesteps, progress_bar=False)
    elapsed = time.perf_counter() - start
    audits = model.gradient_audit
    if model.num_timesteps != total_timesteps:
        raise RuntimeError(f"Expected {total_timesteps} steps, got {model.num_timesteps}")
    if not audits or not all(row["all_finite"] for row in audits):
        raise RuntimeError("PPO gradient audit found missing or non-finite gradients")
    if not any(row["any_nonzero"] for row in audits):
        raise RuntimeError("PPO gradient audit found no non-zero gradient update")
    parameters_finite = all(
        bool(torch.isfinite(parameter).all()) for parameter in model.policy.parameters()
    )
    changed = any(
        not torch.equal(before, after.detach())
        for before, after in zip(initial_parameters, model.policy.parameters(), strict=True)
    )
    if not parameters_finite or not changed:
        raise RuntimeError("PPO parameters are non-finite or did not update")

    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_path.with_suffix("")))
    zip_path = model_path.with_suffix(".zip")
    if not zip_path.is_file():
        raise RuntimeError(f"Final checkpoint was not created: {zip_path}")
    reloaded = MaskablePPO.load(str(zip_path), device="cpu")
    audit = {
        **training,
        "actual_timesteps": int(model.num_timesteps),
        "runtime_seconds": elapsed,
        "steps_per_second": float(model.num_timesteps / elapsed),
        "gradient_update_count": len(audits),
        "all_gradients_finite": bool(all(row["all_finite"] for row in audits)),
        "any_nonzero_gradient": bool(any(row["any_nonzero"] for row in audits)),
        "parameters_finite": bool(parameters_finite),
        "parameters_updated": bool(changed),
        "checkpoint_path": str(zip_path),
        "checkpoint_bytes": int(zip_path.stat().st_size),
    }
    train_env.close()
    del model
    return reloaded, audit


def _buy_hold_metrics(env) -> dict[str, Any]:
    import numpy as np

    intervals = env.n_rows - 1
    base = float(env.open_prices[1])
    curve = np.ones(env.n_rows, dtype=np.float64)
    curve[1:] = env.close_prices[1:] / base
    drawdown = curve / np.maximum.accumulate(curve) - 1.0
    total_return = float(curve[-1] - 1.0)
    return {
        "chronological_portfolio_cagr": float(curve[-1] ** (252.0 / intervals) - 1.0),
        "maximum_drawdown": float(drawdown.min()),
        "exposure_percentage": float((env.n_rows - 1) / env.n_rows * 100.0),
        "number_of_trades": 0,
        "average_waiting_duration": None,
        "median_waiting_duration": None,
        "average_holding_duration": None,
        "median_holding_duration": None,
        "win_rate": None,
        "mean_terminal_rl_reward": None,
        "median_terminal_rl_reward": None,
        "total_calendar_return": total_return,
        "final_portfolio_value": float(curve[-1]),
        "no_trade_episode_count": 0,
        "no_trade_episode_frequency": None,
        "truncated_episode_count": 0,
        "truncated_episode_frequency": None,
        "incomplete_episode_count": 0,
        "evaluated_trading_intervals": intervals,
        "benchmark_definition": "Buy at first next-day open; mark to close through period end",
    }


def _benchmark_row(name: str, split: str, metrics: dict[str, Any], seed=None) -> dict[str, Any]:
    return {
        "row_type": "benchmark",
        "variant": "benchmark",
        "policy": name,
        "split": split,
        "seed": seed,
        "aggregation": None,
        **_comparison_metrics(metrics),
    }


COMPARISON_METRICS = (
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


def _comparison_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {name: metrics.get(name) for name in COMPARISON_METRICS}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_experiment(output_root: Path, total_timesteps: int = DEFAULT_TIMESTEPS) -> dict[str, Any]:
    output_root = output_root.expanduser().resolve()
    if output_root.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {output_root}")
    if total_timesteps < 256 or total_timesteps % 256:
        raise ValueError("total_timesteps must be a positive multiple of the 256-step PPO rollout")

    data_root_raw = os.environ.get("STOCKS_DATA_ROOT")
    if not data_root_raw:
        raise RuntimeError("STOCKS_DATA_ROOT must point to the existing shared data root")
    data_root = Path(data_root_raw).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    (output_root / "models").mkdir()
    cache_root = output_root / "cache" / "matplotlib"
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(cache_root)
    import matplotlib

    matplotlib.use("Agg", force=True)
    matplotlib.interactive(False)

    import numpy as np
    import torch

    from vn_stock_rl.trade_episode.evaluation import evaluate_chronological_policy
    from vn_stock_rl.trade_episode.training import (
        _make_env,
        prepare_experiment_data,
        read_experiment_config,
    )

    torch.set_num_threads(1)

    input_before = _stat_inputs(data_root)
    config_paths = {
        "baseline": CONFIG_DIR / "baseline_market.json",
        "alpha": CONFIG_DIR / "market_plus_alpha.json",
    }
    configs = {name: read_experiment_config(path) for name, path in config_paths.items()}
    for config in configs.values():
        if config["data"]["data_cutoff"] != DATA_CUTOFF:
            raise RuntimeError(
                "Experiment config cutoff differs from the authorized 2025-12-31 cap"
            )
        if config["training"].get("gamma") != 1.0:
            raise RuntimeError("Experiment gamma must remain 1.0")

    prepared = {
        name: prepare_experiment_data(configs[name], data_root=data_root)
        for name in ("baseline", "alpha")
    }
    _assert_matched_inputs(prepared["baseline"], prepared["alpha"])
    if prepared["baseline"].metadata["split_dates"]["test"]["end"] > DATA_CUTOFF:
        raise RuntimeError("Exploratory evaluation contains dates past 2025")

    (output_root / "phase3_config.json").write_text(
        json.dumps(
            {
                "experiment": "stock_rl_trade_episode_phase3",
                "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "headless": True,
                "MPLBACKEND": os.environ["MPLBACKEND"],
                "interactive_plotting": False,
                "device": "cpu",
                "workers": 1,
                "data_root": str(data_root),
                "shared_data_read_only": True,
                "data_cutoff": DATA_CUTOFF,
                "price_basis": "user_assumed_dividend_adjusted",
                "seeds": list(SEEDS),
                "timesteps_per_model": total_timesteps,
                "training_config": {
                    "algorithm": "MaskablePPO",
                    "gamma": 1.0,
                    "learning_rate": 3e-4,
                    "n_steps": 256,
                    "batch_size": 64,
                    "n_epochs": 5,
                    "gae_lambda": 0.95,
                    "ent_coef": 0.01,
                    "net_arch": [64, 64],
                },
                "source_configs": {name: str(path) for name, path in config_paths.items()},
                "data": {name: prepared[name].metadata for name in prepared},
                "feature_conditions": {name: prepared[name].feature_names for name in prepared},
                "data_file_stats_before": input_before,
                "data_access_note": (
                    "All rows returned to feature and model code are filtered at 2025-12-31. "
                    "The FPT OHLCV file uses one Parquet row group spanning into 2026; the "
                    "reader may physically decode row-group pages before date filtering."
                ),
                "validation_is_diagnostic_only": True,
                "2023_2025_is_exploratory": True,
                "2026_rows_returned_to_features_or_evaluation": False,
                "reward": "252/T * ln(Psell/Pbuy) - ln(1.07)",
                "action_semantics": {"0": "OUT", "1": "IN"},
                "minimum_holding_intervals": 3,
                "execution": (
                    "observe through close t; execute target action at next available open"
                ),
            },
            indent=2,
            default=_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    env_cfg = dict(configs["baseline"]["environment"])
    training_summaries: list[dict[str, Any]] = []
    trained_models: dict[tuple[str, int], Any] = {}
    total_start = time.perf_counter()
    for variant in ("baseline", "alpha"):
        for seed in SEEDS:
            model_path = output_root / "models" / f"{variant}_seed{seed}"
            model, summary = _train_one(
                prepared[variant], env_cfg, seed, total_timesteps, model_path
            )
            summary["variant"] = variant
            training_summaries.append(summary)
            trained_models[(variant, seed)] = model

    evaluation_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    split_summaries: dict[str, dict[str, Any]] = {}
    for split in ("validation", "test"):
        split_summaries[split] = {}
        reference_env = _make_env(
            prepared["baseline"],
            prepared["baseline"].split_masks[split],
            env_cfg,
            random_start=False,
        )
        split_summaries[split]["date_range"] = {
            "start": str(reference_env.dates[0]),
            "end": str(reference_env.dates[-1]),
            "rows": reference_env.n_rows,
        }
        buy_hold = _buy_hold_metrics(reference_env)
        annual_curve = (1.07) ** (np.arange(reference_env.n_rows, dtype=np.float64) / 252.0)
        annual_benchmark = {
            **buy_hold,
            "chronological_portfolio_cagr": 0.07,
            "maximum_drawdown": 0.0,
            "exposure_percentage": 0.0,
            "total_calendar_return": float(annual_curve[-1] - 1.0),
            "final_portfolio_value": float(annual_curve[-1]),
            "benchmark_definition": "Cash compounded at the annual 7% benchmark",
        }
        buy_hold_row = _benchmark_row("buy_and_hold", split, buy_hold)
        hurdle_row = _benchmark_row("7_percent_annual_benchmark", split, annual_benchmark)
        benchmark_rows.extend((buy_hold_row, hurdle_row))
        comparison_rows.extend((buy_hold_row, hurdle_row))

        immediate_env = _make_env(
            prepared["baseline"],
            prepared["baseline"].split_masks[split],
            env_cfg,
            random_start=False,
        )
        immediate = evaluate_chronological_policy(
            ImmediateBuyMinimumHoldPolicy(), immediate_env, seed=SEEDS[0], deterministic=True
        )
        for episode in immediate["episodes"]:
            evaluation_rows.append(
                {
                    "variant": "benchmark",
                    "policy": "immediate_buy_min_hold",
                    "seed": SEEDS[0],
                    "split": split,
                    **episode,
                }
            )
        comparison_rows.append(_benchmark_row("immediate_buy_min_hold", split, immediate, SEEDS[0]))
        immediate_env.close()
        reference_env.close()

        model_metrics_by_variant: dict[str, dict[int, dict[str, Any]]] = {
            "baseline": {},
            "alpha": {},
        }
        for variant in ("baseline", "alpha"):
            for seed in SEEDS:
                eval_data = prepared[variant]
                eval_env = _make_env(
                    eval_data, eval_data.split_masks[split], env_cfg, random_start=False
                )
                result = evaluate_chronological_policy(
                    trained_models[(variant, seed)], eval_env, seed=seed, deterministic=True
                )
                model_metrics_by_variant[variant][seed] = result
                for episode in result["episodes"]:
                    evaluation_rows.append(
                        {
                            "variant": variant,
                            "policy": "MaskablePPO",
                            "seed": seed,
                            "split": split,
                            **episode,
                        }
                    )
                comparison_rows.append(
                    {
                        "row_type": "agent_seed",
                        "variant": variant,
                        "policy": "MaskablePPO",
                        "split": split,
                        "seed": seed,
                        "aggregation": None,
                        **_comparison_metrics(result),
                    }
                )
                eval_env.close()

        random_results: list[dict[str, Any]] = []
        for seed in SEEDS:
            random_env = _make_env(
                prepared["baseline"],
                prepared["baseline"].split_masks[split],
                env_cfg,
                random_start=False,
            )
            random_result = evaluate_chronological_policy(
                RandomValidActionPolicy(seed), random_env, seed=seed, deterministic=True
            )
            random_results.append(random_result)
            for episode in random_result["episodes"]:
                evaluation_rows.append(
                    {
                        "variant": "benchmark",
                        "policy": "random_valid_action",
                        "seed": seed,
                        "split": split,
                        **episode,
                    }
                )
            comparison_rows.append(
                _benchmark_row("random_valid_action", split, random_result, seed)
            )
            random_env.close()

        for variant in ("baseline", "alpha"):
            split_summaries[split][variant] = {}
            for metric in COMPARISON_METRICS:
                values = [model_metrics_by_variant[variant][seed].get(metric) for seed in SEEDS]
                numeric = [
                    float(value)
                    for value in values
                    if value is not None and np.isfinite(float(value))
                ]
                split_summaries[split][variant][metric] = {
                    "mean": None if not numeric else float(np.mean(numeric)),
                    "median": None if not numeric else float(np.median(numeric)),
                    "per_seed": dict(zip((str(seed) for seed in SEEDS), values, strict=True)),
                }
            split_summaries[split][variant]["policy_behavior_diagnostics"] = {
                str(seed): {
                    "action_counts": model_metrics_by_variant[variant][seed]["action_counts"],
                    "never_bought": model_metrics_by_variant[variant][seed]["action_counts"]["BUY"]
                    == 0,
                    "first_action_buy_frequency": model_metrics_by_variant[variant][seed][
                        "first_action_buy_frequency"
                    ],
                    "immediate_buy_trade_frequency": model_metrics_by_variant[variant][seed][
                        "immediate_buy_trade_frequency"
                    ],
                    "minimum_hold_exit_frequency": model_metrics_by_variant[variant][seed][
                        "minimum_hold_exit_frequency"
                    ],
                    "trades_below_three": model_metrics_by_variant[variant][seed][
                        "number_of_trades"
                    ]
                    < 3,
                    "open_position_truncated_episode_count": model_metrics_by_variant[variant][
                        seed
                    ]["open_position_truncated_episode_count"],
                    "no_trade_episode_count": model_metrics_by_variant[variant][seed][
                        "no_trade_episode_count"
                    ],
                    "truncated_episode_count": model_metrics_by_variant[variant][seed][
                        "truncated_episode_count"
                    ],
                    "mean_terminal_rl_reward": model_metrics_by_variant[variant][seed][
                        "mean_terminal_rl_reward"
                    ],
                    "chronological_portfolio_cagr": model_metrics_by_variant[variant][seed][
                        "chronological_portfolio_cagr"
                    ],
                }
                for seed in SEEDS
            }
            for aggregation in ("mean", "median"):
                row = {
                    "row_type": "agent_aggregate",
                    "variant": variant,
                    "policy": "MaskablePPO",
                    "split": split,
                    "seed": None,
                    "aggregation": aggregation,
                }
                for metric in COMPARISON_METRICS:
                    row[metric] = split_summaries[split][variant][metric][aggregation]
                comparison_rows.append(row)

        for seed in SEEDS:
            baseline_result = model_metrics_by_variant["baseline"][seed]
            alpha_result = model_metrics_by_variant["alpha"][seed]
            row = {
                "row_type": "paired_seed_delta",
                "variant": "alpha_minus_baseline",
                "policy": "MaskablePPO",
                "split": split,
                "seed": seed,
                "aggregation": None,
            }
            for metric in COMPARISON_METRICS:
                base_value, alpha_value = baseline_result.get(metric), alpha_result.get(metric)
                row[metric] = (
                    None
                    if base_value is None or alpha_value is None
                    else float(alpha_value) - float(base_value)
                )
            comparison_rows.append(row)
        mean_delta = {
            metric: split_summaries[split]["alpha"][metric]["mean"]
            - split_summaries[split]["baseline"][metric]["mean"]
            if split_summaries[split]["alpha"][metric]["mean"] is not None
            and split_summaries[split]["baseline"][metric]["mean"] is not None
            else None
            for metric in COMPARISON_METRICS
        }
        comparison_rows.append(
            {
                "row_type": "paired_mean_delta",
                "variant": "alpha_minus_baseline",
                "policy": "MaskablePPO",
                "split": split,
                "seed": None,
                "aggregation": "mean",
                **mean_delta,
            }
        )

    for summary in training_summaries:
        trained_models.pop((summary["variant"], summary["seed"]), None)
    input_after = _stat_inputs(data_root)
    if input_before != input_after:
        raise RuntimeError(
            "A shared input data file's size or modification time changed during the run"
        )

    metrics_payload = {
        "completed": True,
        "total_runtime_seconds": time.perf_counter() - total_start,
        "training": training_summaries,
        "evaluation": split_summaries,
        "benchmarks": benchmark_rows,
        "data_file_stats_after": input_after,
        "integrity": {
            "baseline_alpha_dates_prices_and_tradability_identical": True,
            "all_loaded_dates_on_or_before_2025_12_31": True,
            "shared_input_size_and_mtime_unchanged": True,
            "invalid_masked_actions": 0,
            "terminal_reward_formula_changed": False,
            "plots_or_gui_opened": False,
            "training_runs": len(training_summaries),
            "evaluation_policy_episodes_logged": len(evaluation_rows),
        },
        "limitations": [
            "Single ticker FPT only; results are an engineering experiment, not broad evidence.",
            "2023-2025 is exploratory and contaminated by Alpha signal-family selection history.",
            (
                "The FPT OHLCV Parquet row group spans 2026; date filtering excludes 2026 rows "
                "from returned/model data but may physically decode pages first."
            ),
            (
                "Annualized per-trade reward and chronological portfolio returns are reported "
                "separately."
            ),
        ],
    }
    (output_root / "phase3_metrics.json").write_text(
        json.dumps(metrics_payload, indent=2, default=_json_default, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_csv(output_root / "phase3_trades.csv", evaluation_rows)
    _write_csv(output_root / "phase3_comparison.csv", comparison_rows)
    return metrics_payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timesteps", type=int, default=DEFAULT_TIMESTEPS)
    args = parser.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        result = run_experiment(args.output_root, args.timesteps)
    print(
        json.dumps(
            {
                "completed": result["completed"],
                "runtime_seconds": round(result["total_runtime_seconds"], 2),
                "output_root": str(args.output_root.resolve()),
                "model_runs": len(result["training"]),
                "evaluation_episodes_logged": result["integrity"][
                    "evaluation_policy_episodes_logged"
                ],
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
