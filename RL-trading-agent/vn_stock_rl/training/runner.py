from __future__ import annotations

import json
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import random
import shutil
from collections import deque
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import torch as th
from sb3_contrib import RecurrentPPO
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback, EvalCallback
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from vn_stock_rl.config import POLICY_CONFIGS, TRAIN_DEFAULTS
from vn_stock_rl.config.cli_shared import (
    parse_engineered_feature_families,
    parse_helper_window_list,
    parse_news_feature_columns,
    parse_reward_benchmark,
    parse_rs_market_proxies,
    parse_signal_feature_columns,
    parse_window_list,
)
from vn_stock_rl.policies.extractors.cnn_attention_extractor import (
    CNNAttentionExtractor,
    CNNAttentionExtractorForLSTM,
)
from vn_stock_rl.policies.extractors.cnn_extractor import StockClassicCNNExtractor, StockMultiCNNExtractor
from vn_stock_rl.policies.extractors.cnn_lstm_extractor import (
    StockClassicCNNExtractorForLSTM,
    StockMultiCNNExtractorForLSTM,
)
from vn_stock_rl.policies.extractors.cnn_window_attention_extractor import (
    CNNWindowAttentionExtractor,
    CNNWindowAttentionExtractorForLSTM,
)
from vn_stock_rl.policies.extractors.transformer_extractor import (
    StockTransformerExtractor,
    StockTransformerExtractorForLSTM,
)
from vn_stock_rl.policies.registry import normalize_policy, policy_display_name
from vn_stock_rl.training.env_builder import build_training_env
from vn_stock_rl.training.metadata import (
    _auto_model_name,
    _get_env_attr,
    _get_git_commit_info,
    _to_jsonable,
)
from vn_stock_rl.training.reporting import (
    print_training_complete,
    print_training_start,
)
from vn_stock_rl.external_features import default_signal_prediction_dir

ENGINEERED_FEATURE_FAMILIES = (
    "volatility",
    "trend",
    "momentum",
    "volume_context",
    "drawdown",
    "relative_strength",
)

_normalize_policy = normalize_policy
_policy_display_name = policy_display_name
_parse_window_list = parse_window_list
_parse_helper_window_list = parse_helper_window_list
_parse_engineered_feature_families = parse_engineered_feature_families
_parse_rs_market_proxies = parse_rs_market_proxies
_parse_news_feature_columns = parse_news_feature_columns
_parse_signal_feature_columns = parse_signal_feature_columns
_parse_reward_benchmark = parse_reward_benchmark

def _append_with_running_sum(window: deque, running_sum: float, value: float):
    if len(window) == window.maxlen:
        running_sum -= float(window[0])
    window.append(float(value))
    running_sum += float(value)
    return running_sum, (running_sum / float(len(window)))

def _build_env(
    mode: str,
    stock: str,
    stocks: list,
    all_stocks: bool,
    data_dir: str,
    drawdown_penalty_enabled: Optional[bool],
    drawdown_penalty_lambda: Optional[float],
    drawdown_penalty_train_only: Optional[bool],
    reward_benchmark: Optional[str],
    benchmark_weight: Optional[float],
    benchmark_relative_reward: Optional[bool],
    train_episode_sampling_enabled: Optional[bool],
    train_episode_min_fraction: Optional[float],
    train_episode_max_fraction: Optional[float],
    start_date: Optional[str],
    end_date: Optional[str],
    source_mode: Optional[str],
    ma_windows: list,
    helpers_ma_windows: list,
    returns_windows: list,
    helpers_returns_windows: list,
    engineered_features: Optional[list],
    window_policy: Optional[str],
    feature_windows: Optional[list],
    logspace_min: Optional[int],
    logspace_max: Optional[int],
    logspace_count: Optional[int],
    rs_market_proxies: Optional[list],
    rs_include_long: Optional[bool],
    calendar_features: Optional[list],
    news_feature_columns: Optional[list],
    news_prediction_dir: Optional[str],
    signal_feature_columns: Optional[list],
    signal_prediction_dir: Optional[str],
    help_tickers: list,
    market_data_dir: str,
    help_assets: list,
    help_assets_dir: str,
    monitor_path_or_none: Optional[str] = None,
):
    return build_training_env(
        mode=mode,
        stock=stock,
        stocks=stocks,
        all_stocks=all_stocks,
        data_dir=data_dir,
        drawdown_penalty_enabled=drawdown_penalty_enabled,
        drawdown_penalty_lambda=drawdown_penalty_lambda,
        drawdown_penalty_train_only=drawdown_penalty_train_only,
        reward_benchmark=reward_benchmark,
        benchmark_weight=benchmark_weight,
        benchmark_relative_reward=benchmark_relative_reward,
        train_episode_sampling_enabled=train_episode_sampling_enabled,
        train_episode_min_fraction=train_episode_min_fraction,
        train_episode_max_fraction=train_episode_max_fraction,
        start_date=start_date,
        end_date=end_date,
        source_mode=source_mode,
        ma_windows=ma_windows,
        helpers_ma_windows=helpers_ma_windows,
        returns_windows=returns_windows,
        helpers_returns_windows=helpers_returns_windows,
        engineered_features=engineered_features,
        window_policy=window_policy,
        feature_windows=feature_windows,
        logspace_min=logspace_min,
        logspace_max=logspace_max,
        logspace_count=logspace_count,
        rs_market_proxies=rs_market_proxies,
        rs_include_long=rs_include_long,
        calendar_features=calendar_features,
        news_feature_columns=news_feature_columns,
        news_prediction_dir=news_prediction_dir,
        signal_feature_columns=signal_feature_columns,
        signal_prediction_dir=signal_prediction_dir,
        help_tickers=help_tickers,
        market_data_dir=market_data_dir,
        help_assets=help_assets,
        help_assets_dir=help_assets_dir,
        monitor_path_or_none=monitor_path_or_none,
    )

class EntropyScheduleCallback(BaseCallback):
    """Update model.ent_coef on a schedule during training."""

    def __init__(self, schedule_fn):
        super().__init__()
        self.schedule_fn = schedule_fn

    def _on_rollout_start(self) -> bool:
        if self.schedule_fn is None:
            return True
        # SB3 keeps _current_progress_remaining updated in learn().
        progress_remaining = getattr(self.model, "_current_progress_remaining", None)
        if progress_remaining is None:
            # Fallback if attribute isn't available yet.
            progress_remaining = 1.0 - (self.num_timesteps / self.model._total_timesteps)
        self.model.ent_coef = float(self.schedule_fn(progress_remaining))
        return True

    def _on_step(self) -> bool:
        # Required by BaseCallback; updates happen on rollouts.
        return True

class TrainingEpisodeStatsCallback(BaseCallback):
    """Log realized training episode return from env info (not just reward)."""

    def __init__(self, window_size: int = 100):
        super().__init__()
        self.window_size = int(window_size)
        self.return_window = deque(maxlen=self.window_size)
        self.reward_window = deque(maxlen=self.window_size)
        self.return_sum = 0.0
        self.reward_sum = 0.0

    def _on_step(self) -> bool:
        infos = self.locals.get("infos")
        dones = self.locals.get("dones")
        if infos is None or dones is None:
            return True

        for done, info in zip(dones, infos):
            if not done or not isinstance(info, dict):
                continue

            equity = info.get("equity")
            if equity is not None:
                episode_return = float(equity) - 1.0
                self.return_sum, return_mean = _append_with_running_sum(
                    self.return_window,
                    self.return_sum,
                    episode_return,
                )
                self.logger.record("train_episode/return_last", episode_return)
                self.logger.record("train_episode/return_mean_100", float(return_mean))

            cumulative_reward = info.get("cumulative_return")
            if cumulative_reward is not None:
                cumulative_reward = float(cumulative_reward)
                self.reward_sum, reward_mean = _append_with_running_sum(
                    self.reward_window,
                    self.reward_sum,
                    cumulative_reward,
                )
                self.logger.record("train_episode/cumulative_reward_last", cumulative_reward)
                self.logger.record("train_episode/cumulative_reward_mean_100", float(reward_mean))

        return True

