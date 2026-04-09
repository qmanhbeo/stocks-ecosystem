"""
H327: CafeF historical foreign-flow source audit and first predictive screen.

Question:
    Now that CafeF GDKhoiNgoai has been backfilled, is the source broad enough
    to support honest research, and do simple lagged foreign-flow features have
    standalone predictive content versus the existing S1 target?

Design:
    - audit CafeF foreign-flow rows against the local stock trading calendar
    - quantify missingness, duplicate keys, net-field consistency, and coverage
    - build a small set of cross-sectional ranked raw and lagged flow features
    - evaluate only 2015-2025 for predictive content; 2026 is source-only / monitor

This is not a live-system change and does not publish an RL feature.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.repo_paths import data_path  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_s1_frame, spearman_stat  # noqa: E402


FLOW_PATH = data_path("foreign_flow/cafef/foreign_flow_daily.parquet")
STOCK_DIR = data_path("stock")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"
EXCLUDE = {"VNINDEX", "VN30"}
DEV_START = "2015-01-01"
DEV_END = "2022-12-31"
VALIDATION_START = "2023-01-01"
VALIDATION_END = "2024-12-31"
CONFIRMATION_START = "2025-01-01"
CONFIRMATION_END = "2025-12-31"
PREDICTIVE_START = "2015-01-01"
PREDICTIVE_END = "2025-12-31"
MIN_DAILY_OBS = 30
MIN_YEARLY_OBS = 500
PASS_IC = 0.01
VALIDATION_MIN_ABS_IC = 0.005
PASS_PCT_YEARS = 0.60
PASS_CORR = 0.30
SOURCE_MIN_ROW_COVERAGE = 0.75
SOURCE_MIN_TICKERS_WITH_DATA = 350
SOURCE_MIN_TICKERS_COVERAGE_60 = 300


NUMERIC_FLOW_COLUMNS = [
    "foreign_buy_volume",
    "foreign_sell_volume",
    "foreign_net_volume",
    "foreign_buy_value",
    "foreign_sell_value",
    "foreign_net_value",
    "foreign_room_remaining",
    "foreign_ownership_pct",
]

FEATURE_COLS = [
    "xs_ff_net_vol_share_1d_rank",
    "xs_ff_net_vol_share_1d_lag1_rank",
    "xs_ff_net_vol_share_5d_rank",
    "xs_ff_net_vol_share_5d_lag1_rank",
    "xs_ff_net_value_1d_rank",
    "xs_ff_net_value_5d_rank",
    "xs_ff_buy_share_5d_rank",
    "xs_ff_sell_share_5d_rank",
    "xs_ff_ownership_pct_rank",
    "xs_ff_room_scarcity_rank",
]


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is pd.NaT:
        return None
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        try:
            return str(path.relative_to(ROOT.parent))
        except ValueError:
            return str(path)


def load_flow() -> pd.DataFrame:
    if not FLOW_PATH.exists():
        raise FileNotFoundError(f"Missing CafeF foreign-flow panel: {FLOW_PATH}")
    flow = pd.read_parquet(FLOW_PATH)
    flow["time"] = pd.to_datetime(flow["date"], errors="coerce")
    flow["ticker"] = flow["ticker"].astype(str).str.upper()
    for column in NUMERIC_FLOW_COLUMNS:
        if column in flow.columns:
            flow[column] = pd.to_numeric(flow[column], errors="coerce")
        else:
            flow[column] = np.nan
    flow = flow.dropna(subset=["time", "ticker"]).sort_values(["ticker", "time"]).reset_index(drop=True)
    return flow


def load_stock_panel() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = path.stem.replace("gia_lich_su_", "").replace("_1D", "").upper()
        if not ticker or ticker in EXCLUDE:
            continue
        try:
            frame = pd.read_parquet(path, columns=["time", "close", "volume"])
        except Exception:
            continue
        if frame.empty:
            continue
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
        frame["ticker"] = ticker
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
        frames.append(frame[["time", "ticker", "close", "volume"]].dropna(subset=["time", "ticker"]))
    if not frames:
        raise RuntimeError("No stock daily frames loaded")
    return pd.concat(frames, ignore_index=True).sort_values(["ticker", "time"]).reset_index(drop=True)


def audit_source(flow: pd.DataFrame, stock: pd.DataFrame) -> tuple[dict[str, object], pd.DataFrame]:
    start = pd.Timestamp(PREDICTIVE_START)
    end = pd.Timestamp(PREDICTIVE_END)
    flow_eval = flow.loc[flow["time"].between(start, end)].copy()
    stock_eval = stock.loc[stock["time"].between(start, end)].copy()

    stock_keys = stock_eval[["time", "ticker"]].drop_duplicates()
    flow_keys = flow_eval[["time", "ticker"]].drop_duplicates()
    stock_join = stock_keys.merge(flow_keys.assign(has_flow=True), on=["time", "ticker"], how="left")
    stock_join["has_flow"] = stock_join["has_flow"].fillna(False)

    coverage_by_ticker = (
        stock_join.groupby("ticker", as_index=False)
        .agg(stock_days=("time", "size"), flow_days=("has_flow", "sum"))
        .assign(coverage_ratio=lambda df: df["flow_days"] / df["stock_days"].replace(0, np.nan))
        .sort_values(["coverage_ratio", "stock_days", "ticker"], ascending=[True, False, True])
        .reset_index(drop=True)
    )

    flow_unmatched = flow_keys.merge(stock_keys.assign(has_stock=True), on=["time", "ticker"], how="left")
    unmatched_flow_rows = int(flow_unmatched["has_stock"].isna().sum())

    dup_count = int(flow.duplicated(["time", "ticker"]).sum())
    net_vol_mismatch = int(
        (
            (flow["foreign_buy_volume"] - flow["foreign_sell_volume"] - flow["foreign_net_volume"])
            .abs()
            .fillna(0)
            > 1e-6
        ).sum()
    )
    net_value_mismatch = int(
        (
            (flow["foreign_buy_value"] - flow["foreign_sell_value"] - flow["foreign_net_value"])
            .abs()
            .fillna(0)
            > 1e-3
        ).sum()
    )
    null_ratios = {
        column: float(flow_eval[column].isna().mean())
        for column in NUMERIC_FLOW_COLUMNS
        if column in flow_eval.columns
    }

    summary = {
        "flow_path": _relative(FLOW_PATH),
        "flow_rows_total": int(len(flow)),
        "flow_tickers_total": int(flow["ticker"].nunique()),
        "flow_date_min": _json_safe(flow["time"].min()),
        "flow_date_max": _json_safe(flow["time"].max()),
        "eval_window": f"{PREDICTIVE_START}..{PREDICTIVE_END}",
        "stock_rows_eval": int(len(stock_keys)),
        "flow_rows_eval": int(len(flow_keys)),
        "matched_stock_rows_eval": int(stock_join["has_flow"].sum()),
        "row_coverage_eval": float(stock_join["has_flow"].mean()),
        "tickers_with_any_flow_eval": int((coverage_by_ticker["flow_days"] > 0).sum()),
        "tickers_with_coverage_ge_60pct": int((coverage_by_ticker["coverage_ratio"] >= 0.60).sum()),
        "tickers_with_coverage_ge_90pct": int((coverage_by_ticker["coverage_ratio"] >= 0.90).sum()),
        "ticker_coverage_median": float(coverage_by_ticker["coverage_ratio"].median()),
        "ticker_coverage_p10": float(coverage_by_ticker["coverage_ratio"].quantile(0.10)),
        "ticker_coverage_p01": float(coverage_by_ticker["coverage_ratio"].quantile(0.01)),
        "worst_coverage_tickers": _json_safe(coverage_by_ticker.head(15).to_dict(orient="records")),
        "unmatched_flow_rows_eval": unmatched_flow_rows,
        "duplicate_ticker_day_rows_total": dup_count,
        "net_volume_mismatch_rows_total": net_vol_mismatch,
        "net_value_mismatch_rows_total": net_value_mismatch,
        "null_ratios_eval": null_ratios,
    }
    source_gate_pass = (
        summary["row_coverage_eval"] >= SOURCE_MIN_ROW_COVERAGE
        and summary["tickers_with_any_flow_eval"] >= SOURCE_MIN_TICKERS_WITH_DATA
        and summary["tickers_with_coverage_ge_60pct"] >= SOURCE_MIN_TICKERS_COVERAGE_60
        and dup_count == 0
        and net_vol_mismatch == 0
        and net_value_mismatch == 0
    )
    summary["source_gate_pass"] = bool(source_gate_pass)
    return summary, coverage_by_ticker


def rank_by_day(frame: pd.DataFrame, source_col: str, output_col: str, *, ascending: bool = True) -> pd.DataFrame:
    out = frame[["time", "ticker", source_col]].copy()
    out[output_col] = out.groupby("time")[source_col].rank(method="average", pct=True, ascending=ascending)
    return out[["time", "ticker", output_col]]


def build_feature_panel(flow: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    merged = stock.merge(flow, on=["time", "ticker"], how="inner", suffixes=("", "_flow"))
    merged = merged.sort_values(["ticker", "time"]).reset_index(drop=True)
    merged["volume_safe"] = merged["volume"].replace(0, np.nan)
    merged["ff_net_vol_share_1d"] = merged["foreign_net_volume"] / merged["volume_safe"]
    merged["ff_buy_vol_share_1d"] = merged["foreign_buy_volume"] / merged["volume_safe"]
    merged["ff_sell_vol_share_1d"] = merged["foreign_sell_volume"] / merged["volume_safe"]
    merged["ff_net_value_1d"] = merged["foreign_net_value"] / 1e9

    grouped = merged.groupby("ticker", group_keys=False)
    for source_col, output_col in [
        ("foreign_net_volume", "foreign_net_volume_5d"),
        ("foreign_buy_volume", "foreign_buy_volume_5d"),
        ("foreign_sell_volume", "foreign_sell_volume_5d"),
        ("volume", "volume_5d"),
        ("foreign_net_value", "foreign_net_value_5d"),
    ]:
        merged[output_col] = grouped[source_col].rolling(5, min_periods=3).sum().reset_index(level=0, drop=True)

    merged["ff_net_vol_share_5d"] = merged["foreign_net_volume_5d"] / merged["volume_5d"].replace(0, np.nan)
    merged["ff_buy_share_5d"] = merged["foreign_buy_volume_5d"] / merged["volume_5d"].replace(0, np.nan)
    merged["ff_sell_share_5d"] = merged["foreign_sell_volume_5d"] / merged["volume_5d"].replace(0, np.nan)
    merged["ff_net_value_5d"] = merged["foreign_net_value_5d"] / 1e9

    for source_col in [
        "ff_net_vol_share_1d",
        "ff_net_vol_share_5d",
        "ff_net_value_1d",
        "ff_net_value_5d",
        "ff_buy_share_5d",
        "ff_sell_share_5d",
    ]:
        merged[f"{source_col}_lag1"] = grouped[source_col].shift(1)

    ranked = merged[["time", "ticker"]].copy()
    rank_specs = [
        ("ff_net_vol_share_1d", "xs_ff_net_vol_share_1d_rank", True),
        ("ff_net_vol_share_1d_lag1", "xs_ff_net_vol_share_1d_lag1_rank", True),
        ("ff_net_vol_share_5d", "xs_ff_net_vol_share_5d_rank", True),
        ("ff_net_vol_share_5d_lag1", "xs_ff_net_vol_share_5d_lag1_rank", True),
        ("ff_net_value_1d", "xs_ff_net_value_1d_rank", True),
        ("ff_net_value_5d", "xs_ff_net_value_5d_rank", True),
        ("ff_buy_share_5d", "xs_ff_buy_share_5d_rank", True),
        ("ff_sell_share_5d", "xs_ff_sell_share_5d_rank", True),
        ("foreign_ownership_pct", "xs_ff_ownership_pct_rank", True),
        ("foreign_room_remaining", "xs_ff_room_scarcity_rank", False),
    ]
    for source_col, output_col, ascending in rank_specs:
        ranked = ranked.merge(rank_by_day(merged, source_col, output_col, ascending=ascending), on=["time", "ticker"])
    return ranked


def phase_mask(frame: pd.DataFrame, start: str, end: str) -> pd.Series:
    return frame["time"].between(pd.Timestamp(start), pd.Timestamp(end))


def ic_for_frame(frame: pd.DataFrame, feature_col: str) -> dict[str, object]:
    clean = frame[[feature_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < MIN_YEARLY_OBS:
        return {"n": int(len(clean)), "avg_ic": None, "p_value": None}
    stat = spearmanr(clean[feature_col], clean["actual"])
    return {
        "n": int(len(clean)),
        "avg_ic": float(np.asarray(stat.statistic).flat[0]),
        "p_value": float(np.asarray(stat.pvalue).flat[0]),
    }


def yearly_ic(frame: pd.DataFrame, feature_col: str, phase: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for year, group in frame.groupby(frame["time"].dt.year):
        clean = group[[feature_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_YEARLY_OBS:
            continue
        stat = spearmanr(clean[feature_col], clean["actual"])
        rows.append(
            {
                "phase": phase,
                "feature": feature_col,
                "year": int(year),
                "n": int(len(clean)),
                "ic": float(np.asarray(stat.statistic).flat[0]),
                "p_value": float(np.asarray(stat.pvalue).flat[0]),
            }
        )
    return rows


def summarize_years(rows: list[dict[str, object]], direction: int | None = None) -> dict[str, object]:
    if not rows:
        return {"years": 0, "pos_years": 0, "directional_years": 0, "pct_directional_years": None}
    ics = [float(row["ic"]) for row in rows]
    if direction is None:
        avg = float(np.mean(ics))
        direction = 1 if avg >= 0 else -1
    directional = sum(1 for ic in ics if direction * ic > 0)
    return {
        "years": int(len(ics)),
        "pos_years": int(sum(1 for ic in ics if ic > 0)),
        "direction": int(direction),
        "directional_years": int(directional),
        "pct_directional_years": float(directional / len(ics)),
    }


def evaluate_features(merged: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    result_rows: list[dict[str, object]] = []
    yearly_rows: list[dict[str, object]] = []
    phase_specs = {
        "dev_2015_2022": (DEV_START, DEV_END),
        "validation_2023_2024": (VALIDATION_START, VALIDATION_END),
        "confirmation_2025": (CONFIRMATION_START, CONFIRMATION_END),
        "full_2015_2025": (PREDICTIVE_START, PREDICTIVE_END),
    }

    for feature_col in FEATURE_COLS:
        phase_stats: dict[str, dict[str, object]] = {}
        phase_years: dict[str, list[dict[str, object]]] = {}
        for phase, (start, end) in phase_specs.items():
            phase_frame = merged.loc[phase_mask(merged, start, end)].copy()
            stats = ic_for_frame(phase_frame, feature_col)
            years = yearly_ic(phase_frame, feature_col, phase)
            phase_stats[phase] = stats
            phase_years[phase] = years
            yearly_rows.extend(years)

        dev_ic = phase_stats["dev_2015_2022"].get("avg_ic")
        direction = 1 if (dev_ic or 0) >= 0 else -1
        dev_year_summary = summarize_years(phase_years["dev_2015_2022"], direction=direction)
        validation_ic = phase_stats["validation_2023_2024"].get("avg_ic")
        confirmation_ic = phase_stats["confirmation_2025"].get("avg_ic")
        full_ic = phase_stats["full_2015_2025"].get("avg_ic")

        corr_s1 = spearman_stat(merged[feature_col], merged["xs_proba"])
        coverage = float(merged[feature_col].notna().mean())
        dev_gate = (
            abs(dev_ic or 0) >= PASS_IC
            and (dev_year_summary.get("pct_directional_years") or 0) >= PASS_PCT_YEARS
        )
        validation_gate = validation_ic is not None and direction * validation_ic >= VALIDATION_MIN_ABS_IC
        confirmation_ok = confirmation_ic is not None and direction * confirmation_ic > 0
        corr_gate = abs(corr_s1) < PASS_CORR
        candidate_gate = bool(dev_gate and validation_gate and confirmation_ok and corr_gate)

        result_rows.append(
            {
                "feature": feature_col,
                "direction": "positive" if direction > 0 else "negative",
                "coverage": coverage,
                "corr_with_s1": corr_s1,
                "dev_avg_ic": dev_ic,
                "dev_n": phase_stats["dev_2015_2022"].get("n"),
                "dev_years": dev_year_summary.get("years"),
                "dev_directional_years": dev_year_summary.get("directional_years"),
                "dev_pct_directional_years": dev_year_summary.get("pct_directional_years"),
                "validation_avg_ic": validation_ic,
                "validation_n": phase_stats["validation_2023_2024"].get("n"),
                "confirmation_avg_ic": confirmation_ic,
                "confirmation_n": phase_stats["confirmation_2025"].get("n"),
                "full_avg_ic": full_ic,
                "full_n": phase_stats["full_2015_2025"].get("n"),
                "dev_gate": dev_gate,
                "validation_gate": validation_gate,
                "confirmation_ok": confirmation_ok,
                "corr_gate": corr_gate,
                "candidate_gate": candidate_gate,
            }
        )

    results = pd.DataFrame(result_rows)
    yearly = pd.DataFrame(yearly_rows)
    if not results.empty:
        results["abs_dev_ic"] = results["dev_avg_ic"].abs()
        results["abs_validation_ic"] = results["validation_avg_ic"].abs()
        results = results.sort_values(
            ["candidate_gate", "abs_validation_ic", "abs_dev_ic", "feature"],
            ascending=[False, False, False, True],
        ).reset_index(drop=True)
    passing = results.loc[results["candidate_gate"]].copy()
    best = results.iloc[0].to_dict() if not results.empty else {}
    summary = {
        "merged_rows": int(len(merged)),
        "merged_tickers": int(merged["ticker"].nunique()) if not merged.empty else 0,
        "merged_dates": int(merged["time"].nunique()) if not merged.empty else 0,
        "feature_count": int(len(FEATURE_COLS)),
        "passing_features": passing["feature"].tolist() if not passing.empty else [],
        "best_feature": _json_safe(best),
    }
    return results, yearly, summary


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    flow = load_flow()
    stock = load_stock_panel()
    source_summary, coverage_by_ticker = audit_source(flow, stock)
    feature_panel = build_feature_panel(flow, stock)
    s1 = load_s1_frame()
    merged = s1.merge(feature_panel, on=["time", "ticker"], how="inner")
    merged = merged.loc[phase_mask(merged, PREDICTIVE_START, PREDICTIVE_END)].copy()
    results, yearly, predictive_summary = evaluate_features(merged)

    coverage_path = OUT_DIR / f"{ts}_h327_cafef_foreign_flow_coverage_by_ticker.parquet"
    results_path = OUT_DIR / f"{ts}_h327_cafef_foreign_flow_feature_results.parquet"
    yearly_path = OUT_DIR / f"{ts}_h327_cafef_foreign_flow_yearly_ic.parquet"
    details_path = DETAILS_DIR / f"{ts}_h327_cafef_foreign_flow_source_audit_details.json"
    coverage_by_ticker.to_parquet(coverage_path, index=False)
    results.to_parquet(results_path, index=False)
    yearly.to_parquet(yearly_path, index=False)

    passing_features = predictive_summary.get("passing_features") or []
    if passing_features:
        verdict = "PASSED"
        branch_decision = (
            "CafeF foreign-flow source coverage is usable and at least one simple "
            "feature clears the first dev/validation/confirmation standalone screen. "
            "Next: run a stricter redundancy audit versus the C4-C14 matrix before "
            "publishing any feature."
        )
    elif source_summary.get("source_gate_pass"):
        verdict = "MIXED"
        branch_decision = (
            "CafeF foreign-flow source coverage is usable, but the first simple "
            "foreign-flow feature screen did not clear the honest standalone gate. "
            "Next: inspect failure shape before deciding whether to narrow by liquidity, "
            "room scarcity, or sector ownership state."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "CafeF foreign-flow source coverage or integrity is not broad enough for "
            "a full-universe historical signal screen. Stop and repair/source-gate before modeling."
        )

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "source": source_summary,
        "predictive": predictive_summary,
    }
    details = {
        "summary": summary,
        "features": _json_safe(results.to_dict(orient="records")),
        "yearly_ic": _json_safe(yearly.to_dict(orient="records")),
    }
    details_path.write_text(json.dumps(details, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_cafef_foreign_flow_source_audit",
        name="h327_cafef_foreign_flow_source_audit",
        summary=summary,
        artifacts={
            "coverage_by_ticker": coverage_path,
            "feature_results": results_path,
            "yearly_ic": yearly_path,
            "details": details_path,
        },
        metadata={
            "hypothesis": "CafeF GDKhoiNgoai has enough source quality to reopen H95 and simple lagged foreign-flow ranks may add standalone alpha.",
            "protocol": {
                "source_window": f"{PREDICTIVE_START}..{PREDICTIVE_END}",
                "dev": f"{DEV_START}..{DEV_END}",
                "validation": f"{VALIDATION_START}..{VALIDATION_END}",
                "confirmation": f"{CONFIRMATION_START}..{CONFIRMATION_END}",
                "no_tuning_window": "2026+",
            },
        },
    )

    print("H327 CafeF foreign-flow source audit")
    print("=" * 72)
    print(f"verdict: {verdict}")
    print(f"source row coverage 2015-2025: {source_summary['row_coverage_eval']:.2%}")
    print(f"tickers with any flow: {source_summary['tickers_with_any_flow_eval']}")
    print(f"tickers with >=60% coverage: {source_summary['tickers_with_coverage_ge_60pct']}")
    print(f"duplicates: {source_summary['duplicate_ticker_day_rows_total']}")
    print(f"net mismatches: vol={source_summary['net_volume_mismatch_rows_total']} value={source_summary['net_value_mismatch_rows_total']}")
    print(f"merged predictive rows: {predictive_summary['merged_rows']:,}")
    print("top feature rows:")
    display_cols = [
        "feature",
        "direction",
        "dev_avg_ic",
        "dev_directional_years",
        "dev_years",
        "validation_avg_ic",
        "confirmation_avg_ic",
        "corr_with_s1",
        "candidate_gate",
    ]
    print(results[display_cols].head(10).to_string(index=False))
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
