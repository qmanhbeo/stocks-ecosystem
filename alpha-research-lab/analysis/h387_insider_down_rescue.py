from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.repo_paths import artifact_path, data_path  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close, to_long  # noqa: E402


BRANCH_NAME = "h387_insider_down_rescue"
MODE = "research_branch_insider_down_rescue"
OUT_DIR = artifact_path("insider_down")

S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")

HIGH_FLOW_THRESHOLD = 0.80
VISIBLE_DOWN_THRESHOLD = 0.0
DEEP_DOWN_3D_THRESHOLD = -0.02
MIN_YEAR_ROWS = 20
MIN_TRAIN_YEARS = 2
MIN_PASS_LIFT_5D = 0.002


@dataclass(frozen=True)
class StateSpec:
    name: str
    label: str
    family: str


STATE_SPECS = [
    StateSpec("all_rows", "All ticker-day rows", "all"),
    StateSpec("insider_buy", "Positive C5 insider rows", "insider"),
    StateSpec("insider_high_c16", "Positive insider rows with high C16", "insider_c16"),
    StateSpec("stock_down", "Rows after 1d and 3d stock weakness", "down"),
    StateSpec("stock_down_high_c16", "Stock-down rows with high C16", "down_c16"),
    StateSpec("stock_down_no_insider", "Stock-down rows without positive insider", "down"),
    StateSpec("insider_down", "Positive insider rows after stock weakness", "insider_down"),
    StateSpec(
        "insider_down_high_c16",
        "Positive insider rows after stock weakness with high C16",
        "insider_down_c16",
    ),
    StateSpec(
        "insider_deep_down_high_c16",
        "Positive insider rows after at least 2 percent 3d weakness with high C16",
        "insider_down_c16",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H387: insider-down rescue audit. Tests whether positive insider "
            "conviction after visible stock weakness and high C16 support has "
            "delayed payoff beyond ordinary insider-buy and down-C16 controls."
        )
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_PATH))
    parser.add_argument("--c16-path", type=str, default=str(C16_PATH))
    parser.add_argument("--matrix-path", type=str, default=str(MATRIX_PATH))
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-train-years", type=int, default=MIN_TRAIN_YEARS)
    parser.add_argument("--min-year-rows", type=int, default=MIN_YEAR_ROWS)
    parser.add_argument("--min-pass-lift-5d", type=float, default=MIN_PASS_LIFT_5D)
    return parser.parse_args()


def _safe_numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _load_future_and_trailing_returns(start_year: int, end_year: int) -> pd.DataFrame:
    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    vni_close = load_vni_close().sort_index().reindex(close.index)
    parts: list[pd.DataFrame] = []
    for periods, column in [(1, "future_rel_return_1d"), (5, "future_rel_return_5d")]:
        stock_future = close.shift(-periods).div(close).sub(1.0)
        vni_future = vni_close.shift(-periods).div(vni_close).sub(1.0).reindex(stock_future.index)
        rel = stock_future.sub(vni_future, axis=0)
        part = to_long(rel, column)
        parts.append(part)
    trailing_1d = close.div(close.shift(1)).sub(1.0)
    trailing_3d = close.div(close.shift(3)).sub(1.0)
    drawdown_3d = close.div(close.rolling(3, min_periods=2).max()).sub(1.0)
    parts.append(to_long(trailing_1d, "stock_return_1d"))
    parts.append(to_long(trailing_3d, "stock_return_3d"))
    parts.append(to_long(drawdown_3d, "stock_drawdown_from_3d_high"))

    out = parts[0]
    for part in parts[1:]:
        out = out.merge(part, on=["time", "ticker"], how="inner", validate="one_to_one")
    out["time"] = pd.to_datetime(out["time"], errors="coerce").dt.normalize()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out = out.loc[out["time"].dt.year.between(int(start_year), int(end_year))].copy()
    return out.dropna(
        subset=[
            "time",
            "ticker",
            "future_rel_return_1d",
            "future_rel_return_5d",
            "stock_return_1d",
            "stock_return_3d",
            "stock_drawdown_from_3d_high",
        ]
    )


