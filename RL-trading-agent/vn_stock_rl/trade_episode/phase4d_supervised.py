"""Causal training examples and compact regressors for Phase 4D exit tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from vn_stock_rl.trade_episode.causal_features import CAUSAL_MARKET_FEATURE_NAMES
from vn_stock_rl.trade_episode.environment import annualized_log_excess_reward
from vn_stock_rl.trade_episode.phase4a_data import UNSEEN_TICKERS
from vn_stock_rl.trade_episode.signals import ALPHA_FEATURE_NAMES

PHASE4A_STATE_NAMES = (
    "position_in",
    "holding_intervals_normalized",
    "entry_relative_unrealized_log_return_scaled",
    "waiting_steps_normalized",
    "episode_steps_normalized",
)
ENTRY_VOL_FEATURE = "entry_time_log_volatility"
AGE_FEATURE = "holding_intervals_normalized"


@dataclass(frozen=True)
class ExitExamples:
    market_x: np.ndarray
    alpha_x: np.ndarray
    age_x: np.ndarray
    target: np.ndarray
    metadata: pd.DataFrame
    sample_weight: np.ndarray

    def matrix(self, feature_set: str) -> np.ndarray:
        matrices = {
            "market_only": self.market_x,
            "market_plus_alpha": self.alpha_x,
            "age_only": self.age_x,
        }
        try:
            return matrices[feature_set]
        except KeyError as exc:
            raise ValueError(f"Unknown Phase 4D feature set: {feature_set}") from exc


@dataclass
class FittedExitModel:
    model_id: str
    feature_set: str
    feature_names: tuple[str, ...]
    estimator: Any = None
    scaler: StandardScaler | None = None
    constant: float | None = None

    def predict(self, features: np.ndarray) -> np.ndarray:
        matrix = np.asarray(features, dtype=np.float64)
        if self.constant is not None:
            return np.full(matrix.shape[0], self.constant, dtype=np.float64)
        if self.estimator is None:
            raise RuntimeError(f"{self.model_id}: estimator is unavailable")
        if self.scaler is not None:
            matrix = self.scaler.transform(matrix)
        return np.asarray(self.estimator.predict(matrix), dtype=np.float64).reshape(-1)


def terminal_reward(entry_price: float, exit_price: float, holding_intervals: int) -> float:
    """Call the unchanged Phase 4A reward implementation."""

    return annualized_log_excess_reward(entry_price, exit_price, holding_intervals)


def counterfactual_exit_target(
    stock,
    *,
    decision_index: int,
    current_holding_age: int,
    partition_mask: np.ndarray,
) -> float | None:
    """Build R(HOLD three more intervals)-R(SELL now) using next-open fills.

    Current age is decision index minus entry-fill index. Age 2 is the first
    mask-valid decision because SELL fills one interval later.
    """

    age = int(current_holding_age)
    t = int(decision_index)
    entry_fill_index = t - age
    entry_decision_index = entry_fill_index - 1
    sell_now_decision = t
    sell_now_fill = t + 1
    hold_sell_decision = t + 3
    hold_sell_fill = t + 4
    mask = np.asarray(partition_mask, dtype=bool)
    if age < 2 or mask.shape != stock.can_buy.shape:
        return None
    if entry_decision_index < 0 or hold_sell_fill >= len(stock.opens):
        return None
    same_partition_indices = (
        entry_decision_index,
        entry_fill_index,
        t,
        hold_sell_decision,
        hold_sell_fill,
    )
    if not all(mask[index] for index in same_partition_indices):
        return None
    if not (
        stock.can_buy[entry_decision_index]
        and stock.can_sell[sell_now_decision]
        and stock.can_sell[hold_sell_decision]
    ):
        return None

    entry_price = float(stock.opens[entry_fill_index])
    reward_sell = terminal_reward(entry_price, float(stock.opens[sell_now_fill]), age + 1)
    reward_hold = terminal_reward(entry_price, float(stock.opens[hold_sell_fill]), age + 4)
    return float(reward_hold - reward_sell)


def feature_names() -> dict[str, tuple[str, ...]]:
    market = tuple(CAUSAL_MARKET_FEATURE_NAMES)
    alpha = tuple(ALPHA_FEATURE_NAMES)
    state = PHASE4A_STATE_NAMES
    return {
        "market_only": market + state + (ENTRY_VOL_FEATURE,),
        "market_plus_alpha": market + alpha + state + (ENTRY_VOL_FEATURE,),
        "age_only": (AGE_FEATURE,),
    }


def exit_feature_vector(
    stock,
    *,
    decision_index: int,
    current_holding_age: int,
    phase4a_state_config: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return market-only, market-plus-alpha, and age-only causal inputs."""

    t = int(decision_index)
    age = int(current_holding_age)
    entry_fill_index = t - age
    entry_decision_index = entry_fill_index - 1
    if age < 2 or entry_decision_index < 0 or t >= len(stock.dates):
        raise ValueError("Exit state is outside valid historical indices")
    holding_scale = int(phase4a_state_config["max_holding_intervals"])
    episode_scale = int(phase4a_state_config["max_episode_steps"])
    entry_vol = float(stock.daily_volatility_scale[entry_decision_index])
    if not np.isfinite(entry_vol) or entry_vol <= 0:
        raise ValueError("Entry-time volatility must be finite and positive")
    unrealized = (np.log(float(stock.closes[t])) - np.log(float(stock.opens[entry_fill_index]))) / (
        entry_vol * np.sqrt(max(1, age))
    )
    state = np.asarray(
        [
            1.0,
            age / holding_scale,
            unrealized,
            0.0,
            (age + 1) / episode_scale,
        ],
        dtype=np.float64,
    )
    market = np.asarray(stock.market_features[t], dtype=np.float64)
    alpha = np.asarray(stock.alpha_features[t], dtype=np.float64)
    entry_volatility = np.asarray([np.log(entry_vol)], dtype=np.float64)
    market_x = np.concatenate((market, state, entry_volatility))
    alpha_x = np.concatenate((market, alpha, state, entry_volatility))
    age_x = np.asarray([age / holding_scale], dtype=np.float64)
    if not np.isfinite(market_x).all() or not np.isfinite(alpha_x).all():
        raise ValueError("Phase 4D features must be finite")
    return market_x, alpha_x, age_x


