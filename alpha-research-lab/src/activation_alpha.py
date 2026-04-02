from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from src.repo_paths import data_path
from typing import Callable, Iterable, Mapping, Sequence
import sys

import numpy as np
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))

from shared_market_rules import required_holding_age_for_sell

from src.deterministic_portfolio import (
    MarketInputs,
    compute_strategy_scores,
    load_benchmark_open,
    load_or_build_tradability_panel,
    load_price_panel,
    resolve_strategy_columns,
    simulate_strategy,
)
from src.portfolio_friction_features import build_friction_feature_frame

RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
DISPERSION_PATH = data_path("features/xs_dispersion_regime_daily.parquet")
MACRO_PATH = data_path("features/macro_regime_daily.parquet")
SECTOR_ROTATION_PATH = data_path("features/xs_sector_rotation_daily.parquet")
ACTIVATION_STATE_PATH = data_path("features/activation_state_daily.parquet")


@dataclass(frozen=True)
class SelectorDefinition:
    name: str
    strategy_name: str
    signal_columns: tuple[str, ...]
    top_k: int
    rebalance_every: int
    weighting: str = "equal"


@dataclass(frozen=True)
class ActivationExperimentInputs:
    matrix: pd.DataFrame
    scored: pd.DataFrame
    price_panel: pd.DataFrame
    tradability: pd.DataFrame
    market_inputs: MarketInputs
    selectors: tuple[SelectorDefinition, ...]


def selector_definitions(matrix_columns: Sequence[str]) -> tuple[SelectorDefinition, ...]:
    full_cols = tuple(resolve_strategy_columns(list(matrix_columns), "full_library"))
    s1_cols = tuple(resolve_strategy_columns(list(matrix_columns), "s1_only"))
    return (
        SelectorDefinition(
            name="full_library_k5_r5_eq",
            strategy_name="full_library",
            signal_columns=full_cols,
            top_k=5,
            rebalance_every=5,
            weighting="equal",
        ),
        SelectorDefinition(
            name="s1_only_k5_r5_eq",
            strategy_name="s1_only",
            signal_columns=s1_cols,
            top_k=5,
            rebalance_every=5,
            weighting="equal",
        ),
    )


def load_activation_experiment_inputs(
    *,
    matrix_path: Path = RL_MATRIX_PATH,
    tradability_path: Path = TRADABILITY_PATH,
    stock_dir: Path = STOCK_DIR,
    benchmark_path: Path = BENCHMARK_PATH,
    start_year: int = 2019,
    end_year: int = 2025,
) -> ActivationExperimentInputs:
    matrix = pd.read_parquet(matrix_path)
    matrix["time"] = pd.to_datetime(matrix["time"])
    matrix = matrix[(matrix["time"].dt.year >= start_year) & (matrix["time"].dt.year <= end_year)].copy()
    if matrix.empty:
        raise ValueError(f"No matrix rows in year range {start_year}-{end_year}")

    selectors = selector_definitions(matrix.columns.tolist())
    strategy_map = {selector.strategy_name: list(selector.signal_columns) for selector in selectors}
    scored = compute_strategy_scores(matrix, strategy_map)

    price_panel = load_price_panel(scored["ticker"].unique().tolist(), stock_dir)
    if price_panel.empty:
        raise ValueError(f"No price rows found under {stock_dir}")
    tradability, tradability_source = load_or_build_tradability_panel(price_panel, tradability_path)
    benchmark_open = load_benchmark_open(benchmark_path)
    from src.deterministic_portfolio import build_market_inputs

    market_inputs = build_market_inputs(
        scored,
        price_panel,
        tradability,
        benchmark_open,
        tradability_source=tradability_source,
        strategy_names=[selector.strategy_name for selector in selectors],
        start_year=int(start_year),
        end_year=int(end_year),
    )
    return ActivationExperimentInputs(
        matrix=matrix,
        scored=scored,
        price_panel=price_panel,
        tradability=tradability,
        market_inputs=market_inputs,
        selectors=selectors,
    )


def _safe_mean(values: pd.Series | np.ndarray) -> float:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 0.0
    return float(arr.mean())


def _safe_std(values: pd.Series | np.ndarray) -> float:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size <= 1:
        return 0.0
    return float(arr.std(ddof=0))


