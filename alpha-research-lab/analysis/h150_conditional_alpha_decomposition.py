"""
H150: Conditional alpha decomposition under liquidity-opening states.

Purpose:
- identify which existing signal components survive once the market is tradable
- measure whether the current library has a narrow subset that becomes materially stronger in liquidity-opening states
- decide whether the next branch should be a tradability-conditioned composite or a plain conclusion that the current library is not deployable enough

Usage:
    conda run -n stocks python analysis/h150_conditional_alpha_decomposition.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.deterministic_portfolio import RESERVED_COLUMNS, load_or_build_tradability_panel, load_price_panel
from src.portfolio_friction_features import build_friction_feature_frame
from src.run_summary import write_run_summary

RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


STATE_DEFS = [
    ("unrestricted", lambda frame: pd.Series(True, index=frame.index)),
    ("tv110", lambda frame: pd.to_numeric(frame["tv_to_adv20"], errors="coerce") >= 1.10),
    (
        "tv110_clv45",
        lambda frame: (pd.to_numeric(frame["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(frame["clv"], errors="coerce") >= 0.45),
    ),
    (
        "tv125_clv50",
        lambda frame: (pd.to_numeric(frame["tv_to_adv20"], errors="coerce") >= 1.25)
        & (pd.to_numeric(frame["clv"], errors="coerce") >= 0.50),
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-names-per-day", type=int, default=10)
    parser.add_argument("--signal", action="append", default=[])
    parser.add_argument("--top-signals", type=int, default=10)
    return parser.parse_args()


def _safe_spearman(signal: pd.Series, actual: pd.Series) -> float | None:
    pair = pd.concat([pd.to_numeric(signal, errors="coerce"), pd.to_numeric(actual, errors="coerce")], axis=1).dropna()
    if len(pair) < 2:
        return None
    if pair.iloc[:, 0].nunique(dropna=True) < 2 or pair.iloc[:, 1].nunique(dropna=True) < 2:
        return None
    corr = pair.iloc[:, 0].corr(pair.iloc[:, 1], method="spearman")
    if pd.isna(corr):
        return None
    return float(corr)


def _compute_daily_ic(frame: pd.DataFrame, *, signal_column: str, min_names_per_day: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for time, group in frame.groupby("time", sort=True):
        pair = group[[signal_column, "actual"]].copy()
        pair[signal_column] = pd.to_numeric(pair[signal_column], errors="coerce")
        pair["actual"] = pd.to_numeric(pair["actual"], errors="coerce")
        pair = pair.dropna()
        if len(pair) < int(min_names_per_day):
            continue
        ic = _safe_spearman(pair[signal_column], pair["actual"])
        if ic is None:
            continue
        rows.append(
            {
                "time": pd.Timestamp(time),
                "year": int(pd.Timestamp(time).year),
                "daily_ic": float(ic),
                "sample_size": int(len(pair)),
            }
        )
    return pd.DataFrame(rows)


def _summarize_state_signal(
    *,
    signal_column: str,
    state_name: str,
    state_frame: pd.DataFrame,
    min_names_per_day: int,
    total_rows: int,
    total_days: int,
) -> tuple[dict[str, object], pd.DataFrame]:
    daily = _compute_daily_ic(state_frame, signal_column=signal_column, min_names_per_day=min_names_per_day)
    per_year: list[dict[str, object]] = []
    if not daily.empty:
        for year, group in daily.groupby("year", sort=True):
            per_year.append(
                {
                    "year": int(year),
                    "avg_daily_ic": round(float(group["daily_ic"].mean()), 6),
                    "positive_days": int((group["daily_ic"] > 0.0).sum()),
                    "total_days": int(len(group)),
                    "avg_sample_size": round(float(group["sample_size"].mean()), 2),
                }
            )

    rows_in_state = int(len(state_frame))
    days_in_state = int(state_frame["time"].nunique()) if not state_frame.empty else 0
    summary = {
        "signal": signal_column,
        "state": state_name,
        "avg_daily_ic": round(float(daily["daily_ic"].mean()), 6) if not daily.empty else None,
        "positive_years": int(sum(1 for row in per_year if row["avg_daily_ic"] > 0.0)),
        "total_years": int(len(per_year)),
        "evaluated_days": int(len(daily)),
        "avg_sample_size": round(float(daily["sample_size"].mean()), 2) if not daily.empty else None,
        "state_row_coverage": round(rows_in_state / max(int(total_rows), 1), 6),
        "state_day_coverage": round(days_in_state / max(int(total_days), 1), 6),
        "rows_in_state": rows_in_state,
        "days_in_state": days_in_state,
        "per_year": per_year,
    }
    if not daily.empty:
        daily = daily.assign(signal=signal_column, state=state_name)
    return summary, daily


def _print_top(results: pd.DataFrame, *, title: str, top_n: int) -> None:
    top = results.head(top_n)
    print("\n" + "=" * 176)
    print(title)
    print("=" * 176)
    print(
        f"{'rank':<5} {'signal':<28} {'state':<12} {'avg_ic':>8} {'yrs+':>7} {'days':>8} {'avg_n':>8} {'row_cov':>9} {'day_cov':>9}"
    )
    print("-" * 176)
    for i, row in enumerate(top.itertuples(index=False), start=1):
        avg_ic = float('nan') if row.avg_daily_ic is None else row.avg_daily_ic
        avg_n = float('nan') if row.avg_sample_size is None else row.avg_sample_size
        print(
            f"{i:<5} {row.signal:<28} {row.state:<12} {avg_ic:>+7.4f} {row.positive_years:>3}/{row.total_years:<3} "
            f"{row.evaluated_days:>8} {avg_n:>8.2f} {row.state_row_coverage*100:>8.2f}% {row.state_day_coverage*100:>8.2f}%"
        )


def main() -> None:
    args = parse_args()
    matrix_path = Path(args.matrix)
    tradability_path = Path(args.tradability)
    stock_dir = Path(args.stock_dir)

    print(f"Loading signal matrix: {matrix_path}")
    matrix = pd.read_parquet(matrix_path)
    matrix["time"] = pd.to_datetime(matrix["time"])
    matrix = matrix[(matrix["time"].dt.year >= args.start_year) & (matrix["time"].dt.year <= args.end_year)].copy()
    if matrix.empty:
        raise ValueError(f"No matrix rows in year range {args.start_year}-{args.end_year}")

    requested_signals = [str(value).strip() for value in args.signal if str(value).strip()]
    available_signals = [column for column in matrix.columns if column not in RESERVED_COLUMNS]
    signal_columns = requested_signals or available_signals
    missing = sorted(set(signal_columns) - set(available_signals))
    if missing:
        raise ValueError(f"Unknown signal columns: {missing}; available={available_signals}")

    print("Loading prices and tradability features...")
    price_panel = load_price_panel(matrix["ticker"].unique().tolist(), stock_dir)
    if price_panel.empty:
        raise ValueError(f"No price rows found under {stock_dir}")
    tradability, tradability_source = load_or_build_tradability_panel(price_panel, tradability_path)

    feature_frame = build_friction_feature_frame(matrix[["time", "ticker", "actual"]].copy(), price_panel, tradability)
    merged = matrix.merge(
        feature_frame[["time", "ticker", "tv_to_adv20", "clv", "can_buy_next_open"]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    total_rows = int(len(merged))
    total_days = int(merged["time"].nunique())
    summary_rows: list[dict[str, object]] = []
    daily_parts: list[pd.DataFrame] = []
    for state_name, state_fn in STATE_DEFS:
        mask = state_fn(merged).fillna(False).astype(bool)
        state_frame = merged.loc[mask].copy()
        for signal_column in signal_columns:
            summary_row, daily = _summarize_state_signal(
                signal_column=signal_column,
                state_name=state_name,
                state_frame=state_frame[["time", signal_column, "actual"]].copy(),
                min_names_per_day=int(args.min_names_per_day),
                total_rows=total_rows,
                total_days=total_days,
            )
            summary_rows.append(summary_row)
            if not daily.empty:
                daily_parts.append(daily)

    results = pd.DataFrame(summary_rows)
    results = results.sort_values(
        by=["avg_daily_ic", "positive_years", "state_row_coverage", "signal", "state"],
        ascending=[False, False, False, True, True],
        ignore_index=True,
    )
    daily_ic = pd.concat(daily_parts, ignore_index=True) if daily_parts else pd.DataFrame()

    unrestricted = results.loc[results["state"] == "unrestricted", ["signal", "avg_daily_ic"]].rename(
        columns={"avg_daily_ic": "avg_daily_ic_unrestricted"}
    )
    uplift = results.merge(unrestricted, on="signal", how="left")
    uplift["ic_uplift_vs_unrestricted"] = pd.to_numeric(uplift["avg_daily_ic"], errors="coerce") - pd.to_numeric(
        uplift["avg_daily_ic_unrestricted"], errors="coerce"
    )
    uplift = uplift.sort_values(
        by=["ic_uplift_vs_unrestricted", "avg_daily_ic", "signal", "state"],
        ascending=[False, False, True, True],
        ignore_index=True,
    )

    best_unrestricted = results.loc[results["state"] == "unrestricted"].head(1)
    best_liquidity_opening = results.loc[results["state"] != "unrestricted"].head(1)

    _print_top(results, title="H150: CONDITIONAL ALPHA DECOMPOSITION", top_n=int(args.top_signals))
    _print_top(
        uplift.loc[uplift["state"] != "unrestricted"],
        title="H150: STRONGEST CONDITIONAL IC UPLIFTS VS UNRESTRICTED",
        top_n=int(args.top_signals),
    )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h150_conditional_alpha_decomposition_results.parquet"
    uplift_path = OUT_DIR / f"{ts}_h150_conditional_alpha_decomposition_uplift.parquet"
    daily_path = OUT_DIR / f"{ts}_h150_conditional_alpha_decomposition_daily_ic.parquet"
    results.to_parquet(results_path, index=False)
    uplift.to_parquet(uplift_path, index=False)
    daily_ic.to_parquet(daily_path, index=False)

    summary = {
        "year_range": [int(args.start_year), int(args.end_year)],
        "signal_count": int(len(signal_columns)),
        "state_count": int(len(STATE_DEFS)),
        "min_names_per_day": int(args.min_names_per_day),
        "best_unrestricted": json.loads(best_unrestricted.to_json(orient="records"))[0] if not best_unrestricted.empty else {},
        "best_liquidity_opening": json.loads(best_liquidity_opening.to_json(orient="records"))[0] if not best_liquidity_opening.empty else {},
        "strongest_uplift": json.loads(
            uplift.loc[uplift["state"] != "unrestricted"].head(1).to_json(orient="records")
        )[0]
        if not uplift.loc[uplift["state"] != "unrestricted"].empty
        else {},
        "top_unrestricted": json.loads(
            results.loc[results["state"] == "unrestricted"].head(int(args.top_signals)).to_json(orient="records")
        ),
        "top_liquidity_opening": json.loads(
            results.loc[results["state"] != "unrestricted"].head(int(args.top_signals)).to_json(orient="records")
        ),
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_conditional_alpha_decomposition",
        name="h150_conditional_alpha_decomposition",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "uplift": str(uplift_path),
            "daily_ic": str(daily_path),
        },
        metadata={
            "matrix": str(matrix_path),
            "tradability": str(tradability_path),
            "stock_dir": str(stock_dir),
            "tradability_source": tradability_source,
        },
    )
    print(f"\nSaved H150 summary to {summary_path}")


if __name__ == "__main__":
    main()
