from __future__ import annotations

import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.vec_env import DummyVecEnv

from vn_stock_rl.trade_episode.config import TradeEpisodeConfig, TradeEpisodePaths
from vn_stock_rl.trade_episode.data import load_daily_stock_bars, load_daily_tradability_flags
from vn_stock_rl.trade_episode.environment import TradeEpisodeEnv, annualized_log_excess_reward
from vn_stock_rl.trade_episode.evaluation import evaluate_chronological_policy
from vn_stock_rl.trade_episode.features import FeatureStandardizer
from vn_stock_rl.trade_episode.market_features import (
    MARKET_FEATURE_NAMES,
    build_causal_market_features,
    market_warmup_mask,
)
from vn_stock_rl.trade_episode.signals import ALPHA_FEATURE_NAMES, load_alpha_signals


@dataclass
class PreparedData:
    dates: pd.DatetimeIndex
    opens: np.ndarray
    closes: np.ndarray
    market_features: np.ndarray
    feature_names: list[str]
    can_buy: np.ndarray
    can_sell: np.ndarray
    split_masks: dict[str, np.ndarray]
    scaler: FeatureStandardizer
    metadata: dict[str, Any]


class GradientAuditMaskablePPO(MaskablePPO):
    """MaskablePPO with a post-update finite-gradient check for the smoke run."""

    def __init__(self, *args, **kwargs):
        self.gradient_audit: list[dict[str, bool | int]] = []
        super().__init__(*args, **kwargs)

    def train(self) -> None:
        super().train()
        gradients = [
            parameter.grad.detach()
            for parameter in self.policy.parameters()
            if parameter.grad is not None
        ]
        self.gradient_audit.append(
            {
                "gradient_tensor_count": len(gradients),
                "all_finite": all(bool(torch.isfinite(gradient).all()) for gradient in gradients),
                "any_nonzero": any(bool(torch.count_nonzero(gradient)) for gradient in gradients),
            }
        )


def read_experiment_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).expanduser().resolve()
    with config_path.open(encoding="utf-8") as stream:
        config = json.load(stream)
    required = {
        "name",
        "ticker",
        "include_alpha_signals",
        "data",
        "environment",
        "splits",
        "training",
    }
    missing = required.difference(config)
    if missing:
        raise ValueError(f"Experiment config is missing keys: {sorted(missing)}")
    if config["training"].get("algorithm", "MaskablePPO") != "MaskablePPO":
        raise ValueError("Trade-episode configs must use MaskablePPO")
    TradeEpisodeConfig(
        min_holding_intervals=int(config["environment"].get("min_holding_intervals", 3)),
        annualization_intervals=int(config["environment"].get("annualization_intervals", 252)),
        annual_benchmark=float(config["environment"].get("annual_benchmark", 0.07)),
        gamma=float(config["training"].get("gamma", 1.0)),
        max_episode_steps=int(config["environment"]["max_episode_steps"]),
        max_wait_steps=int(config["environment"]["max_wait_steps"]),
        max_holding_intervals=int(config["environment"]["max_holding_intervals"]),
    )
    return config


def _split_mask(dates: pd.DatetimeIndex, bounds: dict[str, str]) -> np.ndarray:
    start = pd.Timestamp(bounds["start"])
    end = pd.Timestamp(bounds["end"])
    if start > end:
        raise ValueError(f"Invalid split date range: {bounds}")
    return np.asarray((dates >= start) & (dates <= end), dtype=bool)