class ValidationReturnCallback(BaseCallback):
    """Periodically evaluate and log realized validation return (equity - 1)."""

    def __init__(
        self,
        eval_env,
        eval_freq: int,
        n_eval_episodes: int,
        deterministic: bool = True,
        window_size: int = 20,
        best_model_save_path: str = None,
    ):
        super().__init__()
        self.eval_env = eval_env
        self.eval_freq = max(int(eval_freq), 1)
        self.n_eval_episodes = max(int(n_eval_episodes), 1)
        self.deterministic = bool(deterministic)
        self.return_window = deque(maxlen=max(int(window_size), 1))
        self.return_window_sum = 0.0
        self.best_model_save_path = best_model_save_path
        self.best_mean_return = -np.inf
        if self.best_model_save_path:
            os.makedirs(self.best_model_save_path, exist_ok=True)

    @staticmethod
    def _extract_episode_return(info: dict):
        if not isinstance(info, dict):
            return None
        if info.get("equity") is not None:
            return float(info["equity"]) - 1.0
        if info.get("cumulative_return") is not None:
            # Fallback: cumulative sum of step rewards.
            return float(info["cumulative_return"])
        return None

    def _evaluate_val_returns(self):
        obs = self.eval_env.reset()
        state = None
        episode_starts = np.ones((self.eval_env.num_envs,), dtype=bool)
        returns = []

        while len(returns) < self.n_eval_episodes:
            action, state = self.model.predict(
                obs,
                state=state,
                episode_start=episode_starts,
                deterministic=self.deterministic,
            )
            obs, _, dones, infos = self.eval_env.step(action)

            for done, info in zip(dones, infos):
                if not done:
                    continue
                ret = self._extract_episode_return(info)
                returns.append(np.nan if ret is None else float(ret))
                if len(returns) >= self.n_eval_episodes:
                    break

            episode_starts = dones

        returns_array = np.asarray(returns, dtype=np.float64)
        valid = returns_array[~np.isnan(returns_array)]
        if valid.size == 0:
            return None, None, 0
        return float(valid.mean()), float(valid.std()), int(valid.size)

    def _append_return(self, value: float) -> float:
        self.return_window_sum, rolling_mean = _append_with_running_sum(
            self.return_window,
            self.return_window_sum,
            value,
        )
        return float(rolling_mean)

    def _on_step(self) -> bool:
        if self.n_calls % self.eval_freq != 0:
            return True

        mean_return, std_return, n_valid = self._evaluate_val_returns()
        self.logger.record("eval/return_episodes", int(n_valid))
        if mean_return is None:
            return True

        rolling_mean = self._append_return(mean_return)
        self.logger.record("eval/mean_return", mean_return)
        self.logger.record("eval/std_return", std_return)
        self.logger.record("eval/mean_return_rolling", float(rolling_mean))

        if self.best_model_save_path and mean_return > self.best_mean_return:
            self.best_mean_return = mean_return
            best_path = os.path.join(self.best_model_save_path, "best_model")
            self.model.save(best_path)
            print(
                f"New best model by geometric return: "
                f"mean_return={mean_return:.6f} (saved to {best_path}.zip)"
            )
        return True

