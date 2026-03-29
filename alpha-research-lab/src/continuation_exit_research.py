from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.exit_experiment_utils import load_full_library_backbone
from src.research_protocol import DEFAULT_PROTOCOL, assign_research_phase


CONTINUATION_HORIZON_DAYS = 5
BASE_CONTINUATION_FEATURES = [
    "holding_age_before",
    "score_change_since_entry",
    "return_since_entry",
    "peak_return_since_entry",
    "underwater_days_since_entry",
    "blocked_sell_streak",
]


@dataclass(frozen=True)
class ContinuationModelSpec:
    name: str
    feature_columns: tuple[str, ...]


@dataclass(frozen=True)
class ContinuationModelFit:
    spec: ContinuationModelSpec
    intercept: float
    raw_coefficients: dict[str, float]
    scored_dataset: pd.DataFrame
    summary_row: dict[str, object]


@dataclass(frozen=True)
class ContinuationDatasetBundle:
    market_inputs: object
    panel: pd.DataFrame
    baseline_daily: pd.DataFrame
    baseline_blotter: pd.DataFrame


def build_continuation_dataset(
    *,
    matrix_path: Path,
    tradability_path: Path,
    stock_dir: Path,
    benchmark_path: Path,
    start_year: int,
    end_year: int,
    required_holding_age: int,
    initial_notional_vnd: float,
    round_trip_cost: float,
    horizon_days: int = CONTINUATION_HORIZON_DAYS,
) -> ContinuationDatasetBundle:
    from src.deterministic_portfolio import simulate_strategy

    _, _, market_inputs = load_full_library_backbone(
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        start_year=int(start_year),
        end_year=int(end_year),
    )
    fee_leg = float(round_trip_cost) / 2.0
    baseline = simulate_strategy(
        strategy_name="full_library",
        signal_columns=["full_library"],
        market_inputs=market_inputs,
        top_k=5,
        rebalance_every=5,
        weighting="equal",
        initial_notional_vnd=float(initial_notional_vnd),
        max_adv_participation=0.0,
        required_holding_age=int(required_holding_age),
        buy_fee_rate=float(fee_leg),
        sell_fee_rate=float(fee_leg),
        capital_gains_tax_rate=0.0,
        capture_blotter=True,
    )
    if baseline.blotter is None or baseline.blotter.empty:
        raise ValueError("Baseline blotter is empty; cannot build continuation dataset")

    panel = baseline.blotter.copy()
    panel = panel.loc[
        panel["held_before"].fillna(False).astype(bool)
        & panel["can_sell_next_open"].fillna(False).astype(bool)
        & (pd.to_numeric(panel["holding_age_before"], errors="coerce").fillna(0) >= int(required_holding_age))
    ].copy()
    if panel.empty:
        raise ValueError("No legal held-position rows available for continuation labeling")

    dates = pd.to_datetime(market_inputs.dates)
    date_to_idx = {pd.Timestamp(ts): idx for idx, ts in enumerate(dates)}
    ticker_to_idx = {ticker: idx for idx, ticker in enumerate(market_inputs.tickers)}
    open_matrix = np.asarray(market_inputs.open_matrix, dtype=np.float64)
    benchmark_open = np.asarray(market_inputs.benchmark_open, dtype=np.float64)

    hold_advantages: list[float] = []
    future_stock_returns: list[float] = []
    future_benchmark_returns: list[float] = []
    future_end_dates: list[str | None] = []
    valid_mask: list[bool] = []
    for row in panel.itertuples(index=False):
        execution_date = pd.Timestamp(row.execution_date)
        ticker = str(row.ticker)
        exec_idx = date_to_idx.get(execution_date)
        ticker_idx = ticker_to_idx.get(ticker)
        if exec_idx is None or ticker_idx is None:
            hold_advantages.append(np.nan)
            future_stock_returns.append(np.nan)
            future_benchmark_returns.append(np.nan)
            future_end_dates.append(None)
            valid_mask.append(False)
            continue
        future_idx = min(exec_idx + int(horizon_days), len(dates) - 1)
        open_entry = open_matrix[exec_idx, ticker_idx]
        open_future = open_matrix[future_idx, ticker_idx]
        bench_entry = benchmark_open[exec_idx]
        bench_future = benchmark_open[future_idx]
        if not (np.isfinite(open_entry) and np.isfinite(open_future) and open_entry > 0.0 and open_future > 0.0):
            hold_advantages.append(np.nan)
            future_stock_returns.append(np.nan)
            future_benchmark_returns.append(np.nan)
            future_end_dates.append(None)
            valid_mask.append(False)
            continue
        stock_return = float(open_future / open_entry - 1.0)
        benchmark_return = float(bench_future / bench_entry - 1.0) if np.isfinite(bench_entry) and np.isfinite(bench_future) and bench_entry > 0.0 and bench_future > 0.0 else 0.0
        hold_advantages.append(stock_return - benchmark_return)
        future_stock_returns.append(stock_return)
        future_benchmark_returns.append(benchmark_return)
        future_end_dates.append(pd.Timestamp(dates[future_idx]).isoformat())
        valid_mask.append(True)

    panel["future_end_date"] = future_end_dates
    panel["future_stock_return_5d"] = future_stock_returns
    panel["future_benchmark_return_5d"] = future_benchmark_returns
    panel["future_hold_advantage_5d"] = hold_advantages
    panel["continuation_label"] = (pd.to_numeric(panel["future_hold_advantage_5d"], errors="coerce") > 0.0).astype(float)
    panel = panel.loc[np.asarray(valid_mask, dtype=bool)].copy()
    panel["time"] = pd.to_datetime(panel["signal_date"])
    panel = assign_research_phase(panel, date_column="time", protocol=DEFAULT_PROTOCOL)
    return ContinuationDatasetBundle(
        market_inputs=market_inputs,
        panel=panel.reset_index(drop=True),
        baseline_daily=baseline.daily.copy(),
        baseline_blotter=baseline.blotter.copy(),
    )