def generate_exit_examples(
    stocks: dict[str, Any],
    *,
    tickers: tuple[str, ...],
    split: str,
    ages: tuple[int, ...],
    stride: int,
    phase4a_state_config: dict[str, Any],
) -> ExitExamples:
    """Generate age-stratified examples with partition-contained labels."""

    if split not in {"train", "validation", "exploratory"}:
        raise ValueError(f"Unknown chronological split: {split}")
    if stride < 5:
        raise ValueError("Sampling stride must be at least five to separate label windows")
    split_mask_name = "test" if split == "exploratory" else split
    market_rows: list[np.ndarray] = []
    alpha_rows: list[np.ndarray] = []
    age_rows: list[np.ndarray] = []
    targets: list[float] = []
    metadata: list[dict[str, Any]] = []
    for ticker in tickers:
        stock = stocks[ticker]
        partition = np.asarray(stock.split_masks[split_mask_name], dtype=bool)
        selected = np.flatnonzero(partition)
        if selected.size < 10:
            continue
        first, last = int(selected[0]), int(selected[-1])
        for age in ages:
            if age < 2:
                raise ValueError("The earliest mask-valid decision age is two intervals")
            first_decision = first + age + 1
            # HOLD's fill is t+4, so only dates through last-4 can be candidates.
            for decision_index in range(first_decision, last - 3, stride):
                target = counterfactual_exit_target(
                    stock,
                    decision_index=decision_index,
                    current_holding_age=age,
                    partition_mask=partition,
                )
                if target is None:
                    continue
                market_x, alpha_x, age_x = exit_feature_vector(
                    stock,
                    decision_index=decision_index,
                    current_holding_age=age,
                    phase4a_state_config=phase4a_state_config,
                )
                market_rows.append(market_x)
                alpha_rows.append(alpha_x)
                age_rows.append(age_x)
                targets.append(target)
                date = pd.Timestamp(stock.dates[decision_index]).normalize()
                metadata.append(
                    {
                        "ticker": ticker,
                        "ticker_group": (
                            "unseen_ticker" if ticker in UNSEEN_TICKERS else "training_universe"
                        ),
                        "date": str(date.date()),
                        "year": int(date.year),
                        "split": split,
                        "current_holding_age": age,
                    }
                )
    if not targets:
        raise ValueError(f"No eligible Phase 4D samples for split={split}")
    meta = pd.DataFrame(metadata)
    strata = meta.groupby(["ticker", "year", "current_holding_age"], sort=False).ngroup()
    counts = pd.Series(strata).value_counts().to_dict()
    weights = np.asarray([1.0 / counts[group] for group in strata], dtype=np.float64)
    weights *= len(weights) / weights.sum()
    return ExitExamples(
        market_x=np.vstack(market_rows),
        alpha_x=np.vstack(alpha_rows),
        age_x=np.vstack(age_rows),
        target=np.asarray(targets, dtype=np.float64),
        metadata=meta,
        sample_weight=weights,
    )