def _normalized_entropy(values: pd.Series | np.ndarray) -> float:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 0.0
    weights = np.clip(arr, 0.0, None)
    if not np.isfinite(weights).any() or float(weights.sum()) <= 0.0:
        return 0.0
    probs = weights / float(weights.sum())
    probs = probs[probs > 0.0]
    if probs.size <= 1:
        return 0.0
    entropy = -np.sum(probs * np.log(probs))
    return float(entropy / np.log(float(len(probs))))


def _build_selector_snapshot(group: pd.DataFrame, *, score_column: str, prefix: str) -> dict[str, object]:
    ranked = group.sort_values(by=[score_column, "ticker"], ascending=[False, True], ignore_index=True)
    top1 = ranked.head(1)
    top3 = ranked.head(3)
    top5 = ranked.head(5)
    top10 = ranked.head(10)
    liq_open_mask_top5 = (
        (pd.to_numeric(top5["tv_to_adv20"], errors="coerce") >= 1.25)
        & (pd.to_numeric(top5["clv"], errors="coerce") >= 0.50)
        & top5["can_buy_next_open"].astype(bool)
    )
    liq_open_mask_top10 = (
        (pd.to_numeric(top10["tv_to_adv20"], errors="coerce") >= 1.25)
        & (pd.to_numeric(top10["clv"], errors="coerce") >= 0.50)
        & top10["can_buy_next_open"].astype(bool)
    )
    row = {
        f"{prefix}_top1_score": _safe_mean(top1[score_column]),
        f"{prefix}_top3_mean_score": _safe_mean(top3[score_column]),
        f"{prefix}_top5_mean_score": _safe_mean(top5[score_column]),
        f"{prefix}_top1_minus_top5_spread": _safe_mean(top1[score_column]) - _safe_mean(top5[score_column]),
        f"{prefix}_top5_score_std": _safe_std(top5[score_column]),
        f"{prefix}_top10_score_entropy": _normalized_entropy(top10[score_column]),
        f"{prefix}_top5_buyable_count": int(top5["can_buy_next_open"].astype(bool).sum()),
        f"{prefix}_top10_buyable_count": int(top10["can_buy_next_open"].astype(bool).sum()),
        f"{prefix}_top5_liq_open_count": int(liq_open_mask_top5.sum()),
        f"{prefix}_top10_liq_open_count": int(liq_open_mask_top10.sum()),
        f"{prefix}_top5_blocked_buy_count": int(len(top5) - top5["can_buy_next_open"].astype(bool).sum()),
        f"{prefix}_top10_blocked_buy_count": int(len(top10) - top10["can_buy_next_open"].astype(bool).sum()),
        f"{prefix}_top5_mean_adv20_rank": _safe_mean(top5["xs_adv20_rank"]),
        f"{prefix}_top10_mean_adv20_rank": _safe_mean(top10["xs_adv20_rank"]),
        f"{prefix}_top5_mean_tv_to_adv20_rank": _safe_mean(top5["xs_tv_to_adv20_rank"]),
        f"{prefix}_top10_mean_tv_to_adv20_rank": _safe_mean(top10["xs_tv_to_adv20_rank"]),
        f"{prefix}_top5_mean_clv": _safe_mean(top5["clv"]),
        f"{prefix}_top10_mean_clv": _safe_mean(top10["clv"]),
        f"{prefix}_top5_mean_sector_breadth": _safe_mean(top5.get("xs_sector_breadth_5d", pd.Series(dtype=float))),
        f"{prefix}_top5_mean_sector_mom": _safe_mean(top5.get("xs_sector_mom_5d_rank", pd.Series(dtype=float))),
        f"{prefix}_top1_ticker": str(top1.iloc[0]["ticker"]) if not top1.empty else "",
        f"{prefix}_top5_tickers": tuple(str(value) for value in top5["ticker"].tolist()),
    }
    return row


