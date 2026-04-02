from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from src.repo_paths import data_path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from src.activation_alpha import (
    BENCHMARK_PATH,
    RL_MATRIX_PATH,
    STOCK_DIR,
    TRADABILITY_PATH,
    load_activation_experiment_inputs,
)
from src.activation_meta import ACTIVATION_META_PATH, load_or_build_activation_meta
from src.activation_meta_experiment_utils import selector_recent_relative_ewm_from_prev
from src.deterministic_portfolio import load_benchmark_open, simulate_strategy
from src.portfolio_friction_features import build_boolean_matrix, build_friction_feature_frame
from src.tradability_conditioned_research import build_candidate_signal_frame, load_research_bundle


ENTRY_ALPHA_DIR = data_path("features/entry_alpha")
ENTRY_ALPHA_CANDIDATE_PANEL_PATH = ENTRY_ALPHA_DIR / "candidate_panel_daily.parquet"
ENTRY_ALPHA_LABELS_CYCLE5_PATH = ENTRY_ALPHA_DIR / "entry_labels_cycle5.parquet"


@dataclass(frozen=True)
class EntryAlphaInputs:
    matrix: pd.DataFrame
    feature_frame: pd.DataFrame
    price_panel: pd.DataFrame
    benchmark_open: pd.Series
    market_inputs: object
    selector_name: str
    strategy_name: str
    signal_columns: tuple[str, ...]
    top_k: int
    rebalance_every: int
    activation_meta: pd.DataFrame
    activation_meta_source: str


def _selector_prefix(strategy_name: str) -> str:
    return "full" if str(strategy_name) == "full_library" else "s1"


def _selection_score_column(strategy_name: str) -> str:
    return f"score__{str(strategy_name)}"


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    frame.to_parquet(temp_path, index=False)
    temp_path.replace(path)


