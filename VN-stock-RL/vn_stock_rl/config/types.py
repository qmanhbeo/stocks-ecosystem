"""Structured configuration objects for the RL package."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from vn_stock_rl.external_features import default_help_assets_dir, default_market_data_dir, default_stock_data_dir


@dataclass
class WindowPolicyConfig:
    mode: str = "logspace"
    explicit_windows: list[int] = field(default_factory=lambda: [5, 10, 20, 40, 80])
    logspace_min: int = 5
    logspace_max: int = 80
    logspace_count: int = 5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RelativeStrengthConfig:
    market_proxy_preference: list[str] = field(default_factory=lambda: ["VNINDEX", "VN30"])
    include_long_horizon: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EngineeredFeatureConfig:
    enabled: list[str] = field(
        default_factory=lambda: ["volatility", "trend", "momentum", "volume_context", "drawdown"]
    )
    window_policy: WindowPolicyConfig = field(default_factory=WindowPolicyConfig)
    horizons: dict[str, int] = field(default_factory=lambda: {"medium_index": 2, "long_index": 4})
    relative_strength: RelativeStrengthConfig = field(default_factory=RelativeStrengthConfig)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["window_policy"] = self.window_policy.to_dict()
        data["relative_strength"] = self.relative_strength.to_dict()
        return data


@dataclass
class FeatureConfig:
    source_mode: str = "return"
    ohlcv: list[str] = field(default_factory=lambda: ["open", "high", "low", "close", "volume"])
    ma_windows: list[int] = field(default_factory=lambda: [5, 10, 20, 50])
    helpers_ma_windows: list[int | str] = field(default_factory=lambda: ["same"])
    returns_windows: list[int] = field(default_factory=lambda: [5, 10, 20, 50])
    helpers_returns_windows: list[int | str] = field(default_factory=lambda: ["same"])
    calendar: list[str] = field(default_factory=lambda: ["dow", "month", "dom"])
    engineered_features: EngineeredFeatureConfig = field(default_factory=EngineeredFeatureConfig)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["engineered_features"] = self.engineered_features.to_dict()
        return data


@dataclass
class DrawdownPenaltyConfig:
    enabled: bool = True
    lambda_: float = 0.05
    train_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "lambda": self.lambda_,
            "train_only": self.train_only,
        }


@dataclass
class BenchmarkRelativeRewardConfig:
    enabled: bool = False
    benchmark: str = "self_buy_hold"
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "benchmark": self.benchmark,
            "weight": self.weight,
        }


@dataclass
class RewardShapingConfig:
    drawdown_penalty: DrawdownPenaltyConfig = field(default_factory=DrawdownPenaltyConfig)
    benchmark_relative: BenchmarkRelativeRewardConfig = field(default_factory=BenchmarkRelativeRewardConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "drawdown_penalty": self.drawdown_penalty.to_dict(),
            "benchmark_relative": self.benchmark_relative.to_dict(),
        }


@dataclass
class TrainEpisodeSamplingConfig:
    enabled: bool = True
    mode: str = "fraction"
    min_fraction: float = 0.05
    max_fraction: float = 0.25

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EnvConfig:
    train_split: float = 0.7
    val_split: float = 0.15
    min_hold_days: int = 3
    buy_fee_rate: float = 0.003
    sell_fee_rate: float = 0.003
    capital_gains_tax_rate: float = 0.001
    stop_loss: float | None = 0.05
    lookback_window: int = 90
    reward_shaping: RewardShapingConfig = field(default_factory=RewardShapingConfig)
    train_episode_sampling: TrainEpisodeSamplingConfig = field(default_factory=TrainEpisodeSamplingConfig)
    start_episode_position: float = 0.3
    input_features: FeatureConfig = field(default_factory=FeatureConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "train_split": self.train_split,
            "val_split": self.val_split,
            "min_hold_days": self.min_hold_days,
            "buy_fee_rate": self.buy_fee_rate,
            "sell_fee_rate": self.sell_fee_rate,
            "capital_gains_tax_rate": self.capital_gains_tax_rate,
            "stop_loss": self.stop_loss,
            "lookback_window": self.lookback_window,
            "reward_shaping": self.reward_shaping.to_dict(),
            "train_episode_sampling": self.train_episode_sampling.to_dict(),
            "start_episode_position": self.start_episode_position,
            "input_features": self.input_features.to_dict(),
        }


@dataclass
class TrainingConfig:
    data_dir: str = str(default_stock_data_dir())
    market_data_dir: str = str(default_market_data_dir())
    help_assets_dir: str = str(default_help_assets_dir())
    total_timesteps: int = 500_000
    model_name: str = "ppo_trading"
    save_dir: str = "artifacts/trained_models"
    log_dir: str = "artifacts/trained_models"
    checkpoint_freq: int = 50_000
    n_envs: int = 4
    policy: str = "mlp"
    ent_coef_start: float = 0.01
    ent_coef_end: float = 0.0
    ent_coef_schedule: str = "constant"
    eval_freq: int = 50_000
    n_eval_episodes: int = 5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationConfig:
    model_path: str = "artifacts/trained_models/ppo_trading/model_final.zip"
    data_dir: str = str(default_stock_data_dir())
    market_data_dir: str = str(default_market_data_dir())
    help_assets_dir: str = str(default_help_assets_dir())
    mode: str = "test"
    output_dir: str = "artifacts/evaluation_results"
    metrics_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyConfig:
    model_kwargs: dict[str, Any]
    policy_kwargs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"model_kwargs": dict(self.model_kwargs), "policy_kwargs": dict(self.policy_kwargs)}