def _top_bucket_advantage(frame: pd.DataFrame, *, score_column: str, advantage_column: str, q: float = 0.2) -> float | None:
    if frame.empty:
        return None
    work = frame[[score_column, advantage_column]].copy()
    work[score_column] = pd.to_numeric(work[score_column], errors="coerce")
    work[advantage_column] = pd.to_numeric(work[advantage_column], errors="coerce")
    work = work.dropna()
    if work.empty:
        return None
    threshold = float(work[score_column].quantile(1.0 - float(q)))
    bucket = work.loc[work[score_column] >= threshold, advantage_column]
    if bucket.empty:
        return None
    return float(bucket.mean())


def _phase_metrics(frame: pd.DataFrame, *, prob_column: str) -> dict[str, float | None]:
    if frame.empty:
        return {
            "count": 0,
            "auc": None,
            "mean_hold_advantage": None,
            "top_quintile_hold_advantage": None,
            "positive_rate": None,
        }
    work = frame.copy()
    work["continuation_label"] = pd.to_numeric(work["continuation_label"], errors="coerce")
    work[prob_column] = pd.to_numeric(work[prob_column], errors="coerce")
    work["future_hold_advantage_5d"] = pd.to_numeric(work["future_hold_advantage_5d"], errors="coerce")
    work = work.dropna(subset=["continuation_label", prob_column, "future_hold_advantage_5d"])
    if work.empty:
        return {
            "count": 0,
            "auc": None,
            "mean_hold_advantage": None,
            "top_quintile_hold_advantage": None,
            "positive_rate": None,
        }
    y = work["continuation_label"].astype(int)
    auc = None
    if y.nunique() >= 2:
        auc = float(roc_auc_score(y, work[prob_column].astype(float)))
    return {
        "count": int(len(work)),
        "auc": auc,
        "mean_hold_advantage": float(work["future_hold_advantage_5d"].mean()),
        "top_quintile_hold_advantage": _top_bucket_advantage(work, score_column=prob_column, advantage_column="future_hold_advantage_5d", q=0.2),
        "positive_rate": float(y.mean()),
    }


def fit_continuation_model(
    panel: pd.DataFrame,
    *,
    spec: ContinuationModelSpec,
) -> ContinuationModelFit:
    required = list(spec.feature_columns)
    missing = [column for column in required if column not in panel.columns]
    if missing:
        raise ValueError(f"Missing continuation features for {spec.name}: {missing}")

    work = panel.copy()
    for column in required:
        work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0.0)
    work["continuation_label"] = pd.to_numeric(work["continuation_label"], errors="coerce").fillna(0.0)
    train = work.loc[work["research_phase"] == "dev"].copy()
    if train.empty or train["continuation_label"].nunique() < 2:
        raise ValueError(f"Insufficient dev labels to fit continuation model {spec.name}")

    X_train = train[list(spec.feature_columns)].to_numpy(dtype=np.float64)
    y_train = train["continuation_label"].astype(int).to_numpy()
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000, random_state=0)),
    ])
    pipeline.fit(X_train, y_train)
    scaler = pipeline.named_steps["scaler"]
    model = pipeline.named_steps["model"]
    scales = np.where(np.asarray(scaler.scale_, dtype=np.float64) == 0.0, 1.0, np.asarray(scaler.scale_, dtype=np.float64))
    raw_coef = np.asarray(model.coef_[0], dtype=np.float64) / scales
    raw_intercept = float(model.intercept_[0] - np.sum(np.asarray(model.coef_[0], dtype=np.float64) * np.asarray(scaler.mean_, dtype=np.float64) / scales))

    X_all = work[list(spec.feature_columns)].to_numpy(dtype=np.float64)
    probs = pipeline.predict_proba(X_all)[:, 1]
    scored = work.copy()
    scored["continuation_prob"] = probs

    row: dict[str, object] = {
        "model_name": spec.name,
        "feature_columns": list(spec.feature_columns),
        "intercept": raw_intercept,
    }
    for feature_name, coef in zip(spec.feature_columns, raw_coef):
        row[f"coef__{feature_name}"] = float(coef)
    for phase in ("dev", "validation", "confirmation"):
        metrics = _phase_metrics(scored.loc[scored["research_phase"] == phase].copy(), prob_column="continuation_prob")
        for key, value in metrics.items():
            row[f"{phase}_{key}"] = value
    promoted = bool(
        (row.get("validation_auc") is not None and float(row["validation_auc"]) >= 0.55)
        and (row.get("confirmation_auc") is not None and float(row["confirmation_auc"]) >= 0.52)
        and (row.get("validation_top_quintile_hold_advantage") is not None and float(row["validation_top_quintile_hold_advantage"]) > 0.0)
        and (row.get("confirmation_top_quintile_hold_advantage") is not None and float(row["confirmation_top_quintile_hold_advantage"]) > -0.01)
    )
    row["promoted"] = promoted
    return ContinuationModelFit(
        spec=spec,
        intercept=raw_intercept,
        raw_coefficients={feature: float(coef) for feature, coef in zip(spec.feature_columns, raw_coef)},
        scored_dataset=scored,
        summary_row=row,
    )