def _fit_ridge(
    model_id: str,
    feature_set: str,
    features: np.ndarray,
    target: np.ndarray,
    weights: np.ndarray,
    alpha: float,
    names: tuple[str, ...],
) -> FittedExitModel:
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)
    estimator = Ridge(alpha=float(alpha))
    estimator.fit(scaled, target, sample_weight=weights)
    return FittedExitModel(model_id, feature_set, names, estimator=estimator, scaler=scaler)


def fit_exit_models(
    train: ExitExamples,
    *,
    config: dict[str, Any],
) -> dict[str, FittedExitModel]:
    """Fit only the preregistered models; all normalization uses train rows."""

    names = feature_names()
    specs = config["models"]
    models: dict[str, FittedExitModel] = {}
    for model_id, feature_set in (
        ("ridge_market", "market_only"),
        ("ridge_market_alpha", "market_plus_alpha"),
        ("extra_trees_market", "market_only"),
        ("extra_trees_market_alpha", "market_plus_alpha"),
    ):
        spec = specs[model_id]
        x = train.matrix(feature_set)
        if spec["estimator"] == "StandardScaler + Ridge":
            models[model_id] = _fit_ridge(
                model_id,
                feature_set,
                x,
                train.target,
                train.sample_weight,
                float(spec["alpha"]),
                names[feature_set],
            )
        else:
            estimator = ExtraTreesRegressor(
                n_estimators=int(spec["n_estimators"]),
                max_depth=int(spec["max_depth"]),
                min_samples_leaf=int(spec["min_samples_leaf"]),
                max_features=float(spec["max_features"]),
                n_jobs=int(spec["n_jobs"]),
                random_state=int(spec["random_state"]),
            )
            estimator.fit(x, train.target, sample_weight=train.sample_weight)
            models[model_id] = FittedExitModel(
                model_id, feature_set, names[feature_set], estimator=estimator
            )
    age_spec = specs["age_only_ridge"]
    models["age_only_ridge"] = _fit_ridge(
        "age_only_ridge",
        "age_only",
        train.age_x,
        train.target,
        train.sample_weight,
        float(age_spec["alpha"]),
        names["age_only"],
    )
    constant = float(np.average(train.target, weights=train.sample_weight))
    models["constant_mean"] = FittedExitModel("constant_mean", "constant", (), constant=constant)
    return models


def prediction_quality(target: np.ndarray, prediction: np.ndarray) -> dict[str, float | int | None]:
    """Compute rank, error, sign, and class-imbalance metrics."""

    y = np.asarray(target, dtype=np.float64)
    pred = np.asarray(prediction, dtype=np.float64)
    valid = np.isfinite(y) & np.isfinite(pred)
    y, pred = y[valid], pred[valid]
    if not len(y):
        return {"rows": 0}
    truth_positive = y > 0.0
    pred_positive = pred > 0.0
    prevalence = float(truth_positive.mean())
    class_recalls: list[float] = []
    for label in (False, True):
        selected = truth_positive == label
        if selected.any():
            class_recalls.append(float((pred_positive[selected] == label).mean()))
    rho: float | None = None
    if len(y) >= 2 and np.ptp(y) > 0 and np.ptp(pred) > 0:
        y_rank = pd.Series(y).rank(method="average").to_numpy(dtype=np.float64)
        pred_rank = pd.Series(pred).rank(method="average").to_numpy(dtype=np.float64)
        rho = float(np.corrcoef(y_rank, pred_rank)[0, 1])
    return {
        "rows": int(len(y)),
        "spearman_rho": rho,
        "mae": float(np.mean(np.abs(pred - y))),
        "rmse": float(np.sqrt(np.mean(np.square(pred - y)))),
        "directional_accuracy": float(np.mean(pred_positive == truth_positive)),
        "positive_label_prevalence": prevalence,
        "majority_class_accuracy": max(prevalence, 1.0 - prevalence),
        "balanced_accuracy": float(np.mean(class_recalls)),
    }