def prepare_experiment_data(
    config: dict[str, Any],
    *,
    data_root: str | Path,
    smoke: bool = False,
) -> PreparedData:
    """Load a bounded, read-only stock panel and fit preprocessing on train rows."""

    data_cfg = dict(config["data"])
    split_cfg = {name: dict(bounds) for name, bounds in config["splits"].items()}
    env_cfg = dict(config["environment"])
    if smoke:
        smoke_cfg = config.get("smoke", {})
        data_cfg["load_start_date"] = smoke_cfg["load_start_date"]
        data_cfg["data_cutoff"] = smoke_cfg["data_cutoff"]
        split_cfg = {name: dict(bounds) for name, bounds in smoke_cfg["splits"].items()}
        env_cfg.update(smoke_cfg.get("environment", {}))

    bars = load_daily_stock_bars(
        config["ticker"],
        data_root=data_root,
        start_date=data_cfg["load_start_date"],
        end_date=data_cfg["data_cutoff"],
    )
    dates = pd.DatetimeIndex(bars["time"].dt.normalize())
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("OHLCV dates must be unique and chronological")

    market = build_causal_market_features(bars)
    raw_parts = [market]
    feature_names = list(MARKET_FEATURE_NAMES)
    if bool(config["include_alpha_signals"]):
        alpha = load_alpha_signals(config["ticker"], dates, data_root=data_root)
        alpha.index = bars.index
        raw_parts.append(alpha)
        feature_names.extend(ALPHA_FEATURE_NAMES)
    raw_features = pd.concat(raw_parts, axis=1)

    warm = market_warmup_mask(market)
    configured_start = pd.Timestamp(data_cfg.get("feature_start_date", split_cfg["train"]["start"]))
    keep = warm & np.asarray(dates >= configured_start)
    if not keep.any():
        raise ValueError("No usable rows remain after warmup and feature_start_date")
    bars = bars.loc[keep].reset_index(drop=True)
    raw_features = raw_features.loc[keep].reset_index(drop=True)
    dates = pd.DatetimeIndex(bars["time"].dt.normalize())

    split_masks = {name: _split_mask(dates, bounds) for name, bounds in split_cfg.items()}
    if set(split_masks) != {"train", "validation", "test"}:
        raise ValueError("splits must define train, validation, and test")
    for name, mask in split_masks.items():
        if not mask.any():
            raise ValueError(f"{name} split has no rows in the loaded feature dates")
    if np.any(split_masks["train"] & split_masks["validation"]):
        raise ValueError("train and validation splits overlap")
    if np.any(split_masks["validation"] & split_masks["test"]):
        raise ValueError("validation and test splits overlap")
    if np.any(split_masks["train"] & split_masks["test"]):
        raise ValueError("train and test splits overlap")
    if not (
        dates[split_masks["train"]].max()
        < dates[split_masks["validation"]].min()
        < dates[split_masks["test"]].min()
    ):
        raise ValueError("splits must be chronological")

    scaler = FeatureStandardizer.fit(raw_features.loc[split_masks["train"]].to_numpy())
    normalized = scaler.transform(raw_features.to_numpy())
    can_buy, can_sell = load_daily_tradability_flags(
        config["ticker"], bars["time"], data_root=data_root
    )
    metadata = {
        "ticker": config["ticker"],
        "data_root": str(Path(data_root).expanduser().resolve()),
        "price_adjustment_basis": "user_assumed_dividend_adjusted",
        "data_cutoff": str(pd.Timestamp(data_cfg["data_cutoff"]).date()),
        "include_alpha_signals": bool(config["include_alpha_signals"]),
        "feature_names": feature_names,
        "split_dates": {
            name: {
                "start": str(dates[mask].min().date()),
                "end": str(dates[mask].max().date()),
                "rows": int(mask.sum()),
            }
            for name, mask in split_masks.items()
        },
        "train_only_feature_mean": scaler.mean.tolist(),
        "train_only_feature_scale": scaler.scale.tolist(),
        "training_fitted_normalization": True,
    }
    if bool(config["include_alpha_signals"]):
        for feature_name in ("alpha_s1_available", "alpha_c16_available"):
            column = raw_features[feature_name].to_numpy(dtype=np.float64)
            metadata[f"{feature_name}_coverage_pct"] = float(column.mean() * 100.0)
    return PreparedData(
        dates=dates,
        opens=bars["open"].to_numpy(dtype=np.float64),
        closes=bars["close"].to_numpy(dtype=np.float64),
        market_features=normalized,
        feature_names=feature_names,
        can_buy=can_buy.to_numpy(dtype=bool),
        can_sell=can_sell.to_numpy(dtype=bool),
        split_masks=split_masks,
        scaler=scaler,
        metadata=metadata,
    )