def _load_benchmark_state_features(benchmark_path: Path) -> pd.DataFrame:
    benchmark = pd.read_parquet(benchmark_path, columns=["time", "close"]).copy()
    benchmark["time"] = pd.to_datetime(benchmark["time"])
    benchmark = benchmark.sort_values("time").drop_duplicates("time")
    close = pd.to_numeric(benchmark["close"], errors="coerce")
    ma20 = close.rolling(20, min_periods=5).mean()
    ma50 = close.rolling(50, min_periods=10).mean()
    cc_ret = close.pct_change()
    realized_vol_20d = cc_ret.rolling(20, min_periods=5).std()
    peak60 = close.rolling(60, min_periods=10).max()
    out = pd.DataFrame(
        {
            "time": benchmark["time"],
            "vni_ret_5d": close.pct_change(5),
            "vni_ret_20d": close.pct_change(20),
            "vni_above_ma20": (close > ma20).astype(float),
            "vni_above_ma50": (close > ma50).astype(float),
            "vni_realized_vol_20d": realized_vol_20d,
            "vni_drawdown_60d": close / peak60 - 1.0,
        }
    )
    for column in out.columns:
        if column != "time":
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def build_activation_state_frame(
    *,
    matrix: pd.DataFrame,
    price_panel: pd.DataFrame,
    tradability: pd.DataFrame,
    benchmark_path: Path = BENCHMARK_PATH,
    dispersion_path: Path = DISPERSION_PATH,
    macro_path: Path = MACRO_PATH,
    sector_rotation_path: Path = SECTOR_ROTATION_PATH,
) -> pd.DataFrame:
    selectors = selector_definitions(matrix.columns.tolist())
    strategy_map = {selector.strategy_name: list(selector.signal_columns) for selector in selectors}
    scored = compute_strategy_scores(matrix, strategy_map)
    friction = build_friction_feature_frame(scored, price_panel, tradability)

    if sector_rotation_path.exists():
        sector_cols = ["time", "ticker", "xs_sector_breadth_5d", "xs_sector_mom_5d_rank"]
        sector = pd.read_parquet(sector_rotation_path, columns=sector_cols)
        sector["time"] = pd.to_datetime(sector["time"])
        friction = friction.merge(sector, on=["time", "ticker"], how="left", validate="one_to_one")
    else:
        friction["xs_sector_breadth_5d"] = np.nan
        friction["xs_sector_mom_5d_rank"] = np.nan

    rows: list[dict[str, object]] = []
    prev_top5: dict[str, set[str]] = {"full": set(), "s1": set()}
    prev_top1: dict[str, str] = {"full": "", "s1": ""}
    for time, group in friction.groupby("time", sort=True):
        row = {"time": pd.Timestamp(time)}
        row.update(_build_selector_snapshot(group, score_column="score__full_library", prefix="full"))
        row.update(_build_selector_snapshot(group, score_column="score__s1_only", prefix="s1"))
        full_top5 = set(row["full_top5_tickers"])
        s1_top5 = set(row["s1_top5_tickers"])
        union = full_top5 | s1_top5
        overlap = len(full_top5 & s1_top5)
        liq_open_all = (
            (pd.to_numeric(group["tv_to_adv20"], errors="coerce") >= 1.25)
            & (pd.to_numeric(group["clv"], errors="coerce") >= 0.50)
            & group["can_buy_next_open"].astype(bool)
        )
        row.update(
            {
                "selector_top5_overlap": int(overlap),
                "selector_top5_jaccard": float(overlap / max(len(union), 1)),
                "selector_top1_agree": float(row["full_top1_ticker"] == row["s1_top1_ticker"]),
                "buyable_breadth_all": float(group["can_buy_next_open"].astype(bool).mean()),
                "liq_open_breadth_all": float(liq_open_all.mean()),
                "candidate_count": int(len(group)),
                "full_top5_prev_overlap_ratio": float(len(full_top5 & prev_top5["full"]) / max(len(full_top5 | prev_top5["full"]), 1)),
                "s1_top5_prev_overlap_ratio": float(len(s1_top5 & prev_top5["s1"]) / max(len(s1_top5 | prev_top5["s1"]), 1)),
                "full_top1_prev_same": float(row["full_top1_ticker"] == prev_top1["full"]),
                "s1_top1_prev_same": float(row["s1_top1_ticker"] == prev_top1["s1"]),
            }
        )
        prev_top5["full"] = full_top5
        prev_top5["s1"] = s1_top5
        prev_top1["full"] = str(row["full_top1_ticker"])
        prev_top1["s1"] = str(row["s1_top1_ticker"])
        rows.append(row)

    daily = pd.DataFrame(rows).sort_values("time").reset_index(drop=True)
    daily = daily.drop(columns=["full_top5_tickers", "s1_top5_tickers", "full_top1_ticker", "s1_top1_ticker"])

    if dispersion_path.exists():
        dispersion = pd.read_parquet(dispersion_path)
        dispersion["time"] = pd.to_datetime(dispersion["time"])
        daily = daily.merge(dispersion, on="time", how="left")

    if macro_path.exists():
        macro = pd.read_parquet(macro_path)
        macro["time"] = pd.to_datetime(macro["time"])
        keep = [
            "time",
            "vix_mom_20d",
            "vix_vs_ma60",
            "breadth_score",
            "credit_risk_on",
            "vnm_vs_vni_20d",
            "news_surge_5d",
        ]
        macro = macro[[column for column in keep if column in macro.columns]].copy()
        daily = daily.merge(macro, on="time", how="left")

    benchmark_state = _load_benchmark_state_features(benchmark_path)
    daily = daily.merge(benchmark_state, on="time", how="left")

    for column in daily.columns:
        if column == "time":
            continue
        daily[column] = pd.to_numeric(daily[column], errors="coerce")
    daily = daily.sort_values("time").reset_index(drop=True)
    return daily