def load_entry_alpha_inputs(
    *,
    matrix_path: Path = RL_MATRIX_PATH,
    tradability_path: Path = TRADABILITY_PATH,
    stock_dir: Path = STOCK_DIR,
    benchmark_path: Path = BENCHMARK_PATH,
    activation_meta_path: Path = ACTIVATION_META_PATH,
    start_year: int = 2019,
    end_year: int = 2025,
    strategy_name: str = "full_library",
    round_trip_cost: float = 0.003,
    required_holding_age: int = 3,
    initial_notional_vnd: float = 100_000_000.0,
) -> EntryAlphaInputs:
    inputs = load_activation_experiment_inputs(
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        start_year=int(start_year),
        end_year=int(end_year),
    )
    selector = next(
        (item for item in inputs.selectors if str(item.strategy_name) == str(strategy_name)),
        None,
    )
    if selector is None:
        raise ValueError(f"Unsupported strategy_name {strategy_name!r} for entry alpha")

    feature_frame = build_friction_feature_frame(
        inputs.scored,
        inputs.price_panel,
        inputs.tradability,
    )
    matrix_extra = inputs.matrix.drop(columns=["actual"], errors="ignore")
    feature_frame = feature_frame.merge(
        matrix_extra,
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    try:
        research_bundle = load_research_bundle(
            matrix_path=matrix_path,
            tradability_path=tradability_path,
            stock_dir=stock_dir,
            benchmark_path=benchmark_path,
            start_year=int(start_year),
            end_year=int(end_year),
        )
        candidate_signal_frame = build_candidate_signal_frame(
            research_bundle,
            start_year=int(start_year),
            end_year=int(end_year),
        )
        extra_columns = [
            column
            for column in candidate_signal_frame.columns
            if column not in {"time", "ticker"} and column not in feature_frame.columns
        ]
        if extra_columns:
            feature_frame = feature_frame.merge(
                candidate_signal_frame[["time", "ticker"] + extra_columns],
                on=["time", "ticker"],
                how="left",
                validate="one_to_one",
            )
    except FileNotFoundError:
        pass

    activation_meta, meta_source = load_or_build_activation_meta(
        out_path=activation_meta_path,
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        start_year=2015,
        end_year=int(end_year),
        round_trip_cost=float(round_trip_cost),
        required_holding_age=int(required_holding_age),
        initial_notional_vnd=float(initial_notional_vnd),
    )
    activation_meta = activation_meta[
        (pd.to_datetime(activation_meta["time"]).dt.year >= int(start_year))
        & (pd.to_datetime(activation_meta["time"]).dt.year <= int(end_year))
    ].copy()
    prefix = _selector_prefix(strategy_name)
    rel2 = selector_recent_relative_ewm_from_prev(activation_meta, prefix=prefix, span=2)
    activation_meta["activation_rel2"] = pd.to_numeric(rel2, errors="coerce").to_numpy(dtype=float)
    activation_meta["activation_scale"] = (pd.to_numeric(activation_meta["activation_rel2"], errors="coerce") > 0.0).astype(float)
    activation_meta["activation_state"] = np.where(
        pd.to_numeric(activation_meta["activation_scale"], errors="coerce") > 0.0,
        "on",
        "off",
    )

    return EntryAlphaInputs(
        matrix=inputs.matrix.copy(),
        feature_frame=feature_frame,
        price_panel=inputs.price_panel.copy(),
        benchmark_open=load_benchmark_open(benchmark_path),
        market_inputs=inputs.market_inputs,
        selector_name=str(selector.name),
        strategy_name=str(selector.strategy_name),
        signal_columns=tuple(selector.signal_columns),
        top_k=int(selector.top_k),
        rebalance_every=int(selector.rebalance_every),
        activation_meta=activation_meta,
        activation_meta_source=str(meta_source),
    )


def _baseline_prev_close_hold_lookup(
    inputs: EntryAlphaInputs,
    *,
    top_k: int,
    rebalance_every: int,
    round_trip_cost: float,
    required_holding_age: int,
    initial_notional_vnd: float,
) -> dict[pd.Timestamp, set[str]]:
    fee_leg = float(round_trip_cost) / 2.0
    result = simulate_strategy(
        strategy_name=inputs.strategy_name,
        signal_columns=list(inputs.signal_columns),
        market_inputs=inputs.market_inputs,
        top_k=int(top_k),
        rebalance_every=int(rebalance_every),
        weighting="equal",
        initial_notional_vnd=float(initial_notional_vnd),
        max_adv_participation=0.0,
        required_holding_age=int(required_holding_age),
        buy_fee_rate=float(fee_leg),
        sell_fee_rate=float(fee_leg),
        capital_gains_tax_rate=0.0,
    )
    daily = result.daily.copy()
    daily["execution_date"] = pd.to_datetime(daily["execution_date"])
    lookup: dict[pd.Timestamp, set[str]] = {}
    for row in daily.itertuples(index=False):
        held = getattr(row, "held_tickers", []) or []
        lookup[pd.Timestamp(row.execution_date)] = {str(ticker) for ticker in held}
    return lookup


def build_entry_candidate_panel(
    inputs: EntryAlphaInputs,
    *,
    top_m_max: int = 20,
    top_k: int | None = None,
    rebalance_every: int | None = None,
    round_trip_cost: float = 0.003,
    required_holding_age: int = 3,
    initial_notional_vnd: float = 100_000_000.0,
    held_prev_close_lookup: Mapping[pd.Timestamp, set[str]] | None = None,
) -> pd.DataFrame:
    if int(top_m_max) <= 0:
        raise ValueError("top_m_max must be > 0")

    effective_top_k = int(inputs.top_k if top_k is None else top_k)
    effective_rebalance = int(inputs.rebalance_every if rebalance_every is None else rebalance_every)
    score_column = _selection_score_column(inputs.strategy_name)
    if score_column not in inputs.feature_frame.columns:
        raise ValueError(f"Missing selection score column {score_column!r}")

    work = inputs.feature_frame.copy()
    work["time"] = pd.to_datetime(work["time"])
    work["selection_score"] = pd.to_numeric(work[score_column], errors="coerce")
    work = work.sort_values(
        ["time", "selection_score", "ticker"],
        ascending=[True, False, True],
        ignore_index=True,
    )
    work["selection_rank"] = work.groupby("time", sort=False).cumcount() + 1
    work["candidate_pool_rank"] = work["selection_rank"].astype(int)
    work["selection_score_next_candidate"] = work.groupby("time", sort=False)["selection_score"].shift(-1)
    work["selection_score_gap_to_next_candidate"] = (
        pd.to_numeric(work["selection_score"], errors="coerce")
        - pd.to_numeric(work["selection_score_next_candidate"], errors="coerce")
    )
    work["selection_score_topk_cutoff"] = work.groupby("time", sort=False)["selection_score"].transform(
        lambda series: series.iloc[int(effective_top_k)] if len(series) > int(effective_top_k) else np.nan
    )
    work["selection_score_gap_to_top_k_cutoff"] = (
        pd.to_numeric(work["selection_score"], errors="coerce")
        - pd.to_numeric(work["selection_score_topk_cutoff"], errors="coerce")
    )
    panel = work.loc[work["selection_rank"] <= int(top_m_max)].copy()
    panel["candidate_pool_size"] = panel.groupby("time", sort=False)["ticker"].transform("size").astype(int)

    if held_prev_close_lookup is None:
        held_prev_close_lookup = _baseline_prev_close_hold_lookup(
            inputs,
            top_k=int(effective_top_k),
            rebalance_every=int(effective_rebalance),
            round_trip_cost=float(round_trip_cost),
            required_holding_age=int(required_holding_age),
            initial_notional_vnd=float(initial_notional_vnd),
        )
    panel["is_held_prev_close"] = [
        str(ticker) in held_prev_close_lookup.get(pd.Timestamp(time), set())
        for time, ticker in zip(panel["time"], panel["ticker"])
    ]
    panel = panel.merge(
        inputs.activation_meta,
        on="time",
        how="left",
        validate="many_to_one",
    )
    panel["selector_name"] = inputs.selector_name
    panel["strategy_name"] = inputs.strategy_name
    panel["top_k"] = int(effective_top_k)
    panel["rebalance_every"] = int(effective_rebalance)

    preferred = [
        "time",
        "ticker",
        "selector_name",
        "strategy_name",
        "selection_score",
        "selection_rank",
        "candidate_pool_rank",
        "candidate_pool_size",
        "selection_score_gap_to_next_candidate",
        "selection_score_gap_to_top_k_cutoff",
        "can_buy_next_open",
        "can_sell_next_open",
        "is_held_prev_close",
        "activation_state",
        "activation_scale",
        "activation_rel2",
        "top_k",
        "rebalance_every",
        "actual",
    ]
    ordered = preferred + [column for column in panel.columns if column not in preferred]
    return panel.loc[:, ordered].reset_index(drop=True)


def build_entry_labels(
    candidate_panel: pd.DataFrame,
    *,
    price_panel: pd.DataFrame,
    benchmark_open: pd.Series,
    horizon_signal_steps: int,
    signal_dates: Sequence[pd.Timestamp] | None = None,
    round_trip_cost: float = 0.003,
    label_edge_buffer: float = 0.0,
) -> pd.DataFrame:
    if int(horizon_signal_steps) <= 0:
        raise ValueError("horizon_signal_steps must be > 0")

    work = candidate_panel[["time", "ticker"]].copy()
    work["time"] = pd.to_datetime(work["time"])
    if signal_dates is None:
        unique_dates = pd.Index(sorted(pd.to_datetime(benchmark_open.index).drop_duplicates()))
    else:
        unique_dates = pd.Index(sorted(pd.to_datetime(pd.Index(signal_dates)).drop_duplicates()))
    if len(unique_dates) == 0:
        raise ValueError("signal_dates must contain at least one date")
    date_to_pos = {pd.Timestamp(value): idx for idx, value in enumerate(unique_dates)}
    signal_pos = work["time"].map(date_to_pos)
    if signal_pos.isna().any():
        missing = sorted({pd.Timestamp(value).strftime("%Y-%m-%d") for value in work.loc[signal_pos.isna(), "time"]})
        raise ValueError(
            "candidate_panel contains dates that are missing from the signal calendar: "
            + ", ".join(missing[:5])
            + (" ..." if len(missing) > 5 else "")
        )
    signal_pos = signal_pos.astype(int)
    entry_pos = signal_pos + 1
    exit_pos = signal_pos + int(horizon_signal_steps) + 1
    valid = exit_pos < len(unique_dates)

    work["entry_execution_date"] = pd.NaT
    work["cycle_exit_date"] = pd.NaT
    work.loc[valid, "entry_execution_date"] = unique_dates.take(entry_pos[valid].to_numpy(dtype=int))
    work.loc[valid, "cycle_exit_date"] = unique_dates.take(exit_pos[valid].to_numpy(dtype=int))

    price_lookup = price_panel[["time", "ticker", "open"]].copy()
    price_lookup["time"] = pd.to_datetime(price_lookup["time"])
    price_lookup["open"] = pd.to_numeric(price_lookup["open"], errors="coerce")

    work = work.reset_index(names="_row_id")
    entry_prices = (
        work[["_row_id", "ticker", "entry_execution_date"]]
        .rename(columns={"entry_execution_date": "time"})
        .merge(price_lookup.rename(columns={"open": "entry_open_t1"}), on=["time", "ticker"], how="left")
    )
    exit_prices = (
        work[["_row_id", "ticker", "cycle_exit_date"]]
        .rename(columns={"cycle_exit_date": "time"})
        .merge(price_lookup.rename(columns={"open": "cycle_exit_open"}), on=["time", "ticker"], how="left")
    )
    work = work.merge(entry_prices[["_row_id", "entry_open_t1"]], on="_row_id", how="left")
    work = work.merge(exit_prices[["_row_id", "cycle_exit_open"]], on="_row_id", how="left")

    benchmark_frame = benchmark_open.rename("benchmark_open").reset_index()
    benchmark_frame.columns = ["time", "benchmark_open"]
    benchmark_frame["time"] = pd.to_datetime(benchmark_frame["time"])

    work = work.merge(
        benchmark_frame.rename(
            columns={
                "time": "entry_execution_date",
                "benchmark_open": "benchmark_entry_open",
            }
        ),
        on="entry_execution_date",
        how="left",
    )
    work = work.merge(
        benchmark_frame.rename(
            columns={
                "time": "cycle_exit_date",
                "benchmark_open": "benchmark_exit_open",
            }
        ),
        on="cycle_exit_date",
        how="left",
    )

    entry_open = pd.to_numeric(work["entry_open_t1"], errors="coerce")
    exit_open = pd.to_numeric(work["cycle_exit_open"], errors="coerce")
    benchmark_entry = pd.to_numeric(work["benchmark_entry_open"], errors="coerce")
    benchmark_exit = pd.to_numeric(work["benchmark_exit_open"], errors="coerce")

    work["cycle_return_gross"] = exit_open / entry_open - 1.0
    work["cycle_return_net"] = work["cycle_return_gross"] - float(round_trip_cost)
    benchmark_return = benchmark_exit / benchmark_entry - 1.0
    work["cycle_relative_return_vs_vnindex"] = pd.to_numeric(work["cycle_return_net"], errors="coerce") - benchmark_return
    work["cycle_relative_return_vs_cash"] = pd.to_numeric(work["cycle_return_net"], errors="coerce")

    label = pd.Series(pd.array([pd.NA] * len(work), dtype="Int64"), index=work.index)
    valid_label = pd.to_numeric(work["cycle_return_net"], errors="coerce").notna()
    label.loc[valid_label] = (
        pd.to_numeric(work.loc[valid_label, "cycle_return_net"], errors="coerce") > float(label_edge_buffer)
    ).astype(int)
    work["buy_now_label"] = label
    work["label_edge_buffer"] = float(label_edge_buffer)

    preferred = [
        "time",
        "ticker",
        "entry_execution_date",
        "cycle_exit_date",
        "entry_open_t1",
        "cycle_exit_open",
        "cycle_return_gross",
        "cycle_return_net",
        "cycle_relative_return_vs_vnindex",
        "cycle_relative_return_vs_cash",
        "buy_now_label",
        "label_edge_buffer",
    ]
    ordered = preferred + [column for column in work.columns if column not in preferred and column != "_row_id"]
    return work.loc[:, ordered].reset_index(drop=True)


def build_entry_allowed_matrix(
    candidate_panel: pd.DataFrame,
    *,
    dates: Sequence[pd.Timestamp],
    tickers: Sequence[str],
    top_m: int,
    min_selection_score: float | None = None,
    min_score_gap: float | None = None,
    require_buyable: bool = True,
) -> np.ndarray:
    if int(top_m) <= 0:
        raise ValueError("top_m must be > 0")

    work = candidate_panel.copy()
    mask = pd.to_numeric(work["candidate_pool_rank"], errors="coerce") <= int(top_m)
    if min_selection_score is not None:
        mask &= pd.to_numeric(work["selection_score"], errors="coerce") >= float(min_selection_score)
    if min_score_gap is not None:
        mask &= pd.to_numeric(work["selection_score_gap_to_next_candidate"], errors="coerce") >= float(min_score_gap)
    if require_buyable and "can_buy_next_open" in work.columns:
        mask &= work["can_buy_next_open"].fillna(False).astype(bool)

    allowed = work.loc[mask, ["time", "ticker"]].copy()
    allowed["entry_allowed"] = True
    return build_boolean_matrix(
        allowed,
        value_column="entry_allowed",
        dates=list(pd.to_datetime(dates)),
        tickers=list(tickers),
        fill_value=False,
    )


def persist_entry_alpha_artifacts(
    candidate_panel: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    candidate_panel_path: Path = ENTRY_ALPHA_CANDIDATE_PANEL_PATH,
    labels_path: Path = ENTRY_ALPHA_LABELS_CYCLE5_PATH,
) -> None:
    _write_parquet_atomic(candidate_panel, candidate_panel_path)
    _write_parquet_atomic(labels, labels_path)