def _make_env(data: PreparedData, mask: np.ndarray, env_cfg: dict[str, Any], random_start: bool):
    selected = np.flatnonzero(mask)
    first, last = int(selected[0]), int(selected[-1])
    if selected.size != last - first + 1:
        raise ValueError("Each split must be one contiguous chronological interval")
    return TradeEpisodeEnv(
        data.opens[first : last + 1],
        data.closes[first : last + 1],
        price_basis="user_assumed_dividend_adjusted",
        market_features=data.market_features[first : last + 1],
        feature_names=data.feature_names,
        dates=data.dates[first : last + 1],
        can_buy_next_open=data.can_buy[first : last + 1],
        can_sell_next_open=data.can_sell[first : last + 1],
        min_holding_intervals=int(env_cfg.get("min_holding_intervals", 3)),
        max_episode_steps=int(env_cfg["max_episode_steps"]),
        max_wait_steps=int(env_cfg["max_wait_steps"]),
        max_holding_intervals=int(env_cfg["max_holding_intervals"]),
        annualization_intervals=int(env_cfg.get("annualization_intervals", 252)),
        annual_benchmark=float(env_cfg.get("annual_benchmark", 0.07)),
        ticker=str(data.metadata["ticker"]),
        random_start=random_start,
    )


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(1)


def _rollout_one_masked_episode(
    model: MaskablePPO,
    env: TradeEpisodeEnv,
    seed: int,
) -> dict[str, Any]:
    observation, _ = env.reset(seed=seed)
    total_reward = 0.0
    invalid_actions = 0
    steps = 0
    while True:
        mask = env.action_masks()
        action, _ = model.predict(observation, deterministic=True, action_masks=mask)
        action = int(np.asarray(action).reshape(-1)[0])
        if not bool(mask[action]):
            invalid_actions += 1
            raise RuntimeError("MaskablePPO selected an action excluded by the environment mask")
        observation, reward, terminated, truncated, info = env.step(action)
        total_reward += float(reward)
        steps += 1
        if terminated or truncated:
            return {
                "steps": steps,
                "episode_reward": total_reward,
                "invalid_actions": invalid_actions,
                "termination_reason": info["termination_reason"],
                "truncation_reason": info["truncation_reason"],
                "terminal_rl_reward": info["terminal_rl_reward"],
                "entry_date": info["entry_date"],
                "entry_price": info["entry_price"],
                "exit_date": info["exit_date"],
                "exit_price": info["exit_price"],
                "waiting_duration": info["waiting_duration"],
                "holding_duration": info["holding_duration"],
                "raw_trade_return": info["raw_trade_return"],
                "annualized_log_trade_return": info["annualized_log_trade_return"],
                "mark_to_market_portfolio_value": info["mark_to_market_portfolio_value"],
            }


def _historical_reward_probe(data: PreparedData, env_cfg: dict[str, Any]) -> dict[str, Any]:
    """Execute one deterministic legal three-interval trade on train-split bars."""

    train_rows = np.flatnonzero(data.split_masks["train"])
    first, last = int(train_rows[0]), int(train_rows[-1])
    train_slice = slice(first, last + 1)
    local_buy = data.can_buy[train_slice]
    local_sell = data.can_sell[train_slice]
    candidates = [
        index
        for index in range(max(0, len(local_buy) - 4))
        if local_buy[index] and local_sell[index + 3]
    ]
    if not candidates:
        raise RuntimeError(
            "No legal historical 3-interval buy/sell window is available for smoke probe"
        )
    env = _make_env(data, data.split_masks["train"], env_cfg, random_start=False)
    start_index = candidates[0]
    env.reset(options={"start_index": start_index})
    env.step(1)
    for _ in range(2):
        if env.action_masks()[0]:
            raise RuntimeError("SELL mask became valid before three holding intervals")
        env.step(1)
    if not env.action_masks()[0]:
        raise RuntimeError("SELL mask did not open at the three-interval boundary")
    _, reward, terminated, truncated, info = env.step(0)
    env.close()
    expected = annualized_log_excess_reward(
        float(info["entry_price"]),
        float(info["exit_price"]),
        int(info["holding_duration"]),
    )
    if not terminated or truncated or not np.isclose(reward, expected):
        raise RuntimeError("Historical terminal reward probe did not match the specified formula")
    return {
        "entry_date": info["entry_date"],
        "entry_price": info["entry_price"],
        "exit_date": info["exit_date"],
        "exit_price": info["exit_price"],
        "holding_duration": info["holding_duration"],
        "raw_trade_return": info["raw_trade_return"],
        "annualized_log_trade_return": info["annualized_log_trade_return"],
        "terminal_rl_reward": float(reward),
        "reward_formula_matches": True,
    }


