import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from typing import Optional, Tuple, List, Dict, Union
from abc import ABC, abstractmethod
import os
import warnings

from vn_stock_rl.config import DEFAULT_CONFIG
from vn_stock_rl.env.features import CALENDAR_FEATURES, ENGINEERED_FEATURE_FAMILIES, OHLCV_FIELDS, REWARD_BENCHMARKS


class BaseTradingEnv(gym.Env, ABC):
    """
    Base class for trading environments with shared functionality.
    
    Subclasses should implement:
    - _get_current_dataframe(): Returns the dataframe for the current step
    - _setup_data(): Sets up data loading and split calculation
    - _reset_episode_range(): Sets episode start/end indices based on mode
    """
    
    metadata = {'render_modes': ['human']}
    
    def __init__(
        self,
        mode: str = 'train',
        train_split: float = None,
        val_split: float = None,
        min_hold_days: int = None,
        buy_fee_rate: float = None,
        sell_fee_rate: float = None,
        capital_gains_tax_rate: float = None,
        stop_loss: float = None,
        lookback_window: int = None,
        reward_shaping: Optional[dict] = None,
        drawdown_penalty_enabled: Optional[bool] = None,
        drawdown_penalty_lambda: Optional[float] = None,
        drawdown_penalty_train_only: Optional[bool] = None,
        reward_benchmark: Optional[str] = None,
        benchmark_weight: Optional[float] = None,
        benchmark_relative_reward: Optional[bool] = None,
        train_episode_sampling: Optional[dict] = None,
        train_episode_sampling_enabled: Optional[bool] = None,
        train_episode_min_fraction: Optional[float] = None,
        train_episode_max_fraction: Optional[float] = None,
        start_episode_position: Optional[float] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        source_mode: Optional[str] = None,
        ohlcv: Optional[List[str]] = None,
        calendar_features: Optional[List[str]] = None,
        ma_windows: Optional[List[int]] = None,
        helpers_ma_windows: Optional[List[Union[int, str]]] = None,
        returns_windows: Optional[List[int]] = None,
        helpers_returns_windows: Optional[List[Union[int, str]]] = None,
        engineered_features: Optional[List[str]] = None,
        window_policy: Optional[str] = None,
        feature_windows: Optional[List[int]] = None,
        logspace_min: Optional[int] = None,
        logspace_max: Optional[int] = None,
        logspace_count: Optional[int] = None,
        rs_market_proxies: Optional[List[str]] = None,
        rs_include_long: Optional[bool] = None,
        include_can_exit: bool = True,
        help_tickers: Optional[List[str]] = None,
        market_data_dir: str = "data/stock/",
        help_assets: Optional[List[str]] = None,
        help_assets_dir: str = "data/fx-commodities/",
        news_feature_columns: Optional[List[str]] = None,
        news_prediction_dir: Optional[str] = None,
        signal_feature_columns: Optional[List[str]] = None,
        signal_prediction_dir: Optional[str] = None,
    ):
        super().__init__()
        
        # Use default config if not specified
        train_split = train_split if train_split is not None else DEFAULT_CONFIG['train_split']
        val_split = val_split if val_split is not None else DEFAULT_CONFIG['val_split']
        self.min_hold_days = min_hold_days if min_hold_days is not None else DEFAULT_CONFIG['min_hold_days']
        self.buy_fee_rate = buy_fee_rate if buy_fee_rate is not None else DEFAULT_CONFIG['buy_fee_rate']
        self.sell_fee_rate = sell_fee_rate if sell_fee_rate is not None else DEFAULT_CONFIG['sell_fee_rate']
        self.capital_gains_tax_rate = (
            capital_gains_tax_rate
            if capital_gains_tax_rate is not None
            else DEFAULT_CONFIG['capital_gains_tax_rate']
        )
        self.stop_loss = stop_loss if stop_loss is not None else DEFAULT_CONFIG['stop_loss']
        self.lookback_window = lookback_window if lookback_window is not None else DEFAULT_CONFIG['lookback_window']
        self.sample_start_date = self._normalize_date_bound(start_date, "start_date")
        self.sample_end_date = self._normalize_date_bound(end_date, "end_date")
        if self.sample_start_date is not None and self.sample_end_date is not None:
            if self.sample_start_date > self.sample_end_date:
                raise ValueError(
                    f"start_date must be <= end_date, got {self.sample_start_date.date()} > {self.sample_end_date.date()}"
                )

        reward_shaping_cfg = DEFAULT_CONFIG.get("reward_shaping", {})
        if reward_shaping_cfg is None:
            reward_shaping_cfg = {}
        if not isinstance(reward_shaping_cfg, dict):
            raise ValueError("DEFAULT_CONFIG['reward_shaping'] must be a dict when provided")
        if reward_shaping is None:
            reward_shaping = {}
        if not isinstance(reward_shaping, dict):
            raise ValueError("reward_shaping must be a dict when provided")
        drawdown_cfg_default = reward_shaping_cfg.get("drawdown_penalty", {})
        if drawdown_cfg_default is None:
            drawdown_cfg_default = {}
        if not isinstance(drawdown_cfg_default, dict):
            raise ValueError("DEFAULT_CONFIG['reward_shaping']['drawdown_penalty'] must be a dict when provided")
        drawdown_cfg = reward_shaping.get("drawdown_penalty", {})
        if drawdown_cfg is None:
            drawdown_cfg = {}
        if not isinstance(drawdown_cfg, dict):
            raise ValueError("reward_shaping['drawdown_penalty'] must be a dict when provided")

        enabled_default = drawdown_cfg.get("enabled", drawdown_cfg_default.get("enabled", True))
        lambda_default = drawdown_cfg.get("lambda", drawdown_cfg_default.get("lambda", 0.05))
        train_only_default = drawdown_cfg.get("train_only", drawdown_cfg_default.get("train_only", True))
        self.drawdown_penalty_enabled = (
            bool(drawdown_penalty_enabled)
            if drawdown_penalty_enabled is not None
            else bool(enabled_default)
        )
        self.drawdown_penalty_lambda = (
            float(drawdown_penalty_lambda)
            if drawdown_penalty_lambda is not None
            else float(lambda_default)
        )
        if self.drawdown_penalty_lambda < 0.0:
            raise ValueError(f"drawdown_penalty_lambda must be >= 0.0, got {self.drawdown_penalty_lambda}")
        self.drawdown_penalty_train_only = (
            bool(drawdown_penalty_train_only)
            if drawdown_penalty_train_only is not None
            else bool(train_only_default)
        )
        benchmark_cfg_default = reward_shaping_cfg.get("benchmark_relative", {})
        if benchmark_cfg_default is None:
            benchmark_cfg_default = {}
        if not isinstance(benchmark_cfg_default, dict):
            raise ValueError("DEFAULT_CONFIG['reward_shaping']['benchmark_relative'] must be a dict when provided")
        benchmark_cfg = reward_shaping.get("benchmark_relative", {})
        if benchmark_cfg is None:
            benchmark_cfg = {}
        if not isinstance(benchmark_cfg, dict):
            raise ValueError("reward_shaping['benchmark_relative'] must be a dict when provided")

        benchmark_enabled_default = benchmark_cfg.get(
            "enabled",
            benchmark_cfg_default.get("enabled", False),
        )
        benchmark_name_default = str(
            benchmark_cfg.get(
                "benchmark",
                benchmark_cfg_default.get("benchmark", REWARD_BENCHMARKS[0]),
            )
        ).strip().lower()
        benchmark_weight_default = benchmark_cfg.get(
            "weight",
            benchmark_cfg_default.get("weight", 1.0),
        )
        self.benchmark_relative_reward_enabled = (
            bool(benchmark_relative_reward)
            if benchmark_relative_reward is not None
            else bool(benchmark_enabled_default)
        )
        resolved_reward_benchmark = (
            str(reward_benchmark).strip().lower()
            if reward_benchmark is not None
            else benchmark_name_default
        )
        if resolved_reward_benchmark not in REWARD_BENCHMARKS:
            raise ValueError(
                f"reward_benchmark must be one of {list(REWARD_BENCHMARKS)}, got {resolved_reward_benchmark!r}"
            )
        self.reward_benchmark = resolved_reward_benchmark
        self.benchmark_weight = (
            float(benchmark_weight)
            if benchmark_weight is not None
            else float(benchmark_weight_default)
        )
        if self.benchmark_weight < 0.0:
            raise ValueError(f"benchmark_weight must be >= 0.0, got {self.benchmark_weight}")
        self.reward_shaping = {
            "drawdown_penalty": {
                "enabled": bool(self.drawdown_penalty_enabled),
                "lambda": float(self.drawdown_penalty_lambda),
                "train_only": bool(self.drawdown_penalty_train_only),
            },
            "benchmark_relative": {
                "enabled": bool(self.benchmark_relative_reward_enabled),
                "benchmark": self.reward_benchmark,
                "weight": float(self.benchmark_weight),
            },
        }

        train_episode_sampling_cfg = DEFAULT_CONFIG.get("train_episode_sampling", {})
        if train_episode_sampling_cfg is None:
            train_episode_sampling_cfg = {}
        if not isinstance(train_episode_sampling_cfg, dict):
            raise ValueError("DEFAULT_CONFIG['train_episode_sampling'] must be a dict when provided")
        if train_episode_sampling is None:
            train_episode_sampling = {}
        if not isinstance(train_episode_sampling, dict):
            raise ValueError("train_episode_sampling must be a dict when provided")
        sampling_mode = str(
            train_episode_sampling.get(
                "mode",
                train_episode_sampling_cfg.get("mode", "fraction"),
            )
        ).strip().lower()
        if sampling_mode != "fraction":
            raise ValueError(f"Unsupported train_episode_sampling.mode '{sampling_mode}'. Only 'fraction' is supported.")
        enabled_cfg = train_episode_sampling.get(
            "enabled",
            train_episode_sampling_cfg.get("enabled", True),
        )
        self.train_episode_sampling_enabled = (
            bool(train_episode_sampling_enabled)
            if train_episode_sampling_enabled is not None
            else bool(enabled_cfg)
        )
        min_frac_cfg = train_episode_sampling.get(
            "min_fraction",
            train_episode_sampling_cfg.get("min_fraction", 0.2),
        )
        max_frac_cfg = train_episode_sampling.get(
            "max_fraction",
            train_episode_sampling_cfg.get("max_fraction", 0.6),
        )
        self.train_episode_min_fraction = (
            float(train_episode_min_fraction)
            if train_episode_min_fraction is not None
            else float(min_frac_cfg)
        )
        self.train_episode_max_fraction = (
            float(train_episode_max_fraction)
            if train_episode_max_fraction is not None
            else float(max_frac_cfg)
        )
        if not (0.0 < self.train_episode_min_fraction <= 1.0):
            raise ValueError(
                f"train_episode_min_fraction must be in (0,1], got {self.train_episode_min_fraction}"
            )
        if not (0.0 < self.train_episode_max_fraction <= 1.0):
            raise ValueError(
                f"train_episode_max_fraction must be in (0,1], got {self.train_episode_max_fraction}"
            )
        if self.train_episode_min_fraction > self.train_episode_max_fraction:
            raise ValueError(
                "train_episode_min_fraction must be <= train_episode_max_fraction, got "
                f"{self.train_episode_min_fraction} > {self.train_episode_max_fraction}"
            )
        self.train_episode_sampling_mode = sampling_mode
        start_pos_cfg = DEFAULT_CONFIG.get("start_episode_position", 0.0)
        self.start_episode_position = (
            float(start_episode_position) if start_episode_position is not None else float(start_pos_cfg)
        )
        if not (0.0 <= self.start_episode_position <= 1.0):
            raise ValueError(
                f"start_episode_position must be in [0,1], got {self.start_episode_position}"
            )

        input_features_cfg = DEFAULT_CONFIG.get("input_features", {})
        if input_features_cfg is None:
            input_features_cfg = {}
        if not isinstance(input_features_cfg, dict):
            raise ValueError("DEFAULT_CONFIG['input_features'] must be a dict when provided")

        if ohlcv is None:
            ohlcv = input_features_cfg.get("ohlcv", list(OHLCV_FIELDS))
        if ohlcv is None:
            ohlcv = list(OHLCV_FIELDS)
        if not isinstance(ohlcv, (list, tuple)) or len(ohlcv) == 0:
            raise ValueError(f"ohlcv must be a non-empty list/tuple of fields, got {ohlcv}")
        seen_ohlcv = set()
        for field in ohlcv:
            field_name = str(field).strip().lower()
            if field_name not in OHLCV_FIELDS:
                raise ValueError(f"Unsupported ohlcv field '{field_name}'. Allowed: {list(OHLCV_FIELDS)}")
            seen_ohlcv.add(field_name)
        if not seen_ohlcv:
            raise ValueError("At least one OHLCV field must be enabled")
        self.ohlcv_fields = [field for field in OHLCV_FIELDS if field in seen_ohlcv]
        self.base_feature_dim = len(self.ohlcv_fields)

        if calendar_features is None:
            calendar_features = input_features_cfg.get("calendar", [])
        if calendar_features is None:
            calendar_features = []
        if not isinstance(calendar_features, (list, tuple)):
            raise ValueError(
                f"calendar_features must be a list/tuple of {list(CALENDAR_FEATURES)}, got {calendar_features}"
            )
        seen_calendar = set()
        for feature in calendar_features:
            feature_name = str(feature).strip().lower()
            if feature_name not in CALENDAR_FEATURES:
                raise ValueError(
                    f"Unsupported calendar feature '{feature_name}'. Allowed: {list(CALENDAR_FEATURES)}"
                )
            seen_calendar.add(feature_name)
        self.calendar_features = [feature for feature in CALENDAR_FEATURES if feature in seen_calendar]
        self.calendar_feature_dim = 2 * len(self.calendar_features)

        cfg_source_mode = input_features_cfg.get("source_mode")

        if source_mode is None:
            if cfg_source_mode is not None:
                source_mode = str(cfg_source_mode).strip().lower()
            else:
                source_mode = "return"
        else:
            source_mode = str(source_mode).strip().lower()

        if source_mode not in {"raw", "return"}:
            raise ValueError(f"source_mode must be 'raw' or 'return', got {source_mode}")
        self.source_mode = source_mode
        # Kept as a derived attribute for evaluation stats and older tests.
        self.normalize = self.source_mode == "return"

        configured_ma_windows = ma_windows
        if configured_ma_windows is None:
            configured_ma_windows = input_features_cfg.get("ma_windows")
        if configured_ma_windows is None:
            configured_ma_windows = []
        self.ma_windows = self._resolve_ma_windows(configured_ma_windows, "ma_windows")
        self.ma_feature_count = len(self.ma_windows)

        configured_helpers_ma_windows = helpers_ma_windows
        if configured_helpers_ma_windows is None:
            configured_helpers_ma_windows = input_features_cfg.get("helpers_ma_windows")
        self.helpers_ma_windows, self.helpers_ma_windows_cfg = self._resolve_helpers_ma_windows(
            configured_helpers_ma_windows
        )
        self.helpers_ma_feature_count = len(self.helpers_ma_windows)

        configured_returns_windows = returns_windows
        if configured_returns_windows is None:
            configured_returns_windows = input_features_cfg.get("returns_windows")
        self.returns_windows = self._resolve_ma_windows(configured_returns_windows, "returns_windows")
        self.returns_feature_count = len(self.returns_windows)

        configured_helpers_returns_windows = helpers_returns_windows
        if configured_helpers_returns_windows is None:
            configured_helpers_returns_windows = input_features_cfg.get("helpers_returns_windows")
        self.helpers_returns_windows, self.helpers_returns_windows_cfg = self._resolve_helpers_ma_windows(
            configured_helpers_returns_windows,
            target_windows=self.returns_windows,
            field_name="helpers_returns_windows",
        )
        self.helpers_returns_feature_count = len(self.helpers_returns_windows)

        engineered_cfg = input_features_cfg.get("engineered_features", {})
        if engineered_cfg is None:
            engineered_cfg = {}
        if not isinstance(engineered_cfg, dict):
            raise ValueError("input_features.engineered_features must be a dict when provided")

        configured_engineered = engineered_features
        if configured_engineered is None:
            configured_engineered = engineered_cfg.get("enabled", [])
        if configured_engineered is None:
            configured_engineered = []
        if not isinstance(configured_engineered, (list, tuple)):
            raise ValueError(
                f"engineered_features must be a list/tuple of {list(ENGINEERED_FEATURE_FAMILIES)}, got {configured_engineered}"
            )
        seen_engineered = set()
        for family in configured_engineered:
            family_name = str(family).strip().lower()
            if family_name not in ENGINEERED_FEATURE_FAMILIES:
                raise ValueError(
                    f"Unsupported engineered feature family '{family_name}'. Allowed: {list(ENGINEERED_FEATURE_FAMILIES)}"
                )
            seen_engineered.add(family_name)
        self.engineered_feature_families = [
            family for family in ENGINEERED_FEATURE_FAMILIES if family in seen_engineered
        ]

        window_policy_cfg = engineered_cfg.get("window_policy", {}) if isinstance(engineered_cfg, dict) else {}
        if window_policy_cfg is None:
            window_policy_cfg = {}
        if not isinstance(window_policy_cfg, dict):
            raise ValueError("input_features.engineered_features.window_policy must be a dict when provided")
        resolved_window_policy = (
            str(window_policy).strip().lower()
            if window_policy is not None
            else str(window_policy_cfg.get("mode", "logspace")).strip().lower()
        )
        if resolved_window_policy not in {"explicit", "logspace"}:
            raise ValueError(f"window_policy must be 'explicit' or 'logspace', got {resolved_window_policy}")

        explicit_windows_cfg = feature_windows if feature_windows is not None else window_policy_cfg.get("explicit_windows")
        logspace_min_cfg = logspace_min if logspace_min is not None else window_policy_cfg.get("logspace_min", 5)
        logspace_max_cfg = logspace_max if logspace_max is not None else window_policy_cfg.get("logspace_max", 80)
        logspace_count_cfg = logspace_count if logspace_count is not None else window_policy_cfg.get("logspace_count", 5)
        self.engineered_window_policy = resolved_window_policy
        self.engineered_feature_windows = self._resolve_engineered_windows(
            self.engineered_window_policy,
            explicit_windows_cfg,
            logspace_min_cfg,
            logspace_max_cfg,
            logspace_count_cfg,
            self.lookback_window,
            bool(self.engineered_feature_families),
        )

        horizons_cfg = engineered_cfg.get("horizons", {}) if isinstance(engineered_cfg, dict) else {}
        if horizons_cfg is None:
            horizons_cfg = {}
        if not isinstance(horizons_cfg, dict):
            raise ValueError("input_features.engineered_features.horizons must be a dict when provided")
        medium_idx_raw = int(horizons_cfg.get("medium_index", 2))
        long_idx_raw = int(horizons_cfg.get("long_index", 4))
        if medium_idx_raw < 0 or long_idx_raw < 0:
            raise ValueError(
                f"engineered horizon indices must be >= 0, got medium_index={medium_idx_raw}, long_index={long_idx_raw}"
            )

        if self.engineered_feature_families and self.engineered_feature_windows:
            max_idx = len(self.engineered_feature_windows) - 1
            medium_idx = min(medium_idx_raw, max_idx)
            long_idx = min(long_idx_raw, max_idx)
            if medium_idx != medium_idx_raw or long_idx != long_idx_raw:
                warnings.warn(
                    "Engineered horizon index exceeds resolved windows after lookback clamp; "
                    f"using medium_index={medium_idx}, long_index={long_idx} from "
                    f"windows={self.engineered_feature_windows}.",
                    stacklevel=2,
                )
            self.engineered_medium_window = self.engineered_feature_windows[medium_idx]
            self.engineered_long_window = self.engineered_feature_windows[long_idx]
        else:
            # No engineered families enabled: keep resolved windows metadata, but horizons are inactive.
            medium_idx = medium_idx_raw
            long_idx = long_idx_raw
            self.engineered_medium_window = None
            self.engineered_long_window = None

        self.engineered_horizons = {
            "medium_index": medium_idx,
            "long_index": long_idx,
        }

        rs_cfg = engineered_cfg.get("relative_strength", {}) if isinstance(engineered_cfg, dict) else {}
        if rs_cfg is None:
            rs_cfg = {}
        if not isinstance(rs_cfg, dict):
            raise ValueError("input_features.engineered_features.relative_strength must be a dict when provided")
        configured_proxies = rs_market_proxies if rs_market_proxies is not None else rs_cfg.get(
            "market_proxy_preference",
            ["VNINDEX", "VN30"],
        )
        if configured_proxies is None:
            configured_proxies = []
        if not isinstance(configured_proxies, (list, tuple)):
            raise ValueError(f"rs_market_proxies must be a list/tuple, got {configured_proxies}")
        self.rs_market_proxies = [str(x).strip().upper() for x in configured_proxies if str(x).strip()]
        if not self.rs_market_proxies:
            self.rs_market_proxies = ["VNINDEX", "VN30"]
        self.rs_include_long = (
            bool(rs_include_long)
            if rs_include_long is not None
            else bool(rs_cfg.get("include_long_horizon", True))
        )

        self.engineered_feature_names = self._resolve_engineered_feature_names(
            self.engineered_feature_families,
            self.rs_include_long,
        )
        self.engineered_feature_dim = len(self.engineered_feature_names)
        self.news_feature_names, self.news_prediction_dir = self._resolve_news_feature_config(
            news_feature_columns,
            news_prediction_dir,
        )
        self.news_feature_dim = len(self.news_feature_names)
        self.signal_feature_names, self.signal_prediction_dir = self._resolve_signal_feature_config(
            signal_feature_columns,
            signal_prediction_dir,
        )
        self.signal_feature_dim = len(self.signal_feature_names)

        self.input_features = {
            "source_mode": self.source_mode,
            "ohlcv": list(self.ohlcv_fields),
            "ma_windows": list(self.ma_windows),
            "helpers_ma_windows": list(self.helpers_ma_windows_cfg),
            "returns_windows": list(self.returns_windows),
            "helpers_returns_windows": list(self.helpers_returns_windows_cfg),
            "train_episode_sampling": {
                "enabled": bool(self.train_episode_sampling_enabled),
                "mode": self.train_episode_sampling_mode,
                "min_fraction": float(self.train_episode_min_fraction),
                "max_fraction": float(self.train_episode_max_fraction),
            },
            "start_episode_position": float(self.start_episode_position),
            "sample_start_date": (
                self.sample_start_date.strftime("%Y-%m-%d") if self.sample_start_date is not None else None
            ),
            "sample_end_date": (
                self.sample_end_date.strftime("%Y-%m-%d") if self.sample_end_date is not None else None
            ),
            "reward_shaping": {
                "drawdown_penalty": {
                    "enabled": bool(self.drawdown_penalty_enabled),
                    "lambda": float(self.drawdown_penalty_lambda),
                    "train_only": bool(self.drawdown_penalty_train_only),
                },
                "benchmark_relative": {
                    "enabled": bool(self.benchmark_relative_reward_enabled),
                    "benchmark": self.reward_benchmark,
                    "weight": float(self.benchmark_weight),
                },
            },
            "calendar": list(self.calendar_features),
            "calendar_encoding": "sincos",
            "news_features": {
                "columns": list(self.news_feature_names),
                "prediction_dir": self.news_prediction_dir,
            },
            "signal_features": {
                "columns": list(self.signal_feature_names),
                "prediction_dir": self.signal_prediction_dir,
            },
            "engineered_features": {
                "enabled": list(self.engineered_feature_families),
                "window_policy": {
                    "mode": self.engineered_window_policy,
                    "explicit_windows": list(self.engineered_feature_windows),
                    "logspace_min": int(logspace_min_cfg),
                    "logspace_max": int(logspace_max_cfg),
                    "logspace_count": int(logspace_count_cfg),
                },
                "horizons": dict(self.engineered_horizons),
                "relative_strength": {
                    "market_proxy_preference": list(self.rs_market_proxies),
                    "include_long_horizon": bool(self.rs_include_long),
                },
                "resolved_feature_names": list(self.engineered_feature_names),
                "resolved_windows": list(self.engineered_feature_windows),
                "resolved_medium_window": self.engineered_medium_window,
                "resolved_long_window": self.engineered_long_window,
            },
        }
        self.include_can_exit = bool(include_can_exit)
        self.help_tickers = [t.upper() for t in help_tickers] if help_tickers else None
        self.market_data_dir = market_data_dir
        self.help_assets = [a.lower() for a in help_assets] if help_assets else None
        self.help_assets_dir = help_assets_dir
        self.market_feature_count = 0
        self.asset_feature_count = 0
        self.market_ma_feature_count = 0
        self.asset_ma_feature_count = 0
        self.market_returns_feature_count = 0
        self.asset_returns_feature_count = 0
        
        self.mode = mode
        self.train_split = train_split
        self.val_split = val_split
        
        # Setup data (implemented by subclasses)
        self._setup_data()
        
        # Return-based normalization doesn't need statistics
        if self.normalize:
            self._fit_normalizer()
        
        # State: [past_features(lookback_window * D), helper_features, ma_features, pos, count, can_exit]
        self.n_features = self.lookback_window * (
            self.base_feature_dim
            + self.market_feature_count
            + self.asset_feature_count
            + self.ma_feature_count
            + self.market_ma_feature_count
            + self.asset_ma_feature_count
            + self.returns_feature_count
            + self.market_returns_feature_count
            + self.asset_returns_feature_count
            + self.engineered_feature_dim
            + self.news_feature_dim
            + self.signal_feature_dim
            + self.calendar_feature_dim
        )
        
        # Action space: 0 = flat, 1 = long
        self.action_space = spaces.Discrete(2)
        
        # Observation space: continuous features + position state
        extra_state_dim = 3 if self.include_can_exit else 2
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.n_features + extra_state_dim,),
            dtype=np.float32
        )
        
        # Episode state
        self.current_step = 0
        self.position = 0  # 0 = flat, 1 = long (current active position)
        self.hold_count = 0
        self.entry_price = None
        self.pending_action = 0
        self.start_in_position = False
        self.synthetic_entry_idx = None
        self.synthetic_entry_price = None
        
        # Tracking
        self.episode_trades = []
        self.episode_rewards = []
        self.episode_start_idx = 0
        self.episode_end_idx = 0
        self.peak_equity = 1.0
        self.last_raw_return = 0.0
        self.last_benchmark_return = 0.0
        self.last_excess_return = 0.0
        self.last_drawdown = 0.0
        self.last_drawdown_penalty = 0.0
    
    @abstractmethod
    def _setup_data(self):
        """Setup data loading and split calculation. Implemented by subclasses."""
        pass
    
    @abstractmethod
    def _get_current_dataframe(self) -> pd.DataFrame:
        """Returns the dataframe for the current step. Implemented by subclasses."""
        pass
    
    @abstractmethod
    def _reset_episode_range(self):
        """Sets episode_start_idx and episode_end_idx based on mode. Implemented by subclasses."""
        pass
    
    def _fit_normalizer(self):
        """No-op for return-based normalization (no statistics needed)."""
        pass

    @staticmethod
    def _resolve_ma_windows(
        configured_windows: Optional[List[Union[int, str]]],
        field_name: str,
    ) -> List[int]:
        if configured_windows is None:
            configured_windows = []
        if not isinstance(configured_windows, (list, tuple)):
            raise ValueError(f"{field_name} must be a list/tuple, got {configured_windows}")
        resolved = []
        seen_windows = set()
        for window in configured_windows:
            window_int = int(window)
            if window_int <= 0:
                raise ValueError(f"{field_name} must contain positive integers, got {configured_windows}")
            if window_int in seen_windows:
                continue
            seen_windows.add(window_int)
            resolved.append(window_int)
        return resolved

    def _resolve_helpers_ma_windows(
        self,
        configured_windows: Optional[List[Union[int, str]]],
        target_windows: Optional[List[int]] = None,
        field_name: str = "helpers_ma_windows",
    ) -> Tuple[List[int], List[Union[int, str]]]:
        if configured_windows is None:
            configured_windows = []
        if not isinstance(configured_windows, (list, tuple)):
            raise ValueError(f"{field_name} must be a list/tuple, got {configured_windows}")
        if target_windows is None:
            target_windows = self.ma_windows
        tokens = [str(item).strip().lower() for item in configured_windows]
        if "same" in tokens:
            if len(tokens) != 1:
                raise ValueError(f"{field_name} cannot mix 'same' with explicit windows")
            return list(target_windows), ["same"]
        resolved = self._resolve_ma_windows(list(configured_windows), field_name)
        return resolved, list(resolved)

    @staticmethod
    def _resolve_engineered_windows(
        mode: str,
        explicit_windows,
        logspace_min,
        logspace_max,
        logspace_count,
        lookback_window: int,
        require_nonempty: bool,
    ) -> List[int]:
        if mode == "explicit":
            windows = BaseTradingEnv._resolve_ma_windows(explicit_windows, "feature_windows")
        else:
            lmin = int(logspace_min)
            lmax = int(logspace_max)
            lcount = int(logspace_count)
            if lmin <= 0 or lmax <= 0 or lcount <= 0:
                raise ValueError(
                    f"logspace params must be positive: min={lmin}, max={lmax}, count={lcount}"
                )
            if lmin > lmax:
                raise ValueError(f"logspace_min must be <= logspace_max, got {lmin} > {lmax}")
            raw = np.logspace(np.log10(lmin), np.log10(lmax), num=lcount)
            windows = BaseTradingEnv._resolve_ma_windows(np.round(raw).astype(int).tolist(), "feature_windows")

        windows = [w for w in windows if w <= int(lookback_window)]
        if require_nonempty and not windows:
            raise ValueError(
                f"No engineered feature windows remain after clamping to lookback_window={lookback_window}"
            )
        return windows

    @staticmethod
    def _resolve_engineered_feature_names(
        engineered_families: List[str],
        rs_include_long: bool,
    ) -> List[str]:
        names: List[str] = []
        if "volatility" in engineered_families:
            names.extend(["vol_medium", "vol_long"])
        if "trend" in engineered_families:
            names.extend(["dist_ma_medium", "dist_ma_long", "slope_ma_medium", "slope_ma_long"])
        if "momentum" in engineered_families:
            names.extend(["mom_medium", "mom_long"])
        if "volume_context" in engineered_families:
            names.append("vol_ratio_medium")
        if "drawdown" in engineered_families:
            names.append("dd_long")
        if "relative_strength" in engineered_families:
            names.append("rs_medium")
            if rs_include_long:
                names.append("rs_long")
        return names

    @staticmethod
    def _compute_pretrim_ma_frame_for_windows(df: pd.DataFrame, ma_windows: List[int]) -> pd.DataFrame:
        """Compute MA and MA-returns on the untrimmed close series for selected windows."""
        out = pd.DataFrame({"time": df["time"].to_numpy(copy=True)})
        if not ma_windows:
            return out

        close_arr = df["close"].to_numpy(dtype=np.float64)
        prev_close_for_norm = close_arr[:-1].copy()
        prev_close_for_norm[prev_close_for_norm == 0] = 1.0

        for window in ma_windows:
            ma_column = (
                pd.Series(close_arr)
                .rolling(window=window, min_periods=1)
                .mean()
                .to_numpy(dtype=np.float64)
            )
            ma_ret = np.zeros_like(ma_column, dtype=np.float64)
            if len(ma_column) > 1:
                ma_ret[1:] = (ma_column[1:] / prev_close_for_norm) - 1.0
            out[f"ma_{window}"] = ma_column
            out[f"ma_ret_{window}"] = ma_ret
        return out

    def _compute_pretrim_ma_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute MA and MA-returns on the untrimmed base series."""
        return self._compute_pretrim_ma_frame_for_windows(df, self.ma_windows)

    @staticmethod
    def _normalize_date_bound(value: Optional[str], field_name: str) -> Optional[pd.Timestamp]:
        if value is None:
            return None
        try:
            timestamp = pd.Timestamp(value)
        except Exception as exc:
            raise ValueError(f"{field_name} must be a valid date-like value, got {value!r}") from exc
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_localize(None)
        return timestamp.normalize()

    def _filter_df_by_sample_dates(self, df: pd.DataFrame, context: str) -> pd.DataFrame:
        if self.sample_start_date is None and self.sample_end_date is None:
            return df
        if "time" not in df.columns:
            raise ValueError(f"{context} is missing required 'time' column for date filtering")
        if pd.api.types.is_numeric_dtype(df["time"]):
            raise ValueError(
                f"{context} uses numeric 'time' values; start_date/end_date filtering requires datetime-like timestamps"
            )

        time_values = pd.to_datetime(df["time"], errors="coerce")
        if time_values.isna().any():
            raise ValueError(f"{context} contains non-datetime 'time' values and cannot be date-filtered")
        if getattr(time_values.dt, "tz", None) is not None:
            time_values = time_values.dt.tz_localize(None)

        mask = pd.Series(True, index=df.index)
        if self.sample_start_date is not None:
            mask &= time_values >= self.sample_start_date
        if self.sample_end_date is not None:
            mask &= time_values <= self.sample_end_date

        filtered = df.loc[mask].sort_values("time").reset_index(drop=True)
        if filtered.empty:
            bounds = []
            if self.sample_start_date is not None:
                bounds.append(f"start_date={self.sample_start_date.strftime('%Y-%m-%d')}")
            if self.sample_end_date is not None:
                bounds.append(f"end_date={self.sample_end_date.strftime('%Y-%m-%d')}")
            raise ValueError(f"{context} has no rows after applying date filter ({', '.join(bounds)})")
        return filtered

    @staticmethod
    def _resolve_news_feature_config(
        configured_columns: Optional[List[str]],
        prediction_dir: Optional[str],
    ) -> Tuple[List[str], Optional[str]]:
        from vn_stock_rl.external_features import resolve_news_feature_config

        return resolve_news_feature_config(configured_columns, prediction_dir)

    @staticmethod
    def _resolve_signal_feature_config(
        configured_columns: Optional[List[str]],
        prediction_dir: Optional[str],
    ) -> Tuple[List[str], Optional[str]]:
        from vn_stock_rl.external_features import resolve_signal_feature_config

        return resolve_signal_feature_config(configured_columns, prediction_dir)

    @staticmethod
    def _infer_ticker_from_data_path(data_path: str) -> str:
        base_name = os.path.basename(str(data_path)).replace(".parquet", "")
        if "gia_lich_su_" in base_name and "_1D" in base_name:
            return base_name.replace("gia_lich_su_", "").replace("_1D", "")
        return base_name

    def _merge_news_features_for_ticker(self, base_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        if not self.news_feature_names:
            return base_df

        from pathlib import Path

        from vn_stock_rl.external_features import merge_news_features

        merged = merge_news_features(
            base_df=base_df,
            ticker=ticker,
            prediction_dir=(Path(self.news_prediction_dir) if self.news_prediction_dir else None),
            include_columns=self.news_feature_names,
        )
        return merged.drop(columns=["date"], errors="ignore")

    @staticmethod
    def _signal_fill_value_for_column(column: str) -> float:
        from vn_stock_rl.external_features import signal_fill_value_for_column

        return signal_fill_value_for_column(column)

    def _merge_signal_features_for_ticker(self, base_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        if not self.signal_feature_names:
            return base_df

        from pathlib import Path

        from vn_stock_rl.external_features import merge_signal_features

        merged = merge_signal_features(
            base_df=base_df,
            ticker=ticker,
            prediction_dir=(Path(self.signal_prediction_dir) if self.signal_prediction_dir else None),
        )
        for column in self.signal_feature_names:
            fill_value = self._signal_fill_value_for_column(column)
            if column not in merged.columns:
                merged[column] = fill_value
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(fill_value)
        return merged.drop(columns=["date"], errors="ignore")

    @staticmethod
    def _compute_pretrim_window_returns_frame_for_windows(
        df: pd.DataFrame,
        returns_windows: List[int],
    ) -> pd.DataFrame:
        """Compute close-based window returns on untrimmed series for selected windows."""
        out = pd.DataFrame({"time": df["time"].to_numpy(copy=True)})
        if not returns_windows:
            return out

        close_arr = df["close"].to_numpy(dtype=np.float64)
        n = len(close_arr)
        for window in returns_windows:
            values = np.zeros(n, dtype=np.float64)
            if n > window:
                prev = close_arr[:-window].copy()
                prev[prev == 0] = 1.0
                values[window:] = (close_arr[window:] / prev) - 1.0
            out[f"ret_{window}"] = values
        return out

    @staticmethod
    def _compute_pretrim_market_momentum_frame_for_windows(
        df: pd.DataFrame,
        medium_window: int,
        long_window: int,
        include_long: bool,
    ) -> pd.DataFrame:
        out = pd.DataFrame({"time": df["time"].to_numpy(copy=True)})
        close_arr = df["close"].to_numpy(dtype=np.float64)
        mom_medium = np.zeros(len(close_arr), dtype=np.float64)
        if len(close_arr) > medium_window:
            prev = close_arr[:-medium_window].copy()
            prev[prev == 0] = 1.0
            mom_medium[medium_window:] = (close_arr[medium_window:] / prev) - 1.0
        out["mom_medium_market"] = mom_medium

        if include_long:
            mom_long = np.zeros(len(close_arr), dtype=np.float64)
            if len(close_arr) > long_window:
                prev = close_arr[:-long_window].copy()
                prev[prev == 0] = 1.0
                mom_long[long_window:] = (close_arr[long_window:] / prev) - 1.0
            out["mom_long_market"] = mom_long
        return out

    def _load_market_proxy_pretrim_momentum_frame(self) -> Optional[pd.DataFrame]:
        if "relative_strength" not in self.engineered_feature_families:
            return None
        if self.engineered_medium_window is None or self.engineered_long_window is None:
            raise ValueError("Engineered windows are not resolved for relative strength")

        for ticker in self.rs_market_proxies:
            filename = f"gia_lich_su_{ticker}_1D.parquet"
            path = os.path.join(self.market_data_dir, filename)
            if not os.path.exists(path):
                continue
            proxy_df = pd.read_parquet(path).sort_values("time").reset_index(drop=True)
            if "time" not in proxy_df.columns or "close" not in proxy_df.columns:
                raise ValueError(f"Market proxy file missing required columns (time/close): {path}")
            return self._compute_pretrim_market_momentum_frame_for_windows(
                proxy_df,
                self.engineered_medium_window,
                self.engineered_long_window,
                self.rs_include_long,
            )

        raise ValueError(
            "Relative strength enabled but no market proxy found. "
            f"Tried: {self.rs_market_proxies} in {self.market_data_dir}"
        )

    def _compute_pretrim_engineered_frame(
        self,
        df: pd.DataFrame,
        market_momentum_frame: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        out = pd.DataFrame({"time": df["time"].to_numpy(copy=True)})
        if self.engineered_feature_dim == 0:
            return out
        if self.engineered_medium_window is None or self.engineered_long_window is None:
            raise ValueError("Engineered windows are not resolved")

        close_arr = df["close"].to_numpy(dtype=np.float64)
        volume_arr = df["volume"].to_numpy(dtype=np.float64)
        n = len(close_arr)
        w_m = int(self.engineered_medium_window)
        w_l = int(self.engineered_long_window)

        close_ret = np.zeros(n, dtype=np.float64)
        if n > 1:
            prev_close = close_arr[:-1].copy()
            prev_close[prev_close == 0] = 1.0
            close_ret[1:] = (close_arr[1:] / prev_close) - 1.0

        ma_m = pd.Series(close_arr).rolling(window=w_m, min_periods=1).mean().to_numpy(dtype=np.float64)
        ma_l = pd.Series(close_arr).rolling(window=w_l, min_periods=1).mean().to_numpy(dtype=np.float64)
        ma_m_safe = ma_m.copy()
        ma_l_safe = ma_l.copy()
        ma_m_safe[ma_m_safe == 0] = 1.0
        ma_l_safe[ma_l_safe == 0] = 1.0

        mom_m = np.zeros(n, dtype=np.float64)
        mom_l = np.zeros(n, dtype=np.float64)
        if n > w_m:
            prev = close_arr[:-w_m].copy()
            prev[prev == 0] = 1.0
            mom_m[w_m:] = (close_arr[w_m:] / prev) - 1.0
        if n > w_l:
            prev = close_arr[:-w_l].copy()
            prev[prev == 0] = 1.0
            mom_l[w_l:] = (close_arr[w_l:] / prev) - 1.0

        vol_ma_m = pd.Series(volume_arr).rolling(window=w_m, min_periods=1).mean().to_numpy(dtype=np.float64)
        vol_ma_m_safe = vol_ma_m.copy()
        vol_ma_m_safe[vol_ma_m_safe == 0] = 1.0

        drawdown_l = np.zeros(n, dtype=np.float64)
        rolling_max = pd.Series(close_arr).rolling(window=w_l, min_periods=1).max().to_numpy(dtype=np.float64)
        rolling_max[rolling_max == 0] = 1.0
        drawdown_l = (close_arr / rolling_max) - 1.0

        feature_map = {
            "vol_medium": pd.Series(close_ret).rolling(window=w_m, min_periods=1).std().fillna(0.0).to_numpy(dtype=np.float64),
            "vol_long": pd.Series(close_ret).rolling(window=w_l, min_periods=1).std().fillna(0.0).to_numpy(dtype=np.float64),
            "dist_ma_medium": (close_arr / ma_m_safe) - 1.0,
            "dist_ma_long": (close_arr / ma_l_safe) - 1.0,
            "slope_ma_medium": np.diff(ma_m, prepend=ma_m[0]),
            "slope_ma_long": np.diff(ma_l, prepend=ma_l[0]),
            "mom_medium": mom_m,
            "mom_long": mom_l,
            "vol_ratio_medium": volume_arr / vol_ma_m_safe,
            "dd_long": drawdown_l,
        }

        if "relative_strength" in self.engineered_feature_families:
            if market_momentum_frame is None:
                raise ValueError("Relative strength enabled but market_momentum_frame was not provided")
            merged_market = df[["time"]].merge(market_momentum_frame, on="time", how="left", sort=False)
            if merged_market["mom_medium_market"].isna().any():
                raise ValueError("Missing aligned market momentum values for rs_medium")
            feature_map["rs_medium"] = mom_m - merged_market["mom_medium_market"].to_numpy(dtype=np.float64)
            if self.rs_include_long:
                if "mom_long_market" not in merged_market.columns:
                    raise ValueError("mom_long_market missing while rs_long is enabled")
                if merged_market["mom_long_market"].isna().any():
                    raise ValueError("Missing aligned market momentum values for rs_long")
                feature_map["rs_long"] = mom_l - merged_market["mom_long_market"].to_numpy(dtype=np.float64)

        for name in self.engineered_feature_names:
            out[name] = feature_map[name]
        return out

    def _compute_calendar_sincos(self, df: pd.DataFrame) -> np.ndarray:
        """Compute cyclical calendar features from time column."""
        if self.calendar_feature_dim == 0:
            return np.empty((len(df), 0), dtype=np.float64)
        if "time" not in df.columns:
            raise ValueError("Dataframe missing required column: time")

        time_index = pd.to_datetime(df["time"], errors="raise")
        components = []
        for feature in self.calendar_features:
            if feature == "dow":
                values = time_index.dt.dayofweek.to_numpy(dtype=np.float64)  # 0..6
                period = 7.0
            elif feature == "month":
                values = time_index.dt.month.to_numpy(dtype=np.float64)  # 1..12
                period = 12.0
            else:  # dom
                values = time_index.dt.day.to_numpy(dtype=np.float64)  # 1..31
                period = 31.0
            angles = (2.0 * np.pi * values) / period
            components.append(np.sin(angles))
            components.append(np.cos(angles))
        return np.column_stack(components).astype(np.float64, copy=False)

    def _compute_cache_from_df(
        self,
        df: pd.DataFrame,
        precomputed_ma_frame: Optional[pd.DataFrame] = None,
        ma_windows: Optional[List[int]] = None,
        precomputed_window_returns_frame: Optional[pd.DataFrame] = None,
        returns_windows: Optional[List[int]] = None,
        precomputed_engineered_frame: Optional[pd.DataFrame] = None,
        include_engineered: bool = True,
        include_news: bool = True,
        include_signal: bool = True,
    ) -> dict:
        """
        Precompute NumPy arrays for fast access.
        
        Returns:
            cache dict with:
              - ohlcv: shape (N, base_feature_dim)
              - open: shape (N,)
              - close: shape (N,)
              - volume: shape (N,)
              - returns: shape (N, base_feature_dim) (t-1 -> t), row 0 zeros
              - ma: shape (N, len(ma_windows))
              - ma_returns: shape (N, len(ma_windows))
              - window_returns: shape (N, len(returns_windows))
              - engineered: shape (N, engineered_feature_dim) if include_engineered else (N, 0)
              - news: shape (N, news_feature_dim) if include_news else (N, 0)
              - signal: shape (N, signal_feature_dim) if include_signal else (N, 0)
              - calendar: shape (N, calendar_feature_dim)
        """
        required_cols = {"open", "close", "volume", *self.ohlcv_fields}
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Dataframe missing required feature columns: {sorted(missing)}")

        ohlcv = df[self.ohlcv_fields].to_numpy(dtype=np.float64)
        open_arr = df["open"].to_numpy(dtype=np.float64)
        close_arr = df["close"].to_numpy(dtype=np.float64)
        volume_arr = df["volume"].to_numpy(dtype=np.float64)
        
        returns = np.zeros_like(ohlcv, dtype=np.float64)
        prev_close_for_norm = close_arr[:-1].copy()
        prev_close_for_norm[prev_close_for_norm == 0] = 1.0
        if len(ohlcv) > 1:
            prev_close_col = prev_close_for_norm.reshape(-1, 1)
            prev_volume = volume_arr[:-1]
            curr_volume = volume_arr[1:]
            for idx, field in enumerate(self.ohlcv_fields):
                current = ohlcv[1:, idx]
                if field == "volume":
                    field_returns = np.zeros_like(current, dtype=np.float64)
                    nonzero_mask = (prev_volume != 0) & (curr_volume != 0)
                    field_returns[nonzero_mask] = (curr_volume[nonzero_mask] / prev_volume[nonzero_mask]) - 1.0
                    returns[1:, idx] = field_returns
                else:
                    returns[1:, idx] = (current.reshape(-1, 1) / prev_close_col).reshape(-1) - 1.0

        active_ma_windows = self.ma_windows if ma_windows is None else list(ma_windows)
        active_ma_feature_count = len(active_ma_windows)
        ma = np.empty((len(ohlcv), active_ma_feature_count), dtype=np.float64)
        ma_returns = np.zeros_like(ma, dtype=np.float64)
        if active_ma_feature_count:
            if precomputed_ma_frame is not None:
                if "time" not in precomputed_ma_frame.columns:
                    raise ValueError("precomputed_ma_frame must contain 'time' column")
                merged = df[["time"]].merge(precomputed_ma_frame, on="time", how="left", sort=False)
                if merged.isna().any().any():
                    raise ValueError("Missing MA values after aligning precomputed MA frame by time")
                for idx, window in enumerate(active_ma_windows):
                    ma[:, idx] = merged[f"ma_{window}"].to_numpy(dtype=np.float64)
                    ma_returns[:, idx] = merged[f"ma_ret_{window}"].to_numpy(dtype=np.float64)
            else:
                for idx, window in enumerate(active_ma_windows):
                    ma_column = (
                        pd.Series(close_arr)
                        .rolling(window=window, min_periods=1)
                        .mean()
                        .to_numpy(dtype=np.float64)
                    )
                    ma[:, idx] = ma_column
                    if len(ma_column) > 1:
                        ma_returns[1:, idx] = (ma_column[1:] / prev_close_for_norm) - 1.0

        active_returns_windows = self.returns_windows if returns_windows is None else list(returns_windows)
        active_returns_feature_count = len(active_returns_windows)
        window_returns = np.zeros((len(ohlcv), active_returns_feature_count), dtype=np.float64)
        if active_returns_feature_count:
            if precomputed_window_returns_frame is not None:
                if "time" not in precomputed_window_returns_frame.columns:
                    raise ValueError("precomputed_window_returns_frame must contain 'time' column")
                merged = df[["time"]].merge(precomputed_window_returns_frame, on="time", how="left", sort=False)
                if merged.isna().any().any():
                    raise ValueError("Missing window return values after aligning precomputed frame by time")
                for idx, window in enumerate(active_returns_windows):
                    window_returns[:, idx] = merged[f"ret_{window}"].to_numpy(dtype=np.float64)
            else:
                for idx, window in enumerate(active_returns_windows):
                    if len(close_arr) > window:
                        prev = close_arr[:-window].copy()
                        prev[prev == 0] = 1.0
                        window_returns[window:, idx] = (close_arr[window:] / prev) - 1.0

        if include_engineered and self.engineered_feature_dim:
            if precomputed_engineered_frame is not None:
                if "time" not in precomputed_engineered_frame.columns:
                    raise ValueError("precomputed_engineered_frame must contain 'time' column")
                merged_eng = df[["time"]].merge(precomputed_engineered_frame, on="time", how="left", sort=False)
                required_cols = list(self.engineered_feature_names)
                missing_cols = [c for c in required_cols if c not in merged_eng.columns]
                if missing_cols:
                    raise ValueError(f"Missing engineered feature columns after merge: {missing_cols}")
                if merged_eng[required_cols].isna().any().any():
                    raise ValueError("Missing engineered feature values after aligning precomputed engineered frame")
                engineered = merged_eng[required_cols].to_numpy(dtype=np.float64)
            else:
                engineered = self._compute_pretrim_engineered_frame(df)[self.engineered_feature_names].to_numpy(
                    dtype=np.float64
                )
        else:
            engineered = np.empty((len(ohlcv), 0), dtype=np.float64)
        if include_news and self.news_feature_dim:
            missing_news_cols = [column for column in self.news_feature_names if column not in df.columns]
            if missing_news_cols:
                raise ValueError(f"Missing news feature columns after merge: {missing_news_cols}")
            news = (
                df[self.news_feature_names]
                .apply(pd.to_numeric, errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=np.float64)
            )
        else:
            news = np.empty((len(ohlcv), 0), dtype=np.float64)
        if include_signal and self.signal_feature_dim:
            missing_signal_cols = [column for column in self.signal_feature_names if column not in df.columns]
            if missing_signal_cols:
                raise ValueError(f"Missing signal feature columns after merge: {missing_signal_cols}")
            signal = (
                df[self.signal_feature_names]
                .apply(pd.to_numeric, errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=np.float64)
            )
        else:
            signal = np.empty((len(ohlcv), 0), dtype=np.float64)
        calendar = self._compute_calendar_sincos(df)
        
        return {
            'ohlcv': ohlcv,
            'open': open_arr,
            'close': close_arr,
            'volume': volume_arr,
            'returns': returns,
            'ma': ma,
            'ma_returns': ma_returns,
            'window_returns': window_returns,
            'engineered': engineered,
            'news': news,
            'signal': signal,
            'calendar': calendar,
        }

    def _set_active_cache(
        self,
        cache: dict,
        market_caches: Optional[List[dict]] = None,
        asset_caches: Optional[List[dict]] = None
    ):
        """Attach active NumPy cache to instance."""
        self._ohlcv = cache['ohlcv']
        self._open = cache['open']
        self._close = cache['close']
        self._volume = cache['volume']
        self._returns = cache['returns']
        self._ma = cache['ma']
        self._ma_returns = cache['ma_returns']
        self._window_returns = cache['window_returns']
        self._engineered = cache['engineered']
        self._news = cache['news']
        self._signal = cache['signal']
        self._calendar = cache['calendar']
        
        if market_caches:
            self._market_ohlcv = [c['ohlcv'] for c in market_caches]
            self._market_returns = [c['returns'] for c in market_caches]
            self._market_ma = [c['ma'] for c in market_caches]
            self._market_ma_returns = [c['ma_returns'] for c in market_caches]
            self._market_window_returns = [c['window_returns'] for c in market_caches]
            self.market_feature_count = len(market_caches) * self.base_feature_dim
            self.market_ma_feature_count = len(market_caches) * self.helpers_ma_feature_count
            self.market_returns_feature_count = len(market_caches) * self.helpers_returns_feature_count
        else:
            self._market_ohlcv = []
            self._market_returns = []
            self._market_ma = []
            self._market_ma_returns = []
            self._market_window_returns = []
            self.market_feature_count = 0
            self.market_ma_feature_count = 0
            self.market_returns_feature_count = 0
        
        if asset_caches:
            self._asset_ohlcv = [c['ohlcv'] for c in asset_caches]
            self._asset_returns = [c['returns'] for c in asset_caches]
            self._asset_ma = [c['ma'] for c in asset_caches]
            self._asset_ma_returns = [c['ma_returns'] for c in asset_caches]
            self._asset_window_returns = [c['window_returns'] for c in asset_caches]
            self.asset_feature_count = len(asset_caches) * self.base_feature_dim
            self.asset_ma_feature_count = len(asset_caches) * self.helpers_ma_feature_count
            self.asset_returns_feature_count = len(asset_caches) * self.helpers_returns_feature_count
        else:
            self._asset_ohlcv = []
            self._asset_returns = []
            self._asset_ma = []
            self._asset_ma_returns = []
            self._asset_window_returns = []
            self.asset_feature_count = 0
            self.asset_ma_feature_count = 0
            self.asset_returns_feature_count = 0

        # Active feature arrays in fixed order for fast observation assembly.
        # Order must stay: base, market helpers, asset helpers, MA, helper MA, returns,
        # helper returns, engineered, news, calendar.
        self._feature_arrays_normalized = [self._returns, *self._market_returns, *self._asset_returns]
        self._feature_arrays_raw = [self._ohlcv, *self._market_ohlcv, *self._asset_ohlcv]
        if self.ma_feature_count:
            self._feature_arrays_normalized.append(self._ma_returns)
            self._feature_arrays_raw.append(self._ma)
        if self.helpers_ma_feature_count:
            self._feature_arrays_normalized.extend(self._market_ma_returns)
            self._feature_arrays_normalized.extend(self._asset_ma_returns)
            self._feature_arrays_raw.extend(self._market_ma)
            self._feature_arrays_raw.extend(self._asset_ma)
        if self.returns_feature_count:
            self._feature_arrays_normalized.append(self._window_returns)
            self._feature_arrays_raw.append(self._window_returns)
        if self.helpers_returns_feature_count:
            self._feature_arrays_normalized.extend(self._market_window_returns)
            self._feature_arrays_normalized.extend(self._asset_window_returns)
            self._feature_arrays_raw.extend(self._market_window_returns)
            self._feature_arrays_raw.extend(self._asset_window_returns)
        if self.engineered_feature_dim:
            self._feature_arrays_normalized.append(self._engineered)
            self._feature_arrays_raw.append(self._engineered)
        if self.news_feature_dim:
            self._feature_arrays_normalized.append(self._news)
            self._feature_arrays_raw.append(self._news)
        if self.signal_feature_dim:
            self._feature_arrays_normalized.append(self._signal)
            self._feature_arrays_raw.append(self._signal)
        if self.calendar_feature_dim:
            self._feature_arrays_normalized.append(self._calendar)
            self._feature_arrays_raw.append(self._calendar)

        self.n_features = self.lookback_window * (
            self.base_feature_dim
            + self.market_feature_count
            + self.asset_feature_count
            + self.ma_feature_count
            + self.market_ma_feature_count
            + self.asset_ma_feature_count
            + self.returns_feature_count
            + self.market_returns_feature_count
            + self.asset_returns_feature_count
            + self.engineered_feature_dim
            + self.news_feature_dim
            + self.signal_feature_dim
            + self.calendar_feature_dim
        )

    @staticmethod
    def _compute_splits(total_len: int, lookback_window: int, train_split: float, val_split: float) -> dict:
        """
        Compute train/val/test split indices with 1-day gaps between splits.
        Uses the same indexing logic as the environment.
        """
        if lookback_window <= 0:
            raise ValueError(f"lookback_window must be > 0, got {lookback_window}")
        if total_len <= lookback_window + 2:
            raise ValueError(
                f"Dataset too short: total_len={total_len}, lookback_window={lookback_window}. "
                "Need more rows to build observation history and at least one tradable step."
            )
        if not (0.0 < float(train_split) < 1.0):
            raise ValueError(f"train_split must be in (0, 1), got {train_split}")
        if not (0.0 <= float(val_split) < 1.0):
            raise ValueError(f"val_split must be in [0, 1), got {val_split}")
        if float(train_split) + float(val_split) >= 1.0:
            raise ValueError(
                f"train_split + val_split must be < 1.0, got {train_split + val_split}"
            )

        valid_start_idx = lookback_window
        train_start_idx = valid_start_idx + 1
        train_end_idx = int(total_len * train_split) - 1
        val_start_idx = train_end_idx + 2  # skip gap row
        val_end_idx = int(total_len * (train_split + val_split)) - 1
        test_start_idx = val_end_idx + 2  # skip gap row
        test_end_idx = total_len - 1

        return {
            'valid_start_idx': valid_start_idx,
            'train_start_idx': train_start_idx,
            'train_end_idx': train_end_idx,
            'val_start_idx': val_start_idx,
            'val_end_idx': val_end_idx,
            'test_start_idx': test_start_idx,
            'test_end_idx': test_end_idx
        }

    @staticmethod
    def _validate_mode_split(splits: dict, mode: str, context: str = ""):
        """
        Validate only the active mode split has enough rows for t -> t+1 execution.
        This keeps test/val evaluation possible even when train split is too short.
        """
        if mode not in {"train", "val", "test"}:
            raise ValueError(f"Invalid mode: {mode}. Must be 'train', 'val', or 'test'")
        start_key = f"{mode}_start_idx"
        end_key = f"{mode}_end_idx"
        rows = int(splits[end_key] - splits[start_key] + 1)
        if rows < 2:
            scope = f" {context}" if context else ""
            raise ValueError(
                f"Split configuration yields empty or non-tradable range for mode='{mode}'{scope}: "
                f"{mode}_rows={rows}. Need at least 2 rows to support t->t+1 execution."
            )

    def _sample_train_episode_bounds(self, train_start_idx: int, train_end_idx: int) -> Tuple[int, int]:
        """Sample train episode bounds from configured fraction range or return full range."""
        if train_end_idx < train_start_idx:
            raise ValueError(
                f"Invalid train bounds: start={train_start_idx}, end={train_end_idx}"
            )
        if not self.train_episode_sampling_enabled:
            return int(train_start_idx), int(train_end_idx)

        train_rows = int(train_end_idx - train_start_idx + 1)
        min_rows = int(np.floor(train_rows * self.train_episode_min_fraction))
        max_rows = int(np.floor(train_rows * self.train_episode_max_fraction))
        min_rows = max(min_rows, 2)
        max_rows = max(max_rows, min_rows)
        max_rows = min(max_rows, train_rows)

        if max_rows <= min_rows:
            episode_rows = int(min_rows)
        else:
            episode_rows = int(self.np_random.integers(min_rows, max_rows + 1))

        latest_start = int(train_end_idx - episode_rows + 1)
        if latest_start <= train_start_idx:
            episode_start_idx = int(train_start_idx)
        else:
            episode_start_idx = int(self.np_random.integers(train_start_idx, latest_start + 1))
        episode_end_idx = int(episode_start_idx + episode_rows - 1)

        assert episode_start_idx >= self.lookback_window + 1, (
            f"Sampled train episode start {episode_start_idx} is too early for lookback_window={self.lookback_window}"
        )
        assert episode_end_idx <= train_end_idx, (
            f"Sampled train episode end {episode_end_idx} exceeds train_end_idx={train_end_idx}"
        )
        return episode_start_idx, episode_end_idx

    def _load_external_data_map(
        self,
        tickers: List[str],
        data_dir: str,
        file_prefix: str,
        interval: str
    ) -> Dict[str, pd.DataFrame]:
        """Load and validate external helper datasets once."""
        required_cols = {'time', 'open', 'high', 'low', 'close', 'volume'}
        data_map: Dict[str, pd.DataFrame] = {}
        for ticker in tickers:
            file_path = os.path.join(data_dir, f"{file_prefix}{ticker}_{interval}.parquet")
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Market data file not found: {file_path}")
            df = pd.read_parquet(file_path)
            if not required_cols.issubset(df.columns):
                missing = required_cols - set(df.columns)
                raise ValueError(f"Market dataframe {ticker} missing columns: {sorted(missing)}")
            data_map[ticker] = df.sort_values('time').reset_index(drop=True)
        return data_map

    def _align_base_with_external_data(
        self,
        base_df: pd.DataFrame,
        external_data_map: Dict[str, pd.DataFrame]
    ) -> Tuple[pd.DataFrame, List[pd.DataFrame]]:
        """
        Align a base dataframe with already-loaded external datasets by inner join on 'time'.

        Returns:
            aligned_base_df, aligned_external_dfs (in insertion order of external_data_map)
        """
        required_cols = {'time', 'open', 'high', 'low', 'close', 'volume'}
        if not required_cols.issubset(base_df.columns):
            missing = required_cols - set(base_df.columns)
            raise ValueError(f"Base dataframe missing columns: {sorted(missing)}")

        base_sorted = base_df.sort_values('time').reset_index(drop=True)
        common_times = pd.Index(base_sorted['time'])
        for df in external_data_map.values():
            common_times = common_times.intersection(pd.Index(df['time']))

        if len(common_times) == 0:
            raise ValueError("No overlapping dates between base data and market data")

        common_times = pd.Index(common_times).sort_values()
        base_aligned = base_sorted[base_sorted['time'].isin(common_times)].sort_values('time').reset_index(drop=True)
        aligned_external_dfs = []
        for ticker in external_data_map.keys():
            df = external_data_map[ticker]
            aligned = df[df['time'].isin(common_times)].sort_values('time').reset_index(drop=True)
            aligned_external_dfs.append(aligned)

        if len(base_aligned) < self.lookback_window + 2:
            raise ValueError(
                f"Aligned data too short after joining market data: "
                f"{len(base_aligned)} rows (need at least {self.lookback_window + 2})"
            )

        return base_aligned, aligned_external_dfs

    def _load_and_align_market_data(
        self,
        base_df: pd.DataFrame,
        tickers: List[str],
        data_dir: str,
        file_prefix: str,
        interval: str
    ) -> Tuple[pd.DataFrame, List[pd.DataFrame]]:
        """
        Load market index data and align it to base_df by inner join on 'time'.
        
        Returns:
            aligned_base_df, aligned_market_dfs
        """
        market_data_map = self._load_external_data_map(
            tickers=tickers,
            data_dir=data_dir,
            file_prefix=file_prefix,
            interval=interval,
        )
        return self._align_base_with_external_data(base_df, market_data_map)
    
    def _get_observation(self) -> np.ndarray:
        """
        Get current state observation with lookback window ending at t (end-of-day decision).
        
        At step t (end of day t), the agent sees data up to day t close.
        This allows the agent to make decisions at end of day based on full day's data.
        The decision will execute at open[t+1].
        """
        # Observation window ends at t (includes close[t]) for end-of-day decision
        # We need lookback_window rows ending at t (t-lookback+1 .. t)
        end_idx = self.current_step
        start_idx = end_idx - self.lookback_window + 1
        
        # Assert we have enough data (fail loud if not)
        assert start_idx >= 1, \
            f"Insufficient historical data at step {self.current_step}: " \
            f"need at least {self.lookback_window} rows ending at t, got start_idx={start_idx}. " \
            f"Check warm-up period and episode start index."

        feature_arrays = self._feature_arrays_normalized if self.source_mode == "return" else self._feature_arrays_raw
        extra_state_dim = 3 if self.include_can_exit else 2
        state = np.empty(self.n_features + extra_state_dim, dtype=np.float32)

        offset = 0
        for feature_array in feature_arrays:
            window = feature_array[start_idx:end_idx + 1]
            assert window.shape[0] == self.lookback_window, \
                f"Expected {self.lookback_window} rows, got {window.shape[0]}"
            flat_window = window.reshape(-1)
            next_offset = offset + flat_window.size
            state[offset:next_offset] = flat_window
            offset = next_offset

        assert offset == self.n_features, \
            f"Feature length mismatch: expected {self.n_features}, got {offset}"
        state[offset] = float(self.position)
        state[offset + 1] = float(self.hold_count)
        if self.include_can_exit:
            state[offset + 2] = float(self.hold_count >= self.min_hold_days)

        return state
    
    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None):
        """Reset environment to start of episode."""
        super().reset(seed=seed)
        
        # Set episode range (implemented by subclasses)
        self._reset_episode_range()
        
        # Safety assert: ensure we have enough history for observation
        assert self.episode_start_idx >= self.lookback_window + 1, \
            f"Episode start index {self.episode_start_idx} is too early. " \
            f"Need at least {self.lookback_window + 1} rows for observation window."
        
        # Start at beginning of episode (end of day t)
        self.current_step = self.episode_start_idx
        self.position = 0  # No position active initially
        self.hold_count = 0
        self.entry_price = None
        self.pending_action = 0
        self.cash = 1.0
        self.shares = 0.0
        self.start_in_position = False
        self.synthetic_entry_idx = None
        self.synthetic_entry_price = None
        if self.mode == "train" and self.start_episode_position > 0.0:
            if float(self.np_random.random()) < self.start_episode_position:
                open_now = float(self._open[self.current_step])
                if open_now > 0.0:
                    max_hold = max(1, min(int(self.lookback_window), int(self.current_step)))
                    # Retry to find a valid historical entry open.
                    for _ in range(8):
                        hold_days = int(self.np_random.integers(1, max_hold + 1))
                        entry_idx = int(self.current_step - (hold_days - 1))
                        assert entry_idx >= 0, f"entry_idx must be >= 0, got {entry_idx}"
                        entry_open = float(self._open[entry_idx])
                        if entry_open <= 0.0:
                            continue
                        # Synthetic "already long" start state:
                        # - historical entry anchor for hold_count/stop-loss
                        # - no reset buy fee
                        # - normalize current equity to 1.0
                        self.shares = self.cash / open_now
                        self.cash = 0.0
                        self.position = 1
                        self.pending_action = 1
                        self.hold_count = hold_days
                        self.entry_price = entry_open
                        self.start_in_position = True
                        self.synthetic_entry_idx = entry_idx
                        self.synthetic_entry_price = entry_open
                        break
        self.episode_trades = []
        self.episode_rewards = []
        self.cumulative_return = 0.0
        self.peak_equity = max(float(self._equity_at_open(self.current_step)), 1e-12)
        self.last_raw_return = 0.0
        self.last_benchmark_return = 0.0
        self.last_excess_return = 0.0
        self.last_drawdown = 0.0
        self.last_drawdown_penalty = 0.0
        
        observation = self._get_observation()
        info = self._get_reset_info()
        
        return observation, info
    
    def _get_reset_info(self) -> dict:
        """Get info dict for reset. Can be overridden by subclasses."""
        return {
            'mode': self.mode,
            'start_idx': self.episode_start_idx,
            'end_idx': self.episode_end_idx,
            'total_steps': self.episode_end_idx - self.episode_start_idx,
            'start_in_position': bool(self.start_in_position),
            'synthetic_entry_idx': self.synthetic_entry_idx,
            'synthetic_entry_price': self.synthetic_entry_price,
        }

    def _is_episode_done_before_step(self) -> bool:
        """Whether episode has passed the last valid decision step."""
        return self.current_step > self.episode_end_idx

    def _equity_at_open(self, step_idx: int) -> float:
        """Portfolio equity valued at open[step_idx]."""
        return self.cash + (self.shares * self._open[step_idx])

    def _execute_pending_transition(self, pos_old: int, pos_new: int, open_exec: float):
        """Execute pending position transition at the provided execution open price."""
        if pos_old == pos_new:
            return
        if pos_old == 0 and pos_new == 1:
            # Entering: all-in buy, apply buy fee on notional.
            cash_after_fee = self.cash * (1 - self.buy_fee_rate)
            self.shares = cash_after_fee / open_exec
            self.cash = 0.0
            return
        if pos_old == 1 and pos_new == 0:
            # Exiting: all-out sell, apply sell fee + capital gains tax on notional.
            proceeds = self.shares * open_exec
            proceeds_net = proceeds * (1 - self.sell_fee_rate - self.capital_gains_tax_rate)
            self.cash = proceeds_net
            self.shares = 0.0

    def _compute_benchmark_return(self, step_idx_t: int, step_idx_t1: int) -> float:
        """Compute the configured benchmark return over the active step interval."""
        if not self.benchmark_relative_reward_enabled:
            return 0.0
        if self.reward_benchmark == "self_buy_hold":
            open_t = float(self._open[step_idx_t])
            open_t1 = float(self._open[step_idx_t1])
            if open_t == 0.0:
                return 0.0
            return (open_t1 / open_t) - 1.0
        raise ValueError(f"Unsupported reward_benchmark '{self.reward_benchmark}'")

    def _update_position_tracking(self, pos_old: int, pos_new: int, open_exec: float):
        """Update position/hold_count/entry_price after execution."""
        self.position = pos_new
        if self.position == 1:
            if pos_old == 1:
                self.hold_count += 1
            else:
                self.hold_count = 1
                self.entry_price = open_exec
                assert self.entry_price is not None, "Entry price must be set when entering position"
        else:
            self.hold_count = 0
            self.entry_price = None

    def _record_trade_if_changed(self, pos_old: int, pos_new: int, open_exec: float):
        """Record executed trade transition if position changed."""
        if pos_old == pos_new:
            return
        self.episode_trades.append({
            'step': self.current_step,  # Step where execution happened (end of day t+1)
            'from_pos': pos_old,
            'to_pos': pos_new,
            'price': open_exec
        })

    def _apply_next_action_constraints(self, action: int) -> int:
        """Apply min-hold and stop-loss constraints to next pending action."""
        constrained_action = action
        if self.position == 1 and self.hold_count < self.min_hold_days:
            constrained_action = 1  # Cannot schedule exit yet.
        if self.position == 1 and self.entry_price is not None and self.stop_loss is not None:
            close_now = self._close[self.current_step]  # End-of-day price.
            loss = (close_now / self.entry_price) - 1
            if loss <= -self.stop_loss:
                constrained_action = 0  # Schedule exit at next open.
        return constrained_action

    def step(self, action):
        """
        Execute one step with end-of-day decision model.

        At step t (end of day t):
        - Agent sees data up to close[t] and makes decision (action)
        - Reward is for interval (t -> t+1) using position that was active during that interval
        - Previous pending_action executes at open[t+1]
        - New action is stored as pending_action to execute at open[t+2]
        """
        # Safety asserts: ensure we can access t and t+1.
        assert self.current_step < len(self._open), \
            f"current_step {self.current_step} >= len(df) {len(self._open)}"
        assert self.current_step + 1 < len(self._open), \
            f"current_step {self.current_step} + 1 >= len(df) {len(self._open)} (need t+1 for reward and execution)"

        # Check boundary: ensure we're within episode bounds.
        if self._is_episode_done_before_step():
            terminated = True
            truncated = False
            observation = self._get_observation()
            info = self._get_step_info(0.0)
            return observation, 0.0, terminated, truncated, info

        # A) Compute reward denominator for interval (t -> t+1).
        equity_t = self._equity_at_open(self.current_step)

        # B) Advance time to t+1.
        self.current_step += 1

        # C) Execute previous pending decision at open[t+1].
        pos_old = self.position
        pos_new = self.pending_action
        open_exec = self._open[self.current_step]
        self._execute_pending_transition(pos_old, pos_new, open_exec)

        # D) Compute reward and update state/accounting.
        equity_t1 = self._equity_at_open(self.current_step)
        raw_return = (equity_t1 / equity_t) - 1
        benchmark_return = self._compute_benchmark_return(self.current_step - 1, self.current_step)
        excess_return = raw_return - benchmark_return
        relative_reward_signal = raw_return - (self.benchmark_weight * benchmark_return)
        peak_equity = max(float(self.peak_equity), float(equity_t1), 1e-12)
        drawdown = max(0.0, (peak_equity - float(equity_t1)) / peak_equity)
        apply_drawdown_penalty = self.drawdown_penalty_enabled and (
            (not self.drawdown_penalty_train_only) or (self.mode == "train")
        )
        drawdown_penalty = (self.drawdown_penalty_lambda * drawdown) if apply_drawdown_penalty else 0.0
        reward_signal = (
            relative_reward_signal if self.benchmark_relative_reward_enabled else raw_return
        )
        reward = reward_signal - drawdown_penalty
        self.peak_equity = peak_equity
        self.last_raw_return = float(raw_return)
        self.last_benchmark_return = float(benchmark_return)
        self.last_excess_return = float(excess_return)
        self.last_drawdown = float(drawdown)
        self.last_drawdown_penalty = float(drawdown_penalty)
        self._update_position_tracking(pos_old, pos_new, open_exec)
        self._record_trade_if_changed(pos_old, pos_new, open_exec)
        self.episode_rewards.append(reward)
        self.cumulative_return += reward

        # E) Process constraints on NEW decision and store for tomorrow.
        self.pending_action = self._apply_next_action_constraints(action)

        # F) Check termination and return.
        terminated = self.current_step > self.episode_end_idx
        truncated = False
        observation = self._get_observation()
        info = self._get_step_info(reward)
        return observation, reward, terminated, truncated, info

    def _get_step_info(self, reward: float) -> dict:
        """Get info dict for step. Can be overridden by subclasses."""
        open_now = self._open[self.current_step]
        equity = self.cash + (self.shares * open_now)
        return {
            'step': self.current_step,
            'position': self.position,
            'hold_count': self.hold_count,
            'reward': reward,
            'reward_shaped': reward,
            'raw_return': float(self.last_raw_return),
            'benchmark_return': float(self.last_benchmark_return),
            'excess_return': float(self.last_excess_return),
            'drawdown': float(self.last_drawdown),
            'drawdown_penalty': float(self.last_drawdown_penalty),
            'peak_equity': float(self.peak_equity),
            'cumulative_return': self.cumulative_return,
            'cash': self.cash,
            'shares': self.shares,
            'equity': equity
        }
    
    def render(self, mode='human'):
        """Print current state."""
        if mode == 'human':
            stock_name = self._get_stock_name()
            prefix = f"[{stock_name}] " if stock_name else ""
            print(f"{prefix}Step: {self.current_step}/{self.episode_end_idx} | "
                  f"Pos: {self.position} | Hold: {self.hold_count} | "
                  f"Return: {self.cumulative_return:.4f}")
    
    def _get_stock_name(self) -> Optional[str]:
        """Returns stock name for display. Override in subclasses if needed."""
        return None
    
    def get_episode_stats(self):
        """Get episode statistics."""
        total_return = self.cumulative_return
        num_trades = len(self.episode_trades)
        
        # Calculate trade returns
        trade_returns = []
        last_entry_price = None
        fee_multiplier = (
            (1.0 - float(self.buy_fee_rate))
            * (1.0 - float(self.sell_fee_rate) - float(self.capital_gains_tax_rate))
        )
        for trade in self.episode_trades:
            if trade['to_pos'] == 1:
                last_entry_price = trade['price']
            elif trade['to_pos'] == 0 and last_entry_price is not None:
                entry_price = float(last_entry_price)
                exit_price = float(trade['price'])
                gross_multiplier = exit_price / entry_price
                net_multiplier = fee_multiplier * gross_multiplier
                trade_returns.append(net_multiplier - 1.0)
                last_entry_price = None

        if trade_returns:
            trade_returns_arr = np.asarray(trade_returns, dtype=np.float64)
            winning_mask = trade_returns_arr > 0
            win_rate = float(np.mean(winning_mask))
            num_winning = int(np.count_nonzero(winning_mask))
            avg_trade_return = float(np.mean(trade_returns_arr))
        else:
            win_rate = 0.0
            num_winning = 0
            avg_trade_return = 0.0
        
        stats = {
            'total_return': total_return,
            'num_trades': num_trades,
            'num_winning_trades': num_winning,
            'win_rate': win_rate,
            'avg_trade_return': avg_trade_return,
            'total_steps': self.current_step - self.episode_start_idx,
            'reward_mode': (
                'benchmark_relative'
                if self.benchmark_relative_reward_enabled
                else ('drawdown_shaped' if self.drawdown_penalty_enabled else 'raw_return')
            ),
            'reward_benchmark': self.reward_benchmark,
            'benchmark_weight': float(self.benchmark_weight),
        }
        
        # Add stock name if available
        stock_name = self._get_stock_name()
        if stock_name:
            stats['stock'] = stock_name
        
        return stats