def persist_activation_state(
    *,
    matrix_path: Path = RL_MATRIX_PATH,
    tradability_path: Path = TRADABILITY_PATH,
    stock_dir: Path = STOCK_DIR,
    benchmark_path: Path = BENCHMARK_PATH,
    out_path: Path = ACTIVATION_STATE_PATH,
    start_year: int = 2015,
    end_year: int = 2025,
) -> pd.DataFrame:
    inputs = load_activation_experiment_inputs(
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        start_year=start_year,
        end_year=end_year,
    )
    frame = build_activation_state_frame(
        matrix=inputs.matrix,
        price_panel=inputs.price_panel,
        tradability=inputs.tradability,
        benchmark_path=benchmark_path,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out_path, index=False)
    return frame


def load_or_build_activation_state(
    *,
    out_path: Path = ACTIVATION_STATE_PATH,
    matrix_path: Path = RL_MATRIX_PATH,
    tradability_path: Path = TRADABILITY_PATH,
    stock_dir: Path = STOCK_DIR,
    benchmark_path: Path = BENCHMARK_PATH,
    start_year: int = 2015,
    end_year: int = 2025,
) -> tuple[pd.DataFrame, str]:
    required_columns = {
        "full_top5_mean_clv",
        "s1_top5_mean_clv",
        "full_top5_prev_overlap_ratio",
        "s1_top5_prev_overlap_ratio",
        "full_top1_prev_same",
        "s1_top1_prev_same",
    }
    if out_path.exists():
        frame = pd.read_parquet(out_path)
        frame["time"] = pd.to_datetime(frame["time"])
        if required_columns.issubset(frame.columns):
            return frame, "artifact"
    frame = persist_activation_state(
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        out_path=out_path,
        start_year=start_year,
        end_year=end_year,
    )
    return frame, "built"


def align_activation_mask(
    activation_state: pd.DataFrame,
    *,
    dates: Iterable[pd.Timestamp],
    value_column: str,
) -> np.ndarray:
    series = activation_state[["time", value_column]].copy()
    series["time"] = pd.to_datetime(series["time"])
    aligned = series.drop_duplicates("time").set_index("time")[value_column].reindex(pd.to_datetime(list(dates)))
    return aligned.where(pd.notna(aligned), False).astype(bool).to_numpy()


def align_activation_values(
    activation_state: pd.DataFrame,
    *,
    dates: Iterable[pd.Timestamp],
    value_column: str,
    fill_value: float = 0.0,
) -> np.ndarray:
    series = activation_state[["time", value_column]].copy()
    series["time"] = pd.to_datetime(series["time"])
    aligned = series.drop_duplicates("time").set_index("time")[value_column].reindex(pd.to_datetime(list(dates)))
    values = pd.to_numeric(aligned, errors="coerce").fillna(float(fill_value))
    return np.clip(values.to_numpy(dtype=np.float64), 0.0, 1.0)