def _load_panel(args: argparse.Namespace) -> pd.DataFrame:
    if int(args.end_year) >= 2026:
        raise ValueError("H387 must not train or test on 2026+; set --end-year <= 2025")

    s1 = pd.read_parquet(args.s1_path, columns=["time", "ticker", "actual", "xs_proba"]).copy()
    s1["time"] = pd.to_datetime(s1["time"], errors="coerce").dt.normalize()
    s1["ticker"] = s1["ticker"].astype(str).str.upper()
    s1 = s1.loc[s1["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()

    c16 = pd.read_parquet(
        args.c16_path,
        columns=["time", "ticker", "order_volume_ratio_rank", "order_pressure_available"],
    ).copy()
    c16["time"] = pd.to_datetime(c16["time"], errors="coerce").dt.normalize()
    c16["ticker"] = c16["ticker"].astype(str).str.upper()

    matrix = pd.read_parquet(
        args.matrix_path,
        columns=["time", "ticker", "c5_ins_relative_size_5d", "c5_signal_present"],
    ).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    matrix["c5_ins_relative_size_5d"] = _safe_numeric(matrix, "c5_ins_relative_size_5d")
    matrix["c5_signal_present"] = _safe_numeric(matrix, "c5_signal_present")

    returns = _load_future_and_trailing_returns(int(args.start_year), int(args.end_year))

    panel = s1.merge(c16, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(matrix, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(returns, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.loc[panel["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()
    panel["year"] = panel["time"].dt.year.astype(int)

    panel["order_volume_ratio_rank"] = _safe_numeric(panel, "order_volume_ratio_rank", np.nan)
    panel["order_pressure_available"] = panel["order_pressure_available"].astype("boolean").fillna(False).astype(bool)
    panel["c5_ins_relative_size_5d"] = _safe_numeric(panel, "c5_ins_relative_size_5d")
    panel["c5_signal_present"] = _safe_numeric(panel, "c5_signal_present")
    panel["actual"] = _safe_numeric(panel, "actual", np.nan)
    panel["xs_proba"] = _safe_numeric(panel, "xs_proba", np.nan)

    panel["insider_buy"] = (
        (panel["c5_signal_present"] > 0.0)
        & (panel["c5_ins_relative_size_5d"] > 0.0)
    )
    panel["high_c16"] = (
        panel["order_pressure_available"]
        & (panel["order_volume_ratio_rank"] >= HIGH_FLOW_THRESHOLD)
    )
    panel["stock_down"] = (
        (panel["stock_return_1d"] < VISIBLE_DOWN_THRESHOLD)
        & (panel["stock_return_3d"] < VISIBLE_DOWN_THRESHOLD)
    )
    panel["stock_deep_down"] = panel["stock_return_3d"] <= DEEP_DOWN_3D_THRESHOLD
    return panel.dropna(
        subset=[
            "order_volume_ratio_rank",
            "c5_ins_relative_size_5d",
            "actual",
            "xs_proba",
            "future_rel_return_1d",
            "future_rel_return_5d",
            "stock_return_1d",
            "stock_return_3d",
            "stock_drawdown_from_3d_high",
        ]
    )


def _state_mask(panel: pd.DataFrame, state: str) -> pd.Series:
    insider = panel["insider_buy"].fillna(False).astype(bool)
    high_c16 = panel["high_c16"].fillna(False).astype(bool)
    down = panel["stock_down"].fillna(False).astype(bool)
    deep = panel["stock_deep_down"].fillna(False).astype(bool)
    masks = {
        "all_rows": pd.Series(True, index=panel.index),
        "insider_buy": insider,
        "insider_high_c16": insider & high_c16,
        "stock_down": down,
        "stock_down_high_c16": down & high_c16,
        "stock_down_no_insider": down & ~insider,
        "insider_down": insider & down,
        "insider_down_high_c16": insider & down & high_c16,
        "insider_deep_down_high_c16": insider & deep & high_c16,
    }
    if state not in masks:
        raise ValueError(f"Unknown state {state!r}")
    return masks[state]


def _safe_ic(frame: pd.DataFrame, score_col: str, target_col: str, min_rows: int) -> dict[str, object]:
    clean = frame[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < int(min_rows) or clean[score_col].nunique() < 3 or clean[target_col].nunique() < 3:
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    rho, p_value = spearmanr(clean[score_col], clean[target_col])
    rho_value = float(np.asarray(rho).flat[0])
    if not np.isfinite(rho_value):
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    return {"rows": int(len(clean)), "ic": rho_value, "p_value": float(np.asarray(p_value).flat[0])}


def _metric_record(frame: pd.DataFrame, *, min_rows: int) -> dict[str, object]:
    c16_5d = _safe_ic(frame, "order_volume_ratio_rank", "future_rel_return_5d", int(min_rows))
    c5_5d = _safe_ic(frame, "c5_ins_relative_size_5d", "future_rel_return_5d", int(min_rows))
    return {
        "rows": int(len(frame)),
        "mean_rel_1d": float(frame["future_rel_return_1d"].mean()) if not frame.empty else None,
        "mean_rel_5d": float(frame["future_rel_return_5d"].mean()) if not frame.empty else None,
        "median_rel_5d": float(frame["future_rel_return_5d"].median()) if not frame.empty else None,
        "mean_stock_return_1d": float(frame["stock_return_1d"].mean()) if not frame.empty else None,
        "mean_stock_return_3d": float(frame["stock_return_3d"].mean()) if not frame.empty else None,
        "mean_c16_rank": float(frame["order_volume_ratio_rank"].mean()) if not frame.empty else None,
        "mean_c5": float(frame["c5_ins_relative_size_5d"].mean()) if not frame.empty else None,
        "c16_ic_5d": c16_5d["ic"],
        "c16_ic_5d_p_value": c16_5d["p_value"],
        "c5_ic_5d": c5_5d["ic"],
        "c5_ic_5d_p_value": c5_5d["p_value"],
    }


def _fold_rows(panel: pd.DataFrame, *, min_train_years: int, min_year_rows: int) -> pd.DataFrame:
    years = sorted(int(year) for year in panel["year"].unique())
    rows: list[dict[str, object]] = []
    for test_year in years:
        train_years = [year for year in years if year < int(test_year)]
        if len(train_years) < int(min_train_years):
            continue
        train = panel.loc[panel["year"].isin(train_years)].copy()
        test = panel.loc[panel["year"] == int(test_year)].copy()
        for spec in STATE_SPECS:
            train_state = train.loc[_state_mask(train, spec.name)].copy()
            test_state = test.loc[_state_mask(test, spec.name)].copy()
            train_metrics = _metric_record(train_state, min_rows=int(min_year_rows))
            test_metrics = _metric_record(test_state, min_rows=int(min_year_rows))
            rows.append(
                {
                    "test_year": int(test_year),
                    "train_start_year": int(min(train_years)),
                    "train_end_year": int(max(train_years)),
                    "state": spec.name,
                    "label": spec.label,
                    "family": spec.family,
                    **{f"train_{key}": value for key, value in train_metrics.items()},
                    **{f"test_{key}": value for key, value in test_metrics.items()},
                }
            )
    return pd.DataFrame(rows)


def _summarize_states(folds: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spec in STATE_SPECS:
        state_rows = folds.loc[folds["state"] == spec.name].copy()
        valid = state_rows.loc[state_rows["test_rows"] >= MIN_YEAR_ROWS].copy()
        if valid.empty:
            rows.append(
                {
                    "state": spec.name,
                    "label": spec.label,
                    "family": spec.family,
                    "wf_years": 0,
                    "mean_rows": 0.0,
                    "mean_rel_1d": None,
                    "mean_rel_5d": None,
                    "median_rel_5d": None,
                    "mean_stock_return_3d": None,
                    "mean_c16_rank": None,
                    "mean_c5": None,
                    "mean_c16_ic_5d": None,
                    "mean_c5_ic_5d": None,
                    "confirmation_2025_rel_5d": None,
                }
            )
            continue
        conf = valid.loc[valid["test_year"] == 2025]
        rows.append(
            {
                "state": spec.name,
                "label": spec.label,
                "family": spec.family,
                "wf_years": int(len(valid)),
                "mean_rows": float(valid["test_rows"].mean()),
                "mean_rel_1d": float(valid["test_mean_rel_1d"].mean()),
                "mean_rel_5d": float(valid["test_mean_rel_5d"].mean()),
                "median_rel_5d": float(valid["test_median_rel_5d"].mean()),
                "mean_stock_return_3d": float(valid["test_mean_stock_return_3d"].mean()),
                "mean_c16_rank": float(valid["test_mean_c16_rank"].mean()),
                "mean_c5": float(valid["test_mean_c5"].mean()),
                "mean_c16_ic_5d": (
                    float(valid["test_c16_ic_5d"].dropna().mean())
                    if valid["test_c16_ic_5d"].notna().any()
                    else None
                ),
                "mean_c5_ic_5d": (
                    float(valid["test_c5_ic_5d"].dropna().mean())
                    if valid["test_c5_ic_5d"].notna().any()
                    else None
                ),
                "confirmation_2025_rel_5d": (
                    float(conf.iloc[0]["test_mean_rel_5d"]) if not conf.empty else None
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        by=["mean_rel_5d", "mean_rows"],
        ascending=[False, False],
        ignore_index=True,
    )


def _state_record(summary: pd.DataFrame, state: str) -> dict[str, object]:
    row = summary.loc[summary["state"] == state]
    return row.iloc[0].to_dict() if not row.empty else {}


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _lift_stats(folds: pd.DataFrame, state: str, control: str) -> dict[str, object]:
    left = folds.loc[folds["state"] == state, ["test_year", "test_mean_rel_1d", "test_mean_rel_5d", "test_rows"]]
    right = folds.loc[folds["state"] == control, ["test_year", "test_mean_rel_1d", "test_mean_rel_5d", "test_rows"]]
    merged = left.merge(right, on="test_year", how="inner", suffixes=("_state", "_control"))
    merged = merged.loc[
        (merged["test_rows_state"] >= MIN_YEAR_ROWS)
        & (merged["test_rows_control"] >= MIN_YEAR_ROWS)
    ].copy()
    if merged.empty:
        return {
            "state": state,
            "control": control,
            "years": 0,
            "mean_lift_1d": None,
            "mean_lift_5d": None,
            "pos_lift_5d_years": 0,
            "pct_pos_lift_5d_years": None,
            "confirmation_2025_lift_5d": None,
        }
    merged["lift_1d"] = merged["test_mean_rel_1d_state"] - merged["test_mean_rel_1d_control"]
    merged["lift_5d"] = merged["test_mean_rel_5d_state"] - merged["test_mean_rel_5d_control"]
    conf = merged.loc[merged["test_year"] == 2025]
    return {
        "state": state,
        "control": control,
        "years": int(len(merged)),
        "mean_lift_1d": float(merged["lift_1d"].mean()),
        "mean_lift_5d": float(merged["lift_5d"].mean()),
        "pos_lift_5d_years": int((merged["lift_5d"] > 0.0).sum()),
        "pct_pos_lift_5d_years": float((merged["lift_5d"] > 0.0).mean()),
        "confirmation_2025_lift_5d": float(conf.iloc[0]["lift_5d"]) if not conf.empty else None,
    }


def _passes_controls(
    folds: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    state: str,
    controls: list[str],
    min_lift_5d: float,
) -> tuple[bool, dict[str, dict[str, object]]]:
    state_row = _state_record(summary, state)
    if (
        (_safe_float(state_row.get("mean_rows")) or 0.0) < MIN_YEAR_ROWS
        or (_safe_float(state_row.get("mean_rel_5d")) or 0.0) <= 0.0
    ):
        return False, {control: _lift_stats(folds, state, control) for control in controls}
    stats = {control: _lift_stats(folds, state, control) for control in controls}
    required_years = 0
    for control_stats in stats.values():
        years = int(control_stats.get("years") or 0)
        required_years = max(required_years, max(3, int(np.ceil(0.60 * years)))) if years else required_years
        if years == 0:
            return False, stats
        if (_safe_float(control_stats.get("mean_lift_5d")) or 0.0) <= float(min_lift_5d):
            return False, stats
        if int(control_stats.get("pos_lift_5d_years") or 0) < max(3, int(np.ceil(0.60 * years))):
            return False, stats
        conf = _safe_float(control_stats.get("confirmation_2025_lift_5d"))
        if conf is not None and conf <= 0.0:
            return False, stats
    return True, stats


def _verdict(folds: pd.DataFrame, summary: pd.DataFrame, min_lift_5d: float) -> tuple[str, str, str, list[str], dict[str, object]]:
    primary_pass, primary_stats = _passes_controls(
        folds,
        summary,
        state="insider_down_high_c16",
        controls=["insider_buy", "insider_high_c16", "stock_down_high_c16"],
        min_lift_5d=float(min_lift_5d),
    )
    secondary_pass, secondary_stats = _passes_controls(
        folds,
        summary,
        state="insider_down",
        controls=["insider_buy", "stock_down"],
        min_lift_5d=float(min_lift_5d),
    )
    deep_pass, deep_stats = _passes_controls(
        folds,
        summary,
        state="insider_deep_down_high_c16",
        controls=["insider_buy", "insider_high_c16", "stock_down_high_c16"],
        min_lift_5d=float(min_lift_5d),
    )

    diagnostics = {
        "insider_down_high_c16": primary_stats,
        "insider_down": secondary_stats,
        "insider_deep_down_high_c16": deep_stats,
    }
    pass_states: list[str] = []
    if primary_pass:
        pass_states.append("insider_down_high_c16")
    if deep_pass:
        pass_states.append("insider_deep_down_high_c16")
    if pass_states:
        return (
            "PASSED",
            "offline_evidence",
            "A fixed insider-down C16 support state beat insider and down-control payoffs.",
            pass_states,
            diagnostics,
        )
    if secondary_pass:
        return (
            "MIXED",
            "park_or_narrow",
            "Insider after stock weakness beat broad controls, but high-C16 primary support did not clear.",
            ["insider_down"],
            diagnostics,
        )
    return (
        "FAILED",
        "branch_kill_or_reframe",
        "No insider-down rescue state beat insider and down-control payoffs cleanly.",
        [],
        diagnostics,
    )


def main() -> None:
    args = parse_args()
    panel = _load_panel(args)
    if panel.empty:
        raise ValueError("No rows after building H387 panel")
    folds = _fold_rows(
        panel,
        min_train_years=int(args.min_train_years),
        min_year_rows=int(args.min_year_rows),
    )
    if folds.empty:
        raise ValueError("No walk-forward folds produced")
    state_summary = _summarize_states(folds)
    verdict, durable_status, branch_decision, pass_states, lift_diagnostics = _verdict(
        folds,
        state_summary,
        float(args.min_pass_lift_5d),
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    folds_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_folds.parquet"
    states_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_states.parquet"
    folds.to_parquet(folds_path, index=False)
    state_summary.to_parquet(states_path, index=False)

    key_states = {
        state: _state_record(state_summary, state)
        for state in [
            "insider_buy",
            "insider_high_c16",
            "stock_down",
            "stock_down_high_c16",
            "insider_down",
            "insider_down_high_c16",
            "insider_deep_down_high_c16",
        ]
    }
    summary = {
        "branch": "insider_down_rescue",
        "experiment_id": "H387",
        "verdict": verdict,
        "durable_status": durable_status,
        "branch_decision": branch_decision,
        "pass_states": pass_states,
        "protocol": {
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "test_years": sorted(int(year) for year in folds["test_year"].unique()),
            "high_c16_threshold": HIGH_FLOW_THRESHOLD,
            "visible_down_definition": "stock_return_1d < 0 and stock_return_3d < 0",
            "deep_down_3d_threshold": DEEP_DOWN_3D_THRESHOLD,
            "primary_target": "future_rel_return_5d",
        },
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "insider_buy_share": float(panel["insider_buy"].mean()),
        "stock_down_share": float(panel["stock_down"].mean()),
        "high_c16_share": float(panel["high_c16"].mean()),
        "key_states": key_states,
        "lift_diagnostics": lift_diagnostics,
        "pass_rule": (
            "PASS if insider_down_high_c16 or insider_deep_down_high_c16 has "
            "positive mean 5d payoff and beats insider_buy, insider_high_c16, "
            "and stock_down_high_c16 by more than min_pass_lift_5d on average, "
            "with at least 60% positive 5d-lift years and positive 2025 lifts. "
            "MIXED if insider_down clears insider_buy and stock_down controls "
            "but the high-C16 primary state does not. Otherwise FAILED."
        ),
    }
    summary_path = write_run_summary(
        ts=ts,
        mode=MODE,
        name=BRANCH_NAME,
        summary=summary,
        artifacts={
            "folds": folds_path,
            "states": states_path,
            "s1": Path(args.s1_path),
            "c16": Path(args.c16_path),
            "matrix": Path(args.matrix_path),
        },
        metadata={
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "min_pass_lift_5d": float(args.min_pass_lift_5d),
        },
    )

    print("H387 insider-down rescue")
    print(f"saved_summary={summary_path}")
    print(f"folds={folds_path}")
    print(f"states={states_path}")
    print(f"verdict={verdict} | pass_states={pass_states}")
    print(
        state_summary[
            [
                "state",
                "family",
                "wf_years",
                "mean_rows",
                "mean_rel_1d",
                "mean_rel_5d",
                "mean_stock_return_3d",
                "mean_c16_rank",
                "mean_c16_ic_5d",
                "mean_c5_ic_5d",
                "confirmation_2025_rel_5d",
            ]
        ].to_string(index=False)
    )
    for state, controls in lift_diagnostics.items():
        print(f"\n{state} lift diagnostics")
        for control, stats in controls.items():
            print(f"  vs {control}: {stats}")


if __name__ == "__main__":
    main()