def train(
    stock: str = None,
    stocks: list = None,
    all_stocks: bool = False,
    data_dir: str = TRAIN_DEFAULTS["data_dir"],
    drawdown_penalty_enabled: Optional[bool] = None,
    drawdown_penalty_lambda: Optional[float] = None,
    drawdown_penalty_train_only: Optional[bool] = None,
    reward_benchmark: Optional[str] = None,
    benchmark_weight: Optional[float] = None,
    benchmark_relative_reward: Optional[bool] = None,
    train_episode_sampling_enabled: Optional[bool] = None,
    train_episode_min_fraction: Optional[float] = None,
    train_episode_max_fraction: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    source_mode: Optional[str] = None,
    ma_windows: list = None,
    helpers_ma_windows: list = None,
    returns_windows: list = None,
    helpers_returns_windows: list = None,
    engineered_features: Optional[list] = None,
    window_policy: Optional[str] = None,
    feature_windows: Optional[list] = None,
    logspace_min: Optional[int] = None,
    logspace_max: Optional[int] = None,
    logspace_count: Optional[int] = None,
    rs_market_proxies: Optional[list] = None,
    rs_include_long: Optional[bool] = None,
    calendar_features: Optional[list] = None,
    news_feature_columns: Optional[list] = None,
    news_prediction_dir: Optional[str] = None,
    signal_feature_columns: Optional[list] = None,
    signal_prediction_dir: Optional[str] = None,
    help_tickers: list = None,
    market_data_dir: str = TRAIN_DEFAULTS["market_data_dir"],
    help_assets: list = None,
    help_assets_dir: str = TRAIN_DEFAULTS["help_assets_dir"],
    total_timesteps: int = TRAIN_DEFAULTS["total_timesteps"],
    model_name: str = None,
    save_dir: str = TRAIN_DEFAULTS["save_dir"],
    log_dir: str = TRAIN_DEFAULTS["log_dir"],
    checkpoint_freq: int = TRAIN_DEFAULTS["checkpoint_freq"],
    n_envs: int = TRAIN_DEFAULTS["n_envs"],
    policy: str = TRAIN_DEFAULTS["policy"],
    ent_coef_start: float = TRAIN_DEFAULTS["ent_coef_start"],
    ent_coef_end: float = TRAIN_DEFAULTS["ent_coef_end"],
    ent_coef_schedule: str = TRAIN_DEFAULTS["ent_coef_schedule"],
    eval_freq: int = TRAIN_DEFAULTS["eval_freq"],
    n_eval_episodes: int = TRAIN_DEFAULTS["n_eval_episodes"],
    seed: int = None
):
    """
    Train a PPO agent on the trading environment.
    
    Args:
        stock: Stock ticker (e.g., 'ACB') - for single stock mode
        stocks: List of stock tickers (e.g., ['ACB', 'VNM', 'HPG']) - for multi-stock mode
        all_stocks: Train on all stocks in data directory
        data_dir: Directory containing parquet files
        drawdown_penalty_enabled: Override drawdown penalty on/off
        drawdown_penalty_lambda: Override drawdown penalty lambda (>=0)
        drawdown_penalty_train_only: Apply drawdown penalty only in train mode when True
        reward_benchmark: Benchmark for relative reward shaping (currently: self_buy_hold)
        benchmark_weight: Weight applied to the benchmark return in shaped reward
        benchmark_relative_reward: When True, optimize agent_return - benchmark_weight * benchmark_return
        train_episode_sampling_enabled: Override random train sub-episode sampling on/off
        train_episode_min_fraction: Min sampled train episode fraction in (0,1]
        train_episode_max_fraction: Max sampled train episode fraction in (0,1]
        start_date: Optional inclusive sample start date before train/val/test split
        end_date: Optional inclusive sample end date before train/val/test split
        source_mode: Optional feature source mode override ('raw' or 'return')
        ma_windows: Optional moving-average windows to append as features (e.g., [5, 10, 20])
        helpers_ma_windows: Optional helper moving-average windows, or ['same'] to mirror ma_windows
        returns_windows: Optional close-based return windows (e.g., [5, 10, 20])
        helpers_returns_windows: Optional helper return windows, or ['same'] to mirror returns_windows
        engineered_features: Optional engineered feature families to enable
        window_policy: Engineered feature window policy ('explicit' or 'logspace')
        feature_windows: Explicit engineered windows when window_policy='explicit'
        logspace_min/logspace_max/logspace_count: Logspace window generator params
        rs_market_proxies: Relative-strength market proxy tickers preference
        rs_include_long: Whether to include long-horizon relative strength
        calendar_features: Optional calendar features (any of: dow month dom)
        news_feature_columns: Optional daily news feature columns to merge by date
        news_prediction_dir: Optional directory containing per-ticker news parquet exports
        signal_feature_columns: Optional supervised signal feature columns to merge by date
        signal_prediction_dir: Optional directory containing per-ticker signal parquet exports
        help_tickers: Optional list of helper tickers to append as features
        market_data_dir: Directory containing market parquet files
        help_assets: Optional list of helper assets to append as features
        help_assets_dir: Directory containing helper asset parquet files
        total_timesteps: Total training steps
        model_name: Name for saved model. If omitted, auto-generates
            {policy}_{stock}_{timesteps}_{timestamp}.
        save_dir: Root directory for per-run model artifacts
        log_dir: Root directory for per-run tensorboard logs
        checkpoint_freq: Steps between model checkpoints
        n_envs: Number of parallel environments (default: 4, set to 1 to disable)
        policy: Policy architecture ('mlp', 'cnn', 'lstm', 'cnn-lstm',
            'cnn-attention', 'cnn-attention-lstm',
            'cnn-window-attention', 'cnn-window-attention-lstm',
            'multi-cnn', 'multi-cnn-lstm', 'transformer', or 'transformer-lstm')
        ent_coef_start: Starting entropy coefficient
        ent_coef_end: Final entropy coefficient (for scheduled decay)
        ent_coef_schedule: Entropy schedule: constant, linear, cosine
        eval_freq: Evaluate on validation set every N global timesteps
        n_eval_episodes: Number of validation episodes per eval
        seed: Optional random seed for reproducibility
    """
    
    # Validate arguments
    num_modes = sum([stock is not None, stocks is not None, all_stocks])
    if num_modes == 0:
        raise ValueError("Must specify either --stock, --stocks, or --all-stocks")
    if num_modes > 1:
        raise ValueError("Cannot specify more than one of --stock, --stocks, or --all-stocks")
    
    policy = _normalize_policy(policy)
    if policy not in [
        'mlp',
        'lstm',
        'cnn',
        'cnn_lstm',
        'cnn_attention',
        'cnn_attention_lstm',
        'cnn_window_attention',
        'cnn_window_attention_lstm',
        'multi_cnn',
        'multi_cnn_lstm',
        'transformer',
        'transformer_lstm',
    ]:
        raise ValueError(
            "Invalid policy: "
            f"{policy}. Must be 'mlp', 'lstm', 'cnn', 'cnn-lstm' (legacy alias: 'cnn_lstm'), "
            "'cnn-attention', 'cnn-attention-lstm', "
            "'cnn-window-attention', 'cnn-window-attention-lstm', 'multi-cnn', "
            "'multi-cnn-lstm', 'transformer', or 'transformer-lstm'."
        )
    if ent_coef_schedule not in ["constant", "linear", "cosine"]:
        raise ValueError(f"Invalid ent_coef_schedule: {ent_coef_schedule}. Must be 'constant', 'linear', or 'cosine'")
    if n_envs < 1:
        raise ValueError(f"Invalid n_envs: {n_envs}. Must be >= 1.")
    if eval_freq < 1:
        raise ValueError(f"Invalid eval_freq: {eval_freq}. Must be >= 1.")
    if n_eval_episodes < 1:
        raise ValueError(f"Invalid n_eval_episodes: {n_eval_episodes}. Must be >= 1.")
    if seed is not None and seed < 0:
        raise ValueError(f"Invalid seed: {seed}. Must be >= 0.")
    if drawdown_penalty_lambda is not None:
        drawdown_penalty_lambda = float(drawdown_penalty_lambda)
        if drawdown_penalty_lambda < 0.0:
            raise ValueError(f"--drawdown-penalty-lambda must be >= 0.0, got {drawdown_penalty_lambda}")
    reward_benchmark = _parse_reward_benchmark(reward_benchmark)
    if benchmark_weight is not None:
        benchmark_weight = float(benchmark_weight)
        if benchmark_weight < 0.0:
            raise ValueError(f"--benchmark-weight must be >= 0.0, got {benchmark_weight}")
    if train_episode_min_fraction is not None:
        train_episode_min_fraction = float(train_episode_min_fraction)
    if train_episode_max_fraction is not None:
        train_episode_max_fraction = float(train_episode_max_fraction)
    if train_episode_min_fraction is not None and not (0.0 < train_episode_min_fraction <= 1.0):
        raise ValueError(
            f"--train-episode-min-fraction must be in (0,1], got {train_episode_min_fraction}"
        )
    if train_episode_max_fraction is not None and not (0.0 < train_episode_max_fraction <= 1.0):
        raise ValueError(
            f"--train-episode-max-fraction must be in (0,1], got {train_episode_max_fraction}"
        )
    if (
        train_episode_min_fraction is not None
        and train_episode_max_fraction is not None
        and train_episode_min_fraction > train_episode_max_fraction
    ):
        raise ValueError(
            "--train-episode-min-fraction must be <= --train-episode-max-fraction, got "
            f"{train_episode_min_fraction} > {train_episode_max_fraction}"
        )
    ma_windows = _parse_window_list(ma_windows, "--ma-windows")
    helpers_ma_windows = _parse_helper_window_list(helpers_ma_windows, "--helpers-ma-windows")
    returns_windows = _parse_window_list(returns_windows, "--returns-windows")
    helpers_returns_windows = _parse_helper_window_list(helpers_returns_windows, "--helpers-returns-windows")
    engineered_features = _parse_engineered_feature_families(engineered_features)
    feature_windows = _parse_window_list(feature_windows, "--feature-windows")
    rs_market_proxies = _parse_rs_market_proxies(rs_market_proxies)
    news_feature_columns = _parse_news_feature_columns(news_feature_columns)
    signal_feature_columns = _parse_signal_feature_columns(signal_feature_columns)
    if window_policy is not None:
        window_policy = str(window_policy).strip().lower()
        if window_policy not in {"explicit", "logspace"}:
            raise ValueError(f"--window-policy must be 'explicit' or 'logspace', got {window_policy}")

    policy_display = _policy_display_name(policy)

    if isinstance(model_name, str):
        model_name = model_name.strip()
    if not model_name:
        model_name = _auto_model_name(policy_display, stock, stocks, all_stocks, total_timesteps)

    save_root_dir = save_dir
    log_root_dir = log_dir
    run_dir = os.path.join(save_root_dir, model_name)
    checkpoints_dir = os.path.join(run_dir, "checkpoints")
    log_dir = os.path.join(log_root_dir, model_name, "logs")

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
        th.manual_seed(seed)
        if th.cuda.is_available():
            th.cuda.manual_seed_all(seed)
        set_random_seed(seed)

    def _filter_help_tickers(help_list, primary_stock, primary_stocks, use_all):
        if not help_list:
            return None
        if use_all:
            print(
                "WARN: --help-tickers is disabled in --all-stocks mode. "
                "It is treated as a training signal (not passive context), "
                "so we disable it to keep the setup simple and avoid leakage-style coupling."
            )
            return None
        base = set()
        if primary_stock:
            base.add(primary_stock.upper())
        if primary_stocks:
            base |= {s.upper() for s in primary_stocks}
        return [t.upper() for t in help_list if t.upper() not in base]

    help_tickers = _filter_help_tickers(help_tickers, stock, stocks, all_stocks)
    
    # Create directories
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(checkpoints_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    
    print("="*60)
    print("Training Configuration")
    print("="*60)
    
    # GPU Detection and Configuration
    print("\n" + "="*60)
    print("GPU Configuration")
    print("="*60)
    cuda_available = th.cuda.is_available()
    print(f"PyTorch CUDA available: {cuda_available}")
    
    if cuda_available:
        device = "cuda"
        print(f"GPU Device: {th.cuda.get_device_name(0)}")
        print(f"GPU Memory: {th.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
        print(f"Using device: {device}")
    else:
        device = "cpu"
        print("No GPU detected, using CPU")
        print("WARNING: Training will be MUCH slower on CPU!")
        print("   Consider using Google Colab or a cloud GPU for faster training")
    print("="*60)
    
    print("\n" + "="*60)
    print("Dataset Configuration")
    print("="*60)
    
    if all_stocks:
        print(f"Mode: Multi-Stock (All stocks)")
        print(f"Data directory: {data_dir}")
    elif stocks:
        print(f"Mode: Multi-Stock (Selected stocks)")
        print(f"Stocks: {', '.join(stocks)}")
        print(f"Data directory: {data_dir}")
    else:
        print(f"Mode: Single-Stock")
        print(f"Stock: {stock}")
        print(f"Data file: {data_dir}gia_lich_su_{stock}_1D.parquet")
    if source_mode:
        print(f"Feature source mode override: {source_mode}")
    if drawdown_penalty_enabled is not None:
        print(f"Drawdown penalty enabled override: {bool(drawdown_penalty_enabled)}")
    if drawdown_penalty_lambda is not None:
        print(f"Drawdown penalty lambda override: {drawdown_penalty_lambda}")
    if drawdown_penalty_train_only is not None:
        print(f"Drawdown penalty train-only override: {bool(drawdown_penalty_train_only)}")
    if benchmark_relative_reward is not None:
        print(f"Benchmark-relative reward override: {bool(benchmark_relative_reward)}")
    if reward_benchmark is not None:
        print(f"Reward benchmark override: {reward_benchmark}")
    if benchmark_weight is not None:
        print(f"Benchmark weight override: {benchmark_weight}")
    if train_episode_sampling_enabled is not None:
        print(f"Train sub-episode sampling override: {bool(train_episode_sampling_enabled)}")
    if train_episode_min_fraction is not None or train_episode_max_fraction is not None:
        print(
            "Train sub-episode fraction override: "
            f"min={train_episode_min_fraction}, max={train_episode_max_fraction}"
        )
    if start_date or end_date:
        print(f"Sample date filter: start={start_date or 'None'}, end={end_date or 'None'}")
    if ma_windows:
        print(f"MA windows: {', '.join(str(int(w)) for w in ma_windows)}")
    if helpers_ma_windows:
        print(
            "Helper MA windows: "
            + ("same as target MA windows" if helpers_ma_windows == ["same"] else ", ".join(str(int(w)) for w in helpers_ma_windows))
        )
    if returns_windows:
        print(f"Returns windows: {', '.join(str(int(w)) for w in returns_windows)}")
    if helpers_returns_windows:
        print(
            "Helper returns windows: "
            + (
                "same as target returns windows"
                if helpers_returns_windows == ["same"]
                else ", ".join(str(int(w)) for w in helpers_returns_windows)
            )
        )
    if engineered_features is not None:
        print(
            "Engineered features: "
            + (", ".join(engineered_features) if engineered_features else "disabled")
        )
    if window_policy is not None:
        print(f"Engineered window policy override: {window_policy}")
    if feature_windows:
        print(f"Engineered explicit windows: {', '.join(str(int(w)) for w in feature_windows)}")
    if any(v is not None for v in (logspace_min, logspace_max, logspace_count)):
        print(
            "Engineered logspace params override: "
            f"min={logspace_min}, max={logspace_max}, count={logspace_count}"
        )
    if rs_market_proxies:
        print(f"RS market proxies override: {', '.join(rs_market_proxies)}")
    if rs_include_long is not None:
        print(f"RS include long horizon override: {bool(rs_include_long)}")
    if calendar_features:
        print(f"Calendar features: {', '.join(str(f).lower() for f in calendar_features)}")
    if news_feature_columns is not None:
        print(
            "News features: "
            + (", ".join(news_feature_columns) if news_feature_columns else "disabled")
        )
        if news_feature_columns:
            print(f"News predictions dir: {news_prediction_dir or 'data/features/news/predictions'}")
    if signal_feature_columns is not None:
        print(
            "Signal features: "
            + (", ".join(signal_feature_columns) if signal_feature_columns else "disabled")
        )
        if signal_feature_columns:
            print(
                f"Signal predictions dir: {signal_prediction_dir or str(default_signal_prediction_dir())}"
            )
    if help_tickers:
        print(f"Help tickers: {', '.join(help_tickers)}")
        print(f"Market data dir: {market_data_dir}")
    if help_assets:
        print(f"Help assets: {', '.join(help_assets)}")
        print(f"Help assets dir: {help_assets_dir}")
    
    print(f"Policy: {policy_display.upper()}")
    print(f"Total timesteps: {total_timesteps:,}")
    print(f"Model name: {model_name}")
    print(f"Artifacts root: {save_root_dir}")
    print(f"Run directory: {run_dir}")
    print(f"Checkpoints directory: {checkpoints_dir}")
    print(f"Log directory: {log_dir}")
    print(f"Parallel environments: {n_envs}")
    print(f"Seed: {seed if seed is not None else 'None (random)'}")
    if ent_coef_schedule == "constant":
        print(f"Entropy coef: {ent_coef_start} (constant)")
    else:
        print(f"Entropy coef: {ent_coef_start} -> {ent_coef_end} ({ent_coef_schedule} schedule)")
    print("="*60)

    def make_ent_coef_schedule():
        """Create entropy coefficient schedule function (or None for constant)."""
        if ent_coef_schedule == "constant":
            return None

        start = float(ent_coef_start)
        end = float(ent_coef_end)

        if ent_coef_schedule == "linear":
            # progress_remaining goes from 1.0 (start) to 0.0 (end)
            def _linear(progress_remaining: float) -> float:
                return end + (start - end) * progress_remaining
            return _linear

        # cosine schedule
        def _cosine(progress_remaining: float) -> float:
            # Cosine from start -> end over training
            return end + 0.5 * (start - end) * (1 + np.cos(np.pi * (1 - progress_remaining)))
        return _cosine

    # Create training environment
    print("\nCreating training environment...")
    
    def make_env(rank):
        """Create a single environment (for parallelization)."""
        def _init():
            # Only monitor the first environment to avoid too many log files.
            monitor_path = log_dir if rank == 0 else None
            return _build_env(
                mode="train",
                stock=stock,
                stocks=stocks,
                all_stocks=all_stocks,
                data_dir=data_dir,
                drawdown_penalty_enabled=drawdown_penalty_enabled,
                drawdown_penalty_lambda=drawdown_penalty_lambda,
                drawdown_penalty_train_only=drawdown_penalty_train_only,
                reward_benchmark=reward_benchmark,
                benchmark_weight=benchmark_weight,
                benchmark_relative_reward=benchmark_relative_reward,
                train_episode_sampling_enabled=train_episode_sampling_enabled,
                train_episode_min_fraction=train_episode_min_fraction,
                train_episode_max_fraction=train_episode_max_fraction,
                start_date=start_date,
                end_date=end_date,
                source_mode=source_mode,
                ma_windows=ma_windows,
                helpers_ma_windows=helpers_ma_windows,
                returns_windows=returns_windows,
                helpers_returns_windows=helpers_returns_windows,
                engineered_features=engineered_features,
                window_policy=window_policy,
                feature_windows=feature_windows,
                logspace_min=logspace_min,
                logspace_max=logspace_max,
                logspace_count=logspace_count,
                rs_market_proxies=rs_market_proxies,
                rs_include_long=rs_include_long,
                calendar_features=calendar_features,
                news_feature_columns=news_feature_columns,
                news_prediction_dir=news_prediction_dir,
                signal_feature_columns=signal_feature_columns,
                signal_prediction_dir=signal_prediction_dir,
                help_tickers=help_tickers,
                market_data_dir=market_data_dir,
                help_assets=help_assets,
                help_assets_dir=help_assets_dir,
                monitor_path_or_none=monitor_path,
            )
        return _init
    
    # Create vectorized environment
    if n_envs > 1:
        print(f"Using {n_envs} parallel environments for faster training...")
        train_env = SubprocVecEnv([make_env(i) for i in range(n_envs)])
        if seed is not None:
            train_env.seed(seed)
    else:
        print("Using single environment (no parallelization)...")
        train_env = _build_env(
            mode="train",
            stock=stock,
            stocks=stocks,
            all_stocks=all_stocks,
            data_dir=data_dir,
            drawdown_penalty_enabled=drawdown_penalty_enabled,
            drawdown_penalty_lambda=drawdown_penalty_lambda,
            drawdown_penalty_train_only=drawdown_penalty_train_only,
            reward_benchmark=reward_benchmark,
            benchmark_weight=benchmark_weight,
            benchmark_relative_reward=benchmark_relative_reward,
            train_episode_sampling_enabled=train_episode_sampling_enabled,
            train_episode_min_fraction=train_episode_min_fraction,
            train_episode_max_fraction=train_episode_max_fraction,
            start_date=start_date,
            end_date=end_date,
            source_mode=source_mode,
            ma_windows=ma_windows,
            helpers_ma_windows=helpers_ma_windows,
            returns_windows=returns_windows,
            helpers_returns_windows=helpers_returns_windows,
            engineered_features=engineered_features,
            window_policy=window_policy,
            feature_windows=feature_windows,
            logspace_min=logspace_min,
            logspace_max=logspace_max,
            logspace_count=logspace_count,
            rs_market_proxies=rs_market_proxies,
            rs_include_long=rs_include_long,
            calendar_features=calendar_features,
            news_feature_columns=news_feature_columns,
            news_prediction_dir=news_prediction_dir,
            signal_feature_columns=signal_feature_columns,
            signal_prediction_dir=signal_prediction_dir,
            help_tickers=help_tickers,
            market_data_dir=market_data_dir,
            help_assets=help_assets,
            help_assets_dir=help_assets_dir,
            monitor_path_or_none=log_dir,
        )
        if seed is not None:
            try:
                train_env.reset(seed=seed)
            except TypeError:
                pass
    
    print(f"\nEnvironment info:")
    print(f"  Observation space: {train_env.observation_space}")
    print(f"  Action space: {train_env.action_space}")

    # Snapshot resolved environment config early (before learning), so metadata remains valid
    # even if learning is interrupted and vec env wrappers are partially torn down.
    env_input_features_snapshot = _get_env_attr(train_env, "input_features", default=None)
    env_config_snapshot = {
        "lookback_window": _get_env_attr(train_env, "lookback_window"),
        "source_mode": _get_env_attr(train_env, "source_mode", default=None),
        "ohlcv": _get_env_attr(train_env, "ohlcv_fields", default=None),
        "calendar_features": _get_env_attr(train_env, "calendar_features", default=None),
        "calendar_encoding": "sincos",
        "input_features": env_input_features_snapshot,
        "ma_windows": _get_env_attr(train_env, "ma_windows", default=[]),
        "helpers_ma_windows": _get_env_attr(train_env, "helpers_ma_windows_cfg", default=[]),
        "returns_windows": _get_env_attr(train_env, "returns_windows", default=[]),
        "helpers_returns_windows": _get_env_attr(train_env, "helpers_returns_windows_cfg", default=[]),
        "engineered_features": _get_env_attr(train_env, "engineered_feature_families", default=[]),
        "window_policy": _get_env_attr(train_env, "engineered_window_policy", default=None),
        "feature_windows": _get_env_attr(train_env, "engineered_feature_windows", default=[]),
        "logspace_min": (
            (env_input_features_snapshot or {})
            .get("engineered_features", {})
            .get("window_policy", {})
            .get("logspace_min")
        ),
        "logspace_max": (
            (env_input_features_snapshot or {})
            .get("engineered_features", {})
            .get("window_policy", {})
            .get("logspace_max")
        ),
        "logspace_count": (
            (env_input_features_snapshot or {})
            .get("engineered_features", {})
            .get("window_policy", {})
            .get("logspace_count")
        ),
        "rs_market_proxies": _get_env_attr(train_env, "rs_market_proxies", default=[]),
        "rs_include_long": _get_env_attr(train_env, "rs_include_long", default=None),
        "drawdown_penalty_enabled": bool(
            _get_env_attr(train_env, "drawdown_penalty_enabled", default=True)
        ),
        "sample_start_date": (
            (
                _get_env_attr(train_env, "sample_start_date", default=None).strftime("%Y-%m-%d")
                if _get_env_attr(train_env, "sample_start_date", default=None) is not None
                else None
            )
        ),
        "sample_end_date": (
            (
                _get_env_attr(train_env, "sample_end_date", default=None).strftime("%Y-%m-%d")
                if _get_env_attr(train_env, "sample_end_date", default=None) is not None
                else None
            )
        ),
        "drawdown_penalty_lambda": float(
            _get_env_attr(train_env, "drawdown_penalty_lambda", default=0.05)
        ),
        "drawdown_penalty_train_only": bool(
            _get_env_attr(train_env, "drawdown_penalty_train_only", default=True)
        ),
        "benchmark_relative_reward": bool(
            _get_env_attr(train_env, "benchmark_relative_reward_enabled", default=False)
        ),
        "reward_benchmark": _get_env_attr(train_env, "reward_benchmark", default="self_buy_hold"),
        "benchmark_weight": float(
            _get_env_attr(train_env, "benchmark_weight", default=1.0)
        ),
        "reward_shaping": _get_env_attr(train_env, "reward_shaping", default=None),
        "train_episode_sampling_enabled": bool(
            _get_env_attr(train_env, "train_episode_sampling_enabled", default=True)
        ),
        "train_episode_min_fraction": float(
            _get_env_attr(train_env, "train_episode_min_fraction", default=0.2)
        ),
        "train_episode_max_fraction": float(
            _get_env_attr(train_env, "train_episode_max_fraction", default=0.6)
        ),
        "train_episode_sampling": {
            "enabled": bool(_get_env_attr(train_env, "train_episode_sampling_enabled", default=True)),
            "mode": str(_get_env_attr(train_env, "train_episode_sampling_mode", default="fraction")),
            "min_fraction": float(_get_env_attr(train_env, "train_episode_min_fraction", default=0.2)),
            "max_fraction": float(_get_env_attr(train_env, "train_episode_max_fraction", default=0.6)),
        },
        "start_episode_position": float(
            _get_env_attr(train_env, "start_episode_position", default=0.0)
        ),
        "train_split": _get_env_attr(train_env, "train_split"),
        "val_split": _get_env_attr(train_env, "val_split"),
        "min_hold_days": _get_env_attr(train_env, "min_hold_days"),
        "buy_fee_rate": _get_env_attr(train_env, "buy_fee_rate"),
        "sell_fee_rate": _get_env_attr(train_env, "sell_fee_rate"),
        "capital_gains_tax_rate": _get_env_attr(train_env, "capital_gains_tax_rate"),
        "stop_loss": _get_env_attr(train_env, "stop_loss"),
        "include_can_exit": bool(_get_env_attr(train_env, "include_can_exit", default=True)),
    }
    if all_stocks or stocks:
        resolved_stocks_snapshot = _get_env_attr(train_env, "stock_names", default=[]) or []
        if not resolved_stocks_snapshot and stocks:
            resolved_stocks_snapshot = list(stocks)
    else:
        resolved_stocks_snapshot = [stock] if stock else []
    
    # Create checkpoint callback
    checkpoint_freq_callback_steps = max(checkpoint_freq // n_envs, 1)
    checkpoint_freq_effective_global = checkpoint_freq_callback_steps * n_envs
    print(
        "Checkpoint interval (global timesteps): "
        f"requested={checkpoint_freq}, effective~={checkpoint_freq_effective_global} "
        f"(callback every {checkpoint_freq_callback_steps} vec step(s) with n_envs={n_envs})"
    )
    checkpoint_callback = CheckpointCallback(
        save_freq=checkpoint_freq_callback_steps,
        save_path=checkpoints_dir,
        name_prefix=model_name,
        save_replay_buffer=False,
        save_vecnormalize=False
    )
    
    # Create validation environment and evaluation callback
    def make_eval_env():
        return _build_env(
            mode="val",
            stock=stock,
            stocks=stocks,
            all_stocks=all_stocks,
            data_dir=data_dir,
            drawdown_penalty_enabled=drawdown_penalty_enabled,
            drawdown_penalty_lambda=drawdown_penalty_lambda,
            drawdown_penalty_train_only=drawdown_penalty_train_only,
            reward_benchmark=reward_benchmark,
            benchmark_weight=benchmark_weight,
            benchmark_relative_reward=benchmark_relative_reward,
            train_episode_sampling_enabled=train_episode_sampling_enabled,
            train_episode_min_fraction=train_episode_min_fraction,
            train_episode_max_fraction=train_episode_max_fraction,
            start_date=start_date,
            end_date=end_date,
            source_mode=source_mode,
            ma_windows=ma_windows,
            helpers_ma_windows=helpers_ma_windows,
            returns_windows=returns_windows,
            helpers_returns_windows=helpers_returns_windows,
            engineered_features=engineered_features,
            window_policy=window_policy,
            feature_windows=feature_windows,
            logspace_min=logspace_min,
            logspace_max=logspace_max,
            logspace_count=logspace_count,
            rs_market_proxies=rs_market_proxies,
            rs_include_long=rs_include_long,
            calendar_features=calendar_features,
            news_feature_columns=news_feature_columns,
            news_prediction_dir=news_prediction_dir,
            signal_feature_columns=signal_feature_columns,
            signal_prediction_dir=signal_prediction_dir,
            help_tickers=help_tickers,
            market_data_dir=market_data_dir,
            help_assets=help_assets,
            help_assets_dir=help_assets_dir,
            monitor_path_or_none="",
        )
    
    eval_env = DummyVecEnv([make_eval_env])
    val_return_env = DummyVecEnv([make_eval_env])
    if seed is not None:
        eval_env.seed(seed + 10_000)
        val_return_env.seed(seed + 20_000)
    # EvalCallback counts vectorized env steps, not global timesteps.
    # Convert requested global timesteps to callback step frequency.
    eval_freq_callback_steps = max(eval_freq // n_envs, 1)
    eval_freq_effective_global = eval_freq_callback_steps * n_envs
    run_best_dir = os.path.join(run_dir, "_best_tmp")
    if os.path.exists(run_best_dir):
        shutil.rmtree(run_best_dir, ignore_errors=True)
    os.makedirs(run_best_dir, exist_ok=True)
    print(
        "Validation eval interval (global timesteps): "
        f"requested={eval_freq}, effective~={eval_freq_effective_global} "
        f"(callback every {eval_freq_callback_steps} vec step(s) with n_envs={n_envs})"
    )
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=None,
        log_path=os.path.join(log_dir, "eval"),
        eval_freq=eval_freq_callback_steps,
        n_eval_episodes=n_eval_episodes,
        deterministic=True,
        render=False,
        verbose=1
    )
    validation_return_callback = ValidationReturnCallback(
        eval_env=val_return_env,
        eval_freq=eval_freq_callback_steps,
        n_eval_episodes=n_eval_episodes,
        deterministic=True,
        window_size=20,
        best_model_save_path=run_best_dir,
    )
    
    # Optional entropy schedule callback
    ent_schedule_fn = make_ent_coef_schedule()
    training_episode_stats_callback = TrainingEpisodeStatsCallback(window_size=100)
    if ent_schedule_fn is not None:
        entropy_callback = EntropyScheduleCallback(ent_schedule_fn)
        callbacks = CallbackList(
            [
                checkpoint_callback,
                eval_callback,
                validation_return_callback,
                training_episode_stats_callback,
                entropy_callback,
            ]
        )
    else:
        callbacks = CallbackList(
            [checkpoint_callback, eval_callback, validation_return_callback, training_episode_stats_callback]
        )
    
    # Create model based on policy type
    print("\n" + "="*60)
    print(f"Initializing {policy_display.upper()} Agent")
    print("="*60)
    
    if policy == "lstm":
        # LSTM policy for temporal learning
        # LSTM naturally handles sequential dependencies in time-series
        policy_cfg = POLICY_CONFIGS["lstm"]
        policy_kwargs = dict(
            lstm_hidden_size=policy_cfg["policy_kwargs"]["lstm_hidden_size"],
            n_lstm_layers=policy_cfg["policy_kwargs"]["n_lstm_layers"],
            enable_critic_lstm=policy_cfg["policy_kwargs"]["enable_critic_lstm"],
            shared_lstm=policy_cfg["policy_kwargs"]["shared_lstm"],
            activation_fn=th.nn.ReLU,
            net_arch=policy_cfg["policy_kwargs"]["net_arch"],
        )
        
        model = RecurrentPPO(
            "MlpLstmPolicy",
            train_env,
            policy_kwargs=policy_kwargs,
            verbose=1,
            learning_rate=policy_cfg["model_kwargs"]["learning_rate"],
            n_steps=policy_cfg["model_kwargs"]["n_steps"],
            batch_size=policy_cfg["model_kwargs"]["batch_size"],
            n_epochs=policy_cfg["model_kwargs"]["n_epochs"],
            gamma=policy_cfg["model_kwargs"]["gamma"],
            gae_lambda=policy_cfg["model_kwargs"]["gae_lambda"],
            clip_range=policy_cfg["model_kwargs"]["clip_range"],
            ent_coef=float(ent_coef_start),
            tensorboard_log=log_dir,
            device=device,  # GPU/CPU selection
            seed=seed
        )
        
        print("\nLSTM Configuration:")
        print(f"  Hidden size: {policy_kwargs['lstm_hidden_size']}")
        print(f"  Num layers: {policy_kwargs['n_lstm_layers']}")
        print(f"  Critic LSTM: {policy_kwargs['enable_critic_lstm']}")
        
    elif policy in {"cnn_lstm", "cnn_attention_lstm", "cnn_window_attention_lstm", "multi_cnn_lstm", "transformer_lstm"}:
        if n_envs > 1:
            lookback_window = train_env.get_attr('lookback_window')[0]
        else:
            lookback_window = train_env.get_wrapper_attr('lookback_window')

        if policy == "multi_cnn_lstm":
            cfg_key = "multi_cnn_lstm"
            extractor_cls = StockMultiCNNExtractorForLSTM
            section_name = "MULTI-CNN+LSTM"
        elif policy == "cnn_lstm":
            cfg_key = "cnn_lstm"
            extractor_cls = StockClassicCNNExtractorForLSTM
            section_name = "CNN+LSTM"
        elif policy == "cnn_attention_lstm":
            cfg_key = "cnn_attention_lstm"
            extractor_cls = CNNAttentionExtractorForLSTM
            section_name = "CNN-ATTENTION+LSTM"
        elif policy == "cnn_window_attention_lstm":
            cfg_key = "cnn_window_attention_lstm"
            extractor_cls = CNNWindowAttentionExtractorForLSTM
            section_name = "CNN-WINDOW-ATTENTION+LSTM"
        else:
            cfg_key = "transformer_lstm"
            extractor_cls = StockTransformerExtractorForLSTM
            section_name = "TRANSFORMER+LSTM"
        policy_cfg = POLICY_CONFIGS[cfg_key]
        extractor_kwargs = dict(policy_cfg["policy_kwargs"].get("features_extractor_kwargs", {}))
        extractor_kwargs["lookback_window"] = lookback_window
        policy_kwargs = dict(
            features_extractor_class=extractor_cls,
            features_extractor_kwargs=extractor_kwargs,
            lstm_hidden_size=policy_cfg["policy_kwargs"]["lstm_hidden_size"],
            n_lstm_layers=policy_cfg["policy_kwargs"]["n_lstm_layers"],
            enable_critic_lstm=policy_cfg["policy_kwargs"]["enable_critic_lstm"],
            shared_lstm=policy_cfg["policy_kwargs"]["shared_lstm"],
            activation_fn=th.nn.ReLU,
            net_arch=policy_cfg["policy_kwargs"]["net_arch"],
        )

        model = RecurrentPPO(
            "MlpLstmPolicy",
            train_env,
            policy_kwargs=policy_kwargs,
            verbose=1,
            learning_rate=policy_cfg["model_kwargs"]["learning_rate"],
            n_steps=policy_cfg["model_kwargs"]["n_steps"],
            batch_size=policy_cfg["model_kwargs"]["batch_size"],
            n_epochs=policy_cfg["model_kwargs"]["n_epochs"],
            gamma=policy_cfg["model_kwargs"]["gamma"],
            gae_lambda=policy_cfg["model_kwargs"]["gae_lambda"],
            clip_range=policy_cfg["model_kwargs"]["clip_range"],
            ent_coef=float(ent_coef_start),
            tensorboard_log=log_dir,
            device=device,
            seed=seed
        )

        print(f"\n{section_name} Configuration:")
        print(f"  Lookback window: {lookback_window}")
        print(f"  Embedding dim: {policy_kwargs['features_extractor_kwargs']['features_dim']}")
        if policy == "multi_cnn_lstm":
            print(f"  CNN windows: {policy_kwargs['features_extractor_kwargs'].get('multi_scale_windows')}")
            print(f"  CNN branch channels: {policy_kwargs['features_extractor_kwargs'].get('branch_channels')}")
            print("  Architecture: obs -> Multi-CNN -> features -> LSTM -> policy/value")
        elif policy == "cnn_lstm":
            print(f"  CNN batch norm: {policy_kwargs['features_extractor_kwargs'].get('use_batch_norm', True)}")
            print("  Architecture: obs -> CNN -> features -> LSTM -> policy/value")
        elif policy == "cnn_attention_lstm":
            print(f"  Window size: {policy_kwargs['features_extractor_kwargs'].get('window_size')}")
            print(f"  Window stride: {policy_kwargs['features_extractor_kwargs'].get('stride')}")
            print(f"  CNN channels: {policy_kwargs['features_extractor_kwargs'].get('cnn_channels')}")
            print(f"  Window embed dim: {policy_kwargs['features_extractor_kwargs'].get('embed_dim')}")
            print(f"  Transformer heads: {policy_kwargs['features_extractor_kwargs'].get('n_heads')}")
            print(f"  Transformer layers: {policy_kwargs['features_extractor_kwargs'].get('n_layers')}")
            print(f"  Transformer dropout: {policy_kwargs['features_extractor_kwargs'].get('dropout')}")
            print(f"  Pooling: {policy_kwargs['features_extractor_kwargs'].get('pooling')}")
            print("  Architecture: obs -> CNN -> windows -> attention -> features -> LSTM -> policy/value")
        elif policy == "cnn_window_attention_lstm":
            print(f"  Window size: {policy_kwargs['features_extractor_kwargs'].get('window_size')}")
            print(f"  Window stride: {policy_kwargs['features_extractor_kwargs'].get('stride')}")
            print(f"  CNN channels: {policy_kwargs['features_extractor_kwargs'].get('cnn_channels')}")
            print(f"  Window embed dim: {policy_kwargs['features_extractor_kwargs'].get('embed_dim')}")
            print(f"  Transformer heads: {policy_kwargs['features_extractor_kwargs'].get('n_heads')}")
            print(f"  Transformer layers: {policy_kwargs['features_extractor_kwargs'].get('n_layers')}")
            print(f"  Transformer dropout: {policy_kwargs['features_extractor_kwargs'].get('dropout')}")
            print(f"  Pooling: {policy_kwargs['features_extractor_kwargs'].get('pooling')}")
            print("  Architecture: obs -> CNN -> windows -> window-importance -> features -> LSTM -> policy/value")
        else:
            print(f"  Transformer d_model: {policy_kwargs['features_extractor_kwargs'].get('d_model')}")
            print(f"  Transformer heads: {policy_kwargs['features_extractor_kwargs'].get('n_heads')}")
            print(f"  Transformer layers: {policy_kwargs['features_extractor_kwargs'].get('n_layers')}")
            print(f"  Transformer dropout: {policy_kwargs['features_extractor_kwargs'].get('dropout')}")
            print(f"  Positional encoding: {policy_kwargs['features_extractor_kwargs'].get('pos_encoding')}")
            print(f"  Pooling: {policy_kwargs['features_extractor_kwargs'].get('pooling')}")
            print("  Architecture: obs -> Transformer -> features -> LSTM -> policy/value")
        print(f"  LSTM hidden size: {policy_kwargs['lstm_hidden_size']}")
        print(f"  LSTM layers: {policy_kwargs['n_lstm_layers']}")
        print(f"  Critic LSTM: {policy_kwargs['enable_critic_lstm']}")

    elif policy in {"cnn", "cnn_attention", "cnn_window_attention", "multi_cnn", "transformer"}:
        if n_envs > 1:
            lookback_window = train_env.get_attr('lookback_window')[0]
        else:
            lookback_window = train_env.get_wrapper_attr('lookback_window')

        if policy == "multi_cnn":
            cfg_key = "multi_cnn"
            extractor_cls = StockMultiCNNExtractor
            section_name = "MULTI-CNN"
        elif policy == "cnn":
            cfg_key = "cnn"
            extractor_cls = StockClassicCNNExtractor
            section_name = "CNN"
        elif policy == "cnn_attention":
            cfg_key = "cnn_attention"
            extractor_cls = CNNAttentionExtractor
            section_name = "CNN-ATTENTION"
        elif policy == "cnn_window_attention":
            cfg_key = "cnn_window_attention"
            extractor_cls = CNNWindowAttentionExtractor
            section_name = "CNN-WINDOW-ATTENTION"
        else:
            cfg_key = "transformer"
            extractor_cls = StockTransformerExtractor
            section_name = "TRANSFORMER"
        policy_cfg = POLICY_CONFIGS[cfg_key]
        extractor_kwargs = dict(policy_cfg["policy_kwargs"].get("features_extractor_kwargs", {}))
        extractor_kwargs["lookback_window"] = lookback_window
        policy_kwargs = dict(
            features_extractor_class=extractor_cls,
            features_extractor_kwargs=extractor_kwargs,
            activation_fn=th.nn.ReLU,
            net_arch=dict(
                pi=policy_cfg["policy_kwargs"]["net_arch"]["pi"],
                vf=policy_cfg["policy_kwargs"]["net_arch"]["vf"],
            )
        )

        model = PPO(
            "MlpPolicy",
            train_env,
            policy_kwargs=policy_kwargs,
            verbose=1,
            learning_rate=policy_cfg["model_kwargs"]["learning_rate"],
            n_steps=policy_cfg["model_kwargs"]["n_steps"],
            batch_size=policy_cfg["model_kwargs"]["batch_size"],
            n_epochs=policy_cfg["model_kwargs"]["n_epochs"],
            gamma=policy_cfg["model_kwargs"]["gamma"],
            gae_lambda=policy_cfg["model_kwargs"]["gae_lambda"],
            clip_range=policy_cfg["model_kwargs"]["clip_range"],
            ent_coef=float(ent_coef_start),
            tensorboard_log=log_dir,
            device=device,
            seed=seed
        )

        print(f"\n{section_name} Configuration:")
        print(f"  Lookback window: {lookback_window}")
        print(f"  Embedding dim: {policy_kwargs['features_extractor_kwargs']['features_dim']}")
        if policy == "multi_cnn":
            print(f"  CNN windows: {policy_kwargs['features_extractor_kwargs'].get('multi_scale_windows')}")
            print(f"  CNN branch channels: {policy_kwargs['features_extractor_kwargs'].get('branch_channels')}")
            print("  Architecture: obs -> Multi-CNN -> features -> policy/value")
        elif policy == "cnn":
            print(f"  CNN batch norm: {policy_kwargs['features_extractor_kwargs'].get('use_batch_norm', False)}")
            print("  Architecture: obs -> CNN -> features -> policy/value")
        elif policy == "cnn_attention":
            print(f"  Window size: {policy_kwargs['features_extractor_kwargs'].get('window_size')}")
            print(f"  Window stride: {policy_kwargs['features_extractor_kwargs'].get('stride')}")
            print(f"  CNN channels: {policy_kwargs['features_extractor_kwargs'].get('cnn_channels')}")
            print(f"  Window embed dim: {policy_kwargs['features_extractor_kwargs'].get('embed_dim')}")
            print(f"  Transformer heads: {policy_kwargs['features_extractor_kwargs'].get('n_heads')}")
            print(f"  Transformer layers: {policy_kwargs['features_extractor_kwargs'].get('n_layers')}")
            print(f"  Transformer dropout: {policy_kwargs['features_extractor_kwargs'].get('dropout')}")
            print(f"  Pooling: {policy_kwargs['features_extractor_kwargs'].get('pooling')}")
            print("  Architecture: obs -> CNN -> windows -> attention -> features -> policy/value")
        elif policy == "cnn_window_attention":
            print(f"  Window size: {policy_kwargs['features_extractor_kwargs'].get('window_size')}")
            print(f"  Window stride: {policy_kwargs['features_extractor_kwargs'].get('stride')}")
            print(f"  CNN channels: {policy_kwargs['features_extractor_kwargs'].get('cnn_channels')}")
            print(f"  Window embed dim: {policy_kwargs['features_extractor_kwargs'].get('embed_dim')}")
            print(f"  Transformer heads: {policy_kwargs['features_extractor_kwargs'].get('n_heads')}")
            print(f"  Transformer layers: {policy_kwargs['features_extractor_kwargs'].get('n_layers')}")
            print(f"  Transformer dropout: {policy_kwargs['features_extractor_kwargs'].get('dropout')}")
            print(f"  Pooling: {policy_kwargs['features_extractor_kwargs'].get('pooling')}")
            print("  Architecture: obs -> CNN -> windows -> window-importance -> features -> policy/value")
        else:
            print(f"  Transformer d_model: {policy_kwargs['features_extractor_kwargs'].get('d_model')}")
            print(f"  Transformer heads: {policy_kwargs['features_extractor_kwargs'].get('n_heads')}")
            print(f"  Transformer layers: {policy_kwargs['features_extractor_kwargs'].get('n_layers')}")
            print(f"  Transformer dropout: {policy_kwargs['features_extractor_kwargs'].get('dropout')}")
            print(f"  Positional encoding: {policy_kwargs['features_extractor_kwargs'].get('pos_encoding')}")
            print(f"  Pooling: {policy_kwargs['features_extractor_kwargs'].get('pooling')}")
            print("  Architecture: obs -> Transformer -> features -> policy/value")
        print(f"  Policy net: {policy_kwargs['net_arch']['pi']}")
        print(f"  Value net: {policy_kwargs['net_arch']['vf']}")
    else:  # mlp
        # Standard MLP policy
        policy_cfg = POLICY_CONFIGS["mlp"]
        policy_kwargs = dict(
            activation_fn=th.nn.ReLU,
            net_arch={
                'pi': policy_cfg["policy_kwargs"]["net_arch"]["pi"],
                'vf': policy_cfg["policy_kwargs"]["net_arch"]["vf"],
            }
        )
        
        model = PPO(
            "MlpPolicy",
            train_env,
            policy_kwargs=policy_kwargs,
            verbose=1,
            learning_rate=policy_cfg["model_kwargs"]["learning_rate"],
            n_steps=policy_cfg["model_kwargs"]["n_steps"],
            batch_size=policy_cfg["model_kwargs"]["batch_size"],
            n_epochs=policy_cfg["model_kwargs"]["n_epochs"],
            gamma=policy_cfg["model_kwargs"]["gamma"],
            gae_lambda=policy_cfg["model_kwargs"]["gae_lambda"],
            clip_range=policy_cfg["model_kwargs"]["clip_range"],
            ent_coef=float(ent_coef_start),
            tensorboard_log=log_dir,
            device=device,  # GPU/CPU selection
            seed=seed
        )
        
        print("\nMLP Configuration:")
        print(f"  Policy net: {policy_kwargs['net_arch']['pi']}")
        print(f"  Value net: {policy_kwargs['net_arch']['vf']}")
    
    print("\nModel architecture:")
    print(model.policy)
    
    # Train the model
    print_training_start(
        log_dir=log_dir,
        run_dir=run_dir,
        checkpoints_dir=checkpoints_dir,
    )
    
    run_started_at_utc = datetime.now(timezone.utc)
    interrupted = False
    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=callbacks,
            progress_bar=True
        )
    except KeyboardInterrupt:
        interrupted = True
        print("\n\nTraining interrupted by user!")
    run_finished_at_utc = datetime.now(timezone.utc)
    full_training_duration_seconds = max(
        0.0, (run_finished_at_utc - run_started_at_utc).total_seconds()
    )
    
    # Save final model
    final_path = os.path.join(run_dir, "model_final")
    model.save(final_path)
    
    # Copy best model (if available) to a friendly name
    best_src = os.path.join(run_best_dir, "best_model.zip")
    best_dst = os.path.join(run_dir, "model_best.zip")
    best_meta_path = os.path.splitext(best_dst)[0] + "_meta.json"
    best_model_reached_at_utc = None
    best_model_time_to_reach_seconds = None
    best_generated_this_run = False
    if os.path.exists(best_src):
        try:
            best_model_reached_at_utc = datetime.fromtimestamp(
                os.path.getmtime(best_src), tz=timezone.utc
            )
            best_elapsed = (best_model_reached_at_utc - run_started_at_utc).total_seconds()
            best_model_time_to_reach_seconds = max(
                0.0, min(full_training_duration_seconds, best_elapsed)
            )
        except Exception:
            best_model_reached_at_utc = None
            best_model_time_to_reach_seconds = None
    if os.path.exists(best_src):
        shutil.copyfile(best_src, best_dst)
        best_generated_this_run = True
    else:
        if os.path.exists(best_dst):
            os.remove(best_dst)
        if os.path.exists(best_meta_path):
            os.remove(best_meta_path)
    
    # Save metadata for training context/configuration used by evaluation.
    run_mode = "all_stocks" if all_stocks else ("selected_stocks" if stocks else "single_stock")
    resolved_stocks = resolved_stocks_snapshot
    git_commit, git_is_dirty = _get_git_commit_info()
    env_config = env_config_snapshot
    observation_extra_state_dim = 3 if env_config["include_can_exit"] else 2

    meta_base = {
        "metadata_version": 2,
        "created_at_utc": run_finished_at_utc.isoformat(),
        "run_started_at_utc": run_started_at_utc.isoformat(),
        "run_finished_at_utc": run_finished_at_utc.isoformat(),
        "full_training_duration_seconds": float(full_training_duration_seconds),
        "best_model_selection_metric": "eval_mean_return_geometric",
        "best_model_reached_at_utc": (
            best_model_reached_at_utc.isoformat() if best_model_reached_at_utc else None
        ),
        "best_model_time_to_reach_seconds": (
            float(best_model_time_to_reach_seconds)
            if best_model_time_to_reach_seconds is not None
            else None
        ),
        "run_mode": run_mode,
        "stock": stock,
        "stocks": stocks or [],
        "all_stocks": all_stocks,
        "resolved_stocks": resolved_stocks or [],
        "policy": policy_display,
        "timesteps_requested": int(total_timesteps),
        "timesteps_completed": int(getattr(model, "num_timesteps", 0)),
        "observation_extra_state_dim": observation_extra_state_dim,
        "interrupted": interrupted,
        "n_envs": int(n_envs),
        "seed": int(seed) if seed is not None else None,
        "checkpoint_freq": int(checkpoint_freq),
        "eval_freq": int(eval_freq),
        "n_eval_episodes": int(n_eval_episodes),
        "ent_coef_start": float(ent_coef_start),
        "ent_coef_end": float(ent_coef_end),
        "ent_coef_schedule": ent_coef_schedule,
        "device": device,
        "cuda_available": bool(cuda_available),
        "git_commit": git_commit,
        "git_is_dirty": git_is_dirty,
        "data_dir": data_dir,
        "save_root_dir": save_root_dir,
        "save_dir": run_dir,
        "run_dir": run_dir,
        "checkpoints_dir": checkpoints_dir,
        "log_root_dir": log_root_dir,
        "log_dir": log_dir,
        "model_name": model_name,
        "model_final_path": f"{final_path}.zip",
        "model_best_path": best_dst if os.path.exists(best_dst) else None,
        "policy_config": _to_jsonable(POLICY_CONFIGS.get(policy, {})),
        "policy_kwargs": _to_jsonable(policy_kwargs),
        "environment_config": _to_jsonable(env_config),
        "train_defaults": _to_jsonable(TRAIN_DEFAULTS),
        # Metadata keys still used by the evaluation pipeline.
        "help_tickers": help_tickers or [],
        "market_data_dir": market_data_dir,
        "help_assets": help_assets or [],
        "help_assets_dir": help_assets_dir
    }

    meta_final = dict(meta_base)
    meta_final["artifact_type"] = "final"
    meta_final["training_duration_scope"] = "full_run"
    meta_final["training_duration_seconds"] = float(full_training_duration_seconds)

    meta_final_path = f"{final_path}_meta.json"
    with open(meta_final_path, "w", encoding="utf-8") as f:
        json.dump(meta_final, f, indent=2)

    if best_generated_this_run and os.path.exists(best_dst):
        meta_best = dict(meta_base)
        best_duration_seconds = (
            float(best_model_time_to_reach_seconds)
            if best_model_time_to_reach_seconds is not None
            else float(full_training_duration_seconds)
        )
        meta_best["artifact_type"] = "best"
        meta_best["training_duration_scope"] = "time_to_best"
        meta_best["training_duration_seconds"] = best_duration_seconds
        with open(best_meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_best, f, indent=2)
    shutil.rmtree(run_best_dir, ignore_errors=True)
    
    print_training_complete(
        final_path=final_path,
        best_dst=(best_dst if os.path.exists(best_dst) else None),
    )
    
    return model