def compute_cycle_metrics(daily: pd.DataFrame) -> dict[str, object]:
    if daily.empty or "rebalance_triggered" not in daily.columns:
        return {
            "cycle_count": 0,
            "active_cycle_count": 0,
            "active_cycle_hit_rate": None,
            "avg_active_cycle_return": None,
            "avg_off_cycle_return": None,
            "activation_on_rate": None,
            "avg_activation_scale": None,
        }

    work = daily.reset_index(drop=True).copy()
    rebalance_idx = np.flatnonzero(work["rebalance_triggered"].fillna(False).to_numpy(dtype=bool))
    if rebalance_idx.size == 0:
        return {
            "cycle_count": 0,
            "active_cycle_count": 0,
            "active_cycle_hit_rate": None,
            "avg_active_cycle_return": None,
            "avg_off_cycle_return": None,
            "activation_on_rate": None,
            "avg_activation_scale": None,
        }

    rows: list[dict[str, object]] = []
    for pos, start in enumerate(rebalance_idx):
        end = int(rebalance_idx[pos + 1]) if pos + 1 < len(rebalance_idx) else int(len(work))
        cycle = work.iloc[int(start):end]
        cycle_ret = float(np.prod(1.0 + cycle["portfolio_return"].to_numpy(dtype=np.float64)) - 1.0)
        activation_on = bool(cycle.iloc[0]["activation_on"])
        activation_scale = float(cycle.iloc[0]["activation_scale"]) if "activation_scale" in cycle.columns else float(activation_on)
        rows.append(
            {
                "cycle_start": pd.Timestamp(cycle.iloc[0]["signal_date"]),
                "activation_on": activation_on,
                "activation_scale": activation_scale,
                "cycle_return": cycle_ret,
            }
        )

    cycles = pd.DataFrame(rows)
    active = cycles.loc[cycles["activation_on"]]
    off = cycles.loc[~cycles["activation_on"]]
    return {
        "cycle_count": int(len(cycles)),
        "active_cycle_count": int(len(active)),
        "active_cycle_hit_rate": round(float((active["cycle_return"] > 0.0).mean()), 6) if not active.empty else None,
        "avg_active_cycle_return": round(float(active["cycle_return"].mean()), 6) if not active.empty else None,
        "avg_off_cycle_return": round(float(off["cycle_return"].mean()), 6) if not off.empty else None,
        "activation_on_rate": round(float(cycles["activation_on"].mean()), 6),
        "avg_activation_scale": round(float(cycles["activation_scale"].mean()), 6),
    }


def sort_activation_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    return results.sort_values(
        by=[
            "relative_total_return",
            "information_ratio_annualized",
            "portfolio_total_return",
            "max_drawdown",
            "activation_on_rate",
            "selector_name",
            "gate_name",
        ],
        ascending=[False, False, False, False, False, True, True],
        ignore_index=True,
    )