def train_trade_episode(
    config_path: str | Path,
    *,
    data_root: str | Path,
    output_root: str | Path,
    smoke: bool = False,
) -> dict[str, Any]:
    """Train the isolated experiment; smoke mode is intentionally small and bounded."""

    config = read_experiment_config(config_path)
    seed = int(config["training"].get("seed", 1208))
    _seed_everything(seed)
    data = prepare_experiment_data(config, data_root=data_root, smoke=smoke)
    env_cfg = dict(config["environment"])
    trainer_cfg = dict(config["training"])
    if smoke:
        smoke_cfg = config.get("smoke", {})
        env_cfg.update(smoke_cfg.get("environment", {}))
        trainer_cfg.update(smoke_cfg.get("training", {}))
    reward_probe = _historical_reward_probe(data, env_cfg)

    paths = TradeEpisodePaths(root=Path(output_root))
    paths.ensure_created()
    run_name = f"{config['name']}_{'smoke' if smoke else 'training'}"
    model_dir = paths.models / run_name
    log_dir = paths.logs / run_name
    evaluation_dir = paths.evaluations / run_name
    for directory in (model_dir, log_dir, evaluation_dir):
        directory.mkdir(parents=True, exist_ok=False)
    config_copy = paths.configs / f"{run_name}.json"
    shutil.copyfile(Path(config_path).expanduser().resolve(), config_copy)

    train_env = DummyVecEnv(
        [lambda: _make_env(data, data.split_masks["train"], env_cfg, random_start=True)]
    )
    evaluation_env = DummyVecEnv(
        [lambda: _make_env(data, data.split_masks["validation"], env_cfg, random_start=False)]
    )
    total_timesteps = int(trainer_cfg["total_timesteps"])
    n_steps = int(trainer_cfg["n_steps"])
    batch_size = int(trainer_cfg["batch_size"])
    if n_steps <= 0 or batch_size <= 0 or batch_size > n_steps:
        raise ValueError("PPO batch_size must be positive and no larger than n_steps")
    if total_timesteps < n_steps:
        raise ValueError("total_timesteps must be at least one rollout (n_steps)")
    eval_freq = max(1, int(trainer_cfg.get("eval_freq", max(n_steps, total_timesteps // 2))))
    checkpoint_freq = max(
        1,
        int(trainer_cfg.get("checkpoint_freq", max(n_steps, total_timesteps // 2))),
    )
    checkpoint_callback = CheckpointCallback(
        save_freq=checkpoint_freq,
        save_path=str(model_dir / "checkpoints"),
        name_prefix=run_name,
        save_replay_buffer=False,
        save_vecnormalize=False,
    )
    (model_dir / "checkpoints").mkdir(parents=True, exist_ok=False)
    eval_callback = MaskableEvalCallback(
        evaluation_env,
        best_model_save_path=str(model_dir / "best"),
        log_path=str(evaluation_dir),
        eval_freq=eval_freq,
        n_eval_episodes=int(trainer_cfg.get("n_eval_episodes", 1)),
        deterministic=True,
        render=False,
        verbose=1,
    )
    (model_dir / "best").mkdir(parents=True, exist_ok=False)

    model = GradientAuditMaskablePPO(
        "MlpPolicy",
        train_env,
        gamma=1.0,
        learning_rate=float(trainer_cfg["learning_rate"]),
        n_steps=n_steps,
        batch_size=batch_size,
        n_epochs=int(trainer_cfg["n_epochs"]),
        gae_lambda=float(trainer_cfg["gae_lambda"]),
        ent_coef=float(trainer_cfg["ent_coef"]),
        seed=seed,
        policy_kwargs={"net_arch": [int(width) for width in trainer_cfg["net_arch"]]},
        tensorboard_log=str(log_dir),
        device="cpu",
        verbose=1,
    )
    before_parameters = [parameter.detach().clone() for parameter in model.policy.parameters()]
    model.learn(
        total_timesteps=total_timesteps,
        callback=[checkpoint_callback, eval_callback],
        progress_bar=False,
    )
    after_parameters = list(model.policy.parameters())
    if not model.gradient_audit:
        raise RuntimeError("No PPO optimization step ran; gradient audit is empty")
    if not all(
        row["all_finite"] and row["gradient_tensor_count"] > 0 for row in model.gradient_audit
    ):
        raise RuntimeError("PPO produced non-finite or missing gradients")
    parameters_finite = all(
        bool(torch.isfinite(parameter).all()) for parameter in model.policy.parameters()
    )
    if not parameters_finite:
        raise RuntimeError("PPO produced non-finite policy parameters")
    parameter_update_observed = any(
        not torch.equal(before, after.detach())
        for before, after in zip(before_parameters, after_parameters, strict=True)
    )
    if not parameter_update_observed:
        raise RuntimeError("PPO parameters did not change during the bounded run")

    model_path = model_dir / f"{run_name}_final"
    model.save(str(model_path))
    checkpoint_path = model_dir / "checkpoints" / f"{run_name}_{total_timesteps}_steps.zip"
    if not checkpoint_path.is_file():
        raise RuntimeError(f"Expected periodic checkpoint was not saved: {checkpoint_path}")
    reloaded = GradientAuditMaskablePPO.load(str(model_path), env=evaluation_env, device="cpu")

    # The callback evaluation and this reload check both use masks. The one-episode
    # rollout is diagnostic only and is not used as a profitability estimate.
    validation_env = _make_env(data, data.split_masks["validation"], env_cfg, random_start=False)
    reload_check = _rollout_one_masked_episode(reloaded, validation_env, seed + 1)
    validation_env.close()
    chronological_dev_test = None
    if not smoke:
        test_env = _make_env(data, data.split_masks["test"], env_cfg, random_start=False)
        chronological_dev_test = evaluate_chronological_policy(
            reloaded,
            test_env,
            seed=seed + 2,
            deterministic=True,
        )
        test_env.close()
    train_env.close()
    evaluation_env.close()

    result = {
        "run_name": run_name,
        "algorithm": "MaskablePPO",
        "gamma": 1.0,
        "seed": seed,
        "smoke_test": smoke,
        "total_timesteps": total_timesteps,
        "train_only_normalization": True,
        "maskable_eval_callback": True,
        "mask_aware_reload_rollout": reload_check,
        "chronological_development_test_performance": chronological_dev_test,
        "historical_terminal_reward_probe": reward_probe,
        "gradient_audit": model.gradient_audit,
        "policy_parameters_finite": parameters_finite,
        "parameter_update_observed": parameter_update_observed,
        "terminal_reward_clipped_or_normalized": False,
        "model_path": str(model_path.with_suffix(".zip")),
        "checkpoint_path": str(checkpoint_path),
        "output_root": str(paths.root),
        "data": data.metadata,
        "note": "Technical smoke diagnostics only; no profitability inference.",
    }
    with (evaluation_dir / "training_summary.json").open("w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, default=str)
        stream.write("\n")
    return result