def run_activation_scenarios(
    *,
    activation_state: pd.DataFrame,
    market_inputs: MarketInputs,
    selectors: Sequence[SelectorDefinition],
    gates: Mapping[str, pd.Series | np.ndarray] | None = None,
    gates_by_selector: Mapping[str, Mapping[str, pd.Series | np.ndarray]] | None = None,
    initial_notional_vnd: float = 100_000_000.0,
    round_trip_cost: float = 0.003,
    capital_gains_tax_rate: float = 0.0,
    required_holding_age: int = 3,
) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    if gates is None and gates_by_selector is None:
        raise ValueError("Provide either gates or gates_by_selector")
    fee_leg = float(round_trip_cost) / 2.0
    hold_age = required_holding_age_for_sell(min_hold_days_override=int(required_holding_age))
    rows: list[dict[str, object]] = []
    daily_outputs: dict[tuple[str, str], pd.DataFrame] = {}

    base_results: dict[str, dict[str, object]] = {}
    for selector in selectors:
        base_result = simulate_strategy(
            strategy_name=selector.strategy_name,
            signal_columns=list(selector.signal_columns),
            market_inputs=market_inputs,
            top_k=int(selector.top_k),
            rebalance_every=int(selector.rebalance_every),
            weighting=str(selector.weighting),
            initial_notional_vnd=float(initial_notional_vnd),
            max_adv_participation=0.0,
            required_holding_age=int(hold_age),
            buy_fee_rate=float(fee_leg),
            sell_fee_rate=float(fee_leg),
            capital_gains_tax_rate=float(capital_gains_tax_rate),
        )
        cycle_metrics = compute_cycle_metrics(base_result.daily)
        base_row = {
            "selector_name": selector.name,
            "selector_strategy": selector.strategy_name,
            "top_k": int(selector.top_k),
            "rebalance_every": int(selector.rebalance_every),
            "weighting": str(selector.weighting),
            "gate_name": "always_on",
            "gate_family": "always_on",
        }
        base_row.update(base_result.summary)
        base_row.update(cycle_metrics)
        base_row["delta_relative_total_return_vs_always_on"] = 0.0
        base_row["delta_information_ratio_vs_always_on"] = 0.0
        rows.append(base_row)
        daily_outputs[(selector.name, "always_on")] = base_result.daily
        base_results[selector.name] = base_row

    for selector in selectors:
        base_row = base_results[selector.name]
        selector_gates = gates_by_selector.get(selector.name, {}) if gates_by_selector is not None else gates
        if selector_gates is None:
            continue
        for gate_name, mask_like in selector_gates.items():
            raw = np.asarray(mask_like)
            if raw.shape != (len(market_inputs.dates),):
                raise ValueError(
                    f"Gate {gate_name!r} has shape {raw.shape}; expected {(len(market_inputs.dates),)}"
                )
            activation_scale = np.clip(
                np.nan_to_num(raw.astype(np.float64), nan=0.0, posinf=1.0, neginf=0.0),
                0.0,
                1.0,
            )
            result = simulate_strategy(
                strategy_name=selector.strategy_name,
                signal_columns=list(selector.signal_columns),
                market_inputs=market_inputs,
                top_k=int(selector.top_k),
                rebalance_every=int(selector.rebalance_every),
                weighting=str(selector.weighting),
                initial_notional_vnd=float(initial_notional_vnd),
                max_adv_participation=0.0,
                required_holding_age=int(hold_age),
                buy_fee_rate=float(fee_leg),
                sell_fee_rate=float(fee_leg),
                capital_gains_tax_rate=float(capital_gains_tax_rate),
                activation_scale=activation_scale,
            )
            cycle_metrics = compute_cycle_metrics(result.daily)
            row = {
                "selector_name": selector.name,
                "selector_strategy": selector.strategy_name,
                "top_k": int(selector.top_k),
                "rebalance_every": int(selector.rebalance_every),
                "weighting": str(selector.weighting),
                "gate_name": str(gate_name),
                "gate_family": str(gate_name).split("__", 1)[0],
            }
            row.update(result.summary)
            row.update(cycle_metrics)
            row["delta_relative_total_return_vs_always_on"] = round(
                float(result.summary["relative_total_return"]) - float(base_row["relative_total_return"]),
                6,
            )
            row["delta_information_ratio_vs_always_on"] = round(
                float((result.summary.get("information_ratio_annualized") or 0.0))
                - float((base_row.get("information_ratio_annualized") or 0.0)),
                6,
            )
            rows.append(row)
            daily_outputs[(selector.name, str(gate_name))] = result.daily

    results = pd.DataFrame(rows)
    return sort_activation_results(results), daily_outputs


def build_quantile_gate(
    series: pd.Series,
    *,
    quantile: float,
    operator: str = ">=",
) -> pd.Series:
    threshold = float(pd.to_numeric(series, errors="coerce").quantile(float(quantile)))
    numeric = pd.to_numeric(series, errors="coerce")
    if operator == ">=":
        return numeric >= threshold
    if operator == "<=":
        return numeric <= threshold
    raise ValueError(f"Unsupported operator {operator!r}")


def build_threshold_gate(series: pd.Series, *, threshold: float, operator: str = ">=") -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if operator == ">=":
        return numeric >= float(threshold)
    if operator == "<=":
        return numeric <= float(threshold)
    raise ValueError(f"Unsupported operator {operator!r}")
