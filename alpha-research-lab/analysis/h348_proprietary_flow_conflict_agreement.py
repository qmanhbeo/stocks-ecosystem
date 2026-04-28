"""
H348: proprietary-flow conflict/agreement pilot.

Question:
    Does CafeF proprietary-desk flow add a distinct non-price actor surface
    after standalone foreign-flow and foreign-insider agreement failed to
    beat stronger daily-state benchmarks?

Design:
    - treat the proprietary-trading archive as a limited 2022+ source
    - use 2022-11 data only as rolling-feature warmup
    - evaluate 2023 as dev, 2024 as validation, and 2025 as confirmation
    - exclude 2026 from predictive use
    - test a small predeclared set of proprietary-flow and foreign/proprietary
      agreement/conflict ranks against the S1 next-day target

A pass here means "continue the branch with a stricter audit", not immediate
signal-library promotion, because the source has only three full predictive
years locally.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.h327_cafef_foreign_flow_source_audit import (  # noqa: E402
    PASS_CORR,
    _json_safe,
    load_flow,
    load_stock_panel,
    rank_by_day,
)
from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_s1_frame, spearman_stat  # noqa: E402


PROP_PATH = data_path("proprietary_trading/cafef/proprietary_trading_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

WARMUP_START = "2022-11-01"
DEV_START = "2023-01-01"
DEV_END = "2023-12-31"
VALIDATION_START = "2024-01-01"
VALIDATION_END = "2024-12-31"
CONFIRMATION_START = "2025-01-01"
CONFIRMATION_END = "2025-12-31"
PREDICTIVE_START = DEV_START
PREDICTIVE_END = CONFIRMATION_END

MIN_PHASE_OBS = 500
MIN_YEARLY_OBS = 500
PASS_IC = 0.01
VALIDATION_MIN_ABS_IC = 0.005

FEATURE_COLS = [
    "xs_prop_net_share_1d_rank",
    "xs_prop_net_share_5d_rank",
    "xs_prop_buy_share_5d_rank",
    "xs_prop_sell_share_5d_rank",
    "xs_prop_abs_activity_5d_rank",
    "xs_prop_ff_agreement_5d_rank",
    "xs_ff_buy_prop_sell_conflict_5d_rank",
    "xs_prop_buy_ff_sell_conflict_5d_rank",
]


def _phase_mask(frame: pd.DataFrame, start: str, end: str) -> pd.Series:
    return frame["time"].between(pd.Timestamp(start), pd.Timestamp(end))


def _rolling_sum(grouped: pd.core.groupby.DataFrameGroupBy, column: str, window: int) -> pd.Series:
    return grouped[column].rolling(window, min_periods=max(3, window // 2)).sum().reset_index(level=0, drop=True)


def _safe_spearman(left: pd.Series, right: pd.Series, *, min_rows: int = MIN_PHASE_OBS) -> float | None:
    clean = (
        pd.concat([left.rename("left"), right.rename("right")], axis=1)
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    if len(clean) < min_rows or clean["left"].nunique() < 3 or clean["right"].nunique() < 3:
        return None
    stat = spearmanr(clean["left"], clean["right"]).statistic
    if not np.isfinite(stat):
        return None
    return float(np.asarray(stat).flat[0])


def load_proprietary_flow() -> pd.DataFrame:
    if not PROP_PATH.exists():
        raise FileNotFoundError(f"Missing proprietary-trading panel: {PROP_PATH}")
    prop = pd.read_parquet(PROP_PATH)
    prop["time"] = pd.to_datetime(prop["date"], errors="coerce")
    prop["ticker"] = prop["ticker"].astype(str).str.upper()
    numeric_cols = [
        "proprietary_buy_volume",
        "proprietary_sell_volume",
        "proprietary_net_volume",
        "proprietary_buy_value",
        "proprietary_sell_value",
        "proprietary_net_value",
    ]
    for column in numeric_cols:
        prop[column] = pd.to_numeric(prop[column], errors="coerce").fillna(0.0)
    return prop.dropna(subset=["time", "ticker"]).sort_values(["ticker", "time"]).reset_index(drop=True)


def _source_summary(prop: pd.DataFrame, stock: pd.DataFrame) -> dict[str, object]:
    eval_stock = stock.loc[_phase_mask(stock, PREDICTIVE_START, PREDICTIVE_END), ["time", "ticker"]].drop_duplicates()
    eval_prop = prop.loc[_phase_mask(prop, PREDICTIVE_START, PREDICTIVE_END)].copy()
    prop_keys = eval_prop[["time", "ticker"]].drop_duplicates()
    joined = eval_stock.merge(prop_keys.assign(has_prop=True), on=["time", "ticker"], how="left")
    joined["has_prop"] = joined["has_prop"].eq(True)
    by_year = []
    for year, group in eval_prop.groupby(eval_prop["time"].dt.year):
        by_year.append(
            {
                "year": int(year),
                "rows": int(len(group)),
                "tickers": int(group["ticker"].nunique()),
                "dates": int(group["time"].nunique()),
                "nonzero_net_rows": int((group["proprietary_net_volume"] != 0).sum()),
            }
        )
    return {
        "prop_path": str(PROP_PATH),
        "prop_rows_total": int(len(prop)),
        "prop_tickers_total": int(prop["ticker"].nunique()),
        "prop_date_min": _json_safe(prop["time"].min()),
        "prop_date_max": _json_safe(prop["time"].max()),
        "predictive_window": f"{PREDICTIVE_START}..{PREDICTIVE_END}",
        "stock_rows_eval": int(len(eval_stock)),
        "prop_rows_eval": int(len(prop_keys)),
        "row_coverage_eval": float(joined["has_prop"].mean()),
        "tickers_with_any_prop_eval": int(prop_keys["ticker"].nunique()),
        "by_year": by_year,
        "missing_prop_rows_are_treated_as_zero": True,
    }


def build_feature_panel(prop: pd.DataFrame, stock: pd.DataFrame, foreign: pd.DataFrame) -> pd.DataFrame:
    start = pd.Timestamp(WARMUP_START)
    end = pd.Timestamp(PREDICTIVE_END)
    base = stock.loc[stock["time"].between(start, end), ["time", "ticker", "volume"]].copy()

    prop_cols = [
        "time",
        "ticker",
        "proprietary_buy_volume",
        "proprietary_sell_volume",
        "proprietary_net_volume",
    ]
    flow_cols = [
        "time",
        "ticker",
        "foreign_buy_volume",
        "foreign_sell_volume",
        "foreign_net_volume",
    ]
    merged = base.merge(prop[prop_cols], on=["time", "ticker"], how="left")
    merged = merged.merge(foreign[flow_cols], on=["time", "ticker"], how="left")
    fill_cols = [
        "proprietary_buy_volume",
        "proprietary_sell_volume",
        "proprietary_net_volume",
        "foreign_buy_volume",
        "foreign_sell_volume",
        "foreign_net_volume",
    ]
    for column in fill_cols:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    merged["volume"] = pd.to_numeric(merged["volume"], errors="coerce")
    merged = merged.sort_values(["ticker", "time"]).reset_index(drop=True)
    grouped = merged.groupby("ticker", group_keys=False)

    volume_5d = _rolling_sum(grouped, "volume", 5).replace(0, np.nan)
    prop_buy_5d = _rolling_sum(grouped, "proprietary_buy_volume", 5)
    prop_sell_5d = _rolling_sum(grouped, "proprietary_sell_volume", 5)
    prop_net_5d = _rolling_sum(grouped, "proprietary_net_volume", 5)
    foreign_net_5d = _rolling_sum(grouped, "foreign_net_volume", 5)

    merged["prop_net_share_1d"] = merged["proprietary_net_volume"] / merged["volume"].replace(0, np.nan)
    merged["prop_net_share_5d"] = prop_net_5d / volume_5d
    merged["prop_buy_share_5d"] = prop_buy_5d / volume_5d
    merged["prop_sell_share_5d"] = prop_sell_5d / volume_5d
    merged["prop_abs_activity_5d"] = (prop_buy_5d + prop_sell_5d) / volume_5d
    merged["ff_net_share_5d"] = foreign_net_5d / volume_5d

    ranked = merged[["time", "ticker"]].copy()
    rank_specs = [
        ("prop_net_share_1d", "xs_prop_net_share_1d_rank"),
        ("prop_net_share_5d", "xs_prop_net_share_5d_rank"),
        ("prop_buy_share_5d", "xs_prop_buy_share_5d_rank"),
        ("prop_sell_share_5d", "xs_prop_sell_share_5d_rank"),
        ("prop_abs_activity_5d", "xs_prop_abs_activity_5d_rank"),
        ("ff_net_share_5d", "xs_ff_net_share_5d_rank"),
    ]
    for source_col, output_col in rank_specs:
        ranked = ranked.merge(rank_by_day(merged, source_col, output_col, ascending=True), on=["time", "ticker"])

    ranked["xs_prop_ff_agreement_5d_rank"] = np.minimum(
        ranked["xs_prop_net_share_5d_rank"],
        ranked["xs_ff_net_share_5d_rank"],
    )
    ranked["xs_ff_buy_prop_sell_conflict_5d_rank"] = (
        ranked["xs_ff_net_share_5d_rank"] * (1.0 - ranked["xs_prop_net_share_5d_rank"])
    )
    ranked["xs_prop_buy_ff_sell_conflict_5d_rank"] = (
        ranked["xs_prop_net_share_5d_rank"] * (1.0 - ranked["xs_ff_net_share_5d_rank"])
    )
    return ranked[["time", "ticker", *FEATURE_COLS]]


def ic_for_frame(frame: pd.DataFrame, feature_col: str) -> dict[str, object]:
    clean = frame[[feature_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < MIN_PHASE_OBS or clean[feature_col].nunique() < 3:
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
        if len(clean) < MIN_YEARLY_OBS or clean[feature_col].nunique() < 3:
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


def evaluate_features(merged: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    result_rows: list[dict[str, object]] = []
    yearly_rows: list[dict[str, object]] = []
    phase_specs = {
        "dev_2023": (DEV_START, DEV_END),
        "validation_2024": (VALIDATION_START, VALIDATION_END),
        "confirmation_2025": (CONFIRMATION_START, CONFIRMATION_END),
        "full_2023_2025": (PREDICTIVE_START, PREDICTIVE_END),
    }

    for feature_col in FEATURE_COLS:
        phase_stats: dict[str, dict[str, object]] = {}
        phase_years: dict[str, list[dict[str, object]]] = {}
        for phase, (start, end) in phase_specs.items():
            phase_frame = merged.loc[_phase_mask(merged, start, end)].copy()
            stats = ic_for_frame(phase_frame, feature_col)
            years = yearly_ic(phase_frame, feature_col, phase)
            phase_stats[phase] = stats
            phase_years[phase] = years
            yearly_rows.extend(years)

        dev_ic = phase_stats["dev_2023"].get("avg_ic")
        direction = 1 if (dev_ic or 0.0) >= 0 else -1
        validation_ic = phase_stats["validation_2024"].get("avg_ic")
        confirmation_ic = phase_stats["confirmation_2025"].get("avg_ic")
        full_ic = phase_stats["full_2023_2025"].get("avg_ic")
        corr_s1 = spearman_stat(merged[feature_col], merged["xs_proba"])
        dev_gate = abs(dev_ic or 0.0) >= PASS_IC
        validation_gate = validation_ic is not None and direction * validation_ic >= VALIDATION_MIN_ABS_IC
        confirmation_ok = confirmation_ic is not None and direction * confirmation_ic > 0
        corr_gate = abs(corr_s1) < PASS_CORR
        candidate_gate = bool(dev_gate and validation_gate and confirmation_ok and corr_gate)
        near_gate = bool(
            not candidate_gate
            and validation_ic is not None
            and confirmation_ic is not None
            and direction * validation_ic > 0
            and direction * confirmation_ic > 0
            and corr_gate
        )

        result_rows.append(
            {
                "feature": feature_col,
                "direction": "positive" if direction > 0 else "negative",
                "coverage": float(merged[feature_col].notna().mean()),
                "corr_with_s1": corr_s1,
                "dev_avg_ic": dev_ic,
                "dev_n": phase_stats["dev_2023"].get("n"),
                "validation_avg_ic": validation_ic,
                "validation_n": phase_stats["validation_2024"].get("n"),
                "confirmation_avg_ic": confirmation_ic,
                "confirmation_n": phase_stats["confirmation_2025"].get("n"),
                "full_avg_ic": full_ic,
                "full_n": phase_stats["full_2023_2025"].get("n"),
                "dev_gate": dev_gate,
                "validation_gate": validation_gate,
                "confirmation_ok": confirmation_ok,
                "corr_gate": corr_gate,
                "candidate_gate": candidate_gate,
                "near_gate": near_gate,
            }
        )

    results = pd.DataFrame(result_rows)
    yearly = pd.DataFrame(yearly_rows)
    if not results.empty:
        results["abs_validation_ic"] = results["validation_avg_ic"].abs()
        results["abs_dev_ic"] = results["dev_avg_ic"].abs()
        results = results.sort_values(
            ["candidate_gate", "near_gate", "abs_validation_ic", "abs_dev_ic", "feature"],
            ascending=[False, False, False, False, True],
        ).reset_index(drop=True)
    passing = results.loc[results["candidate_gate"]].copy()
    near = results.loc[results["near_gate"]].copy()
    return results, yearly, {
        "merged_rows": int(len(merged)),
        "merged_tickers": int(merged["ticker"].nunique()) if not merged.empty else 0,
        "merged_dates": int(merged["time"].nunique()) if not merged.empty else 0,
        "feature_count": int(len(FEATURE_COLS)),
        "passing_features": passing["feature"].tolist() if not passing.empty else [],
        "near_features": near["feature"].tolist() if not near.empty else [],
        "best_feature": _json_safe(results.iloc[0].to_dict()) if not results.empty else {},
    }


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    prop = load_proprietary_flow()
    stock = load_stock_panel()
    foreign = load_flow()
    source_summary = _source_summary(prop, stock)
    feature_panel = build_feature_panel(prop, stock, foreign)
    s1 = load_s1_frame()
    merged = s1.merge(feature_panel, on=["time", "ticker"], how="inner")
    merged = merged.loc[_phase_mask(merged, PREDICTIVE_START, PREDICTIVE_END)].copy()
    results, yearly, predictive_summary = evaluate_features(merged)

    results_path = OUT_DIR / f"{ts}_h348_proprietary_flow_conflict_agreement_results.parquet"
    yearly_path = OUT_DIR / f"{ts}_h348_proprietary_flow_conflict_agreement_yearly_ic.parquet"
    details_path = DETAILS_DIR / f"{ts}_h348_proprietary_flow_conflict_agreement_details.json"
    results.to_parquet(results_path, index=False)
    yearly.to_parquet(yearly_path, index=False)

    passing = predictive_summary.get("passing_features") or []
    near = predictive_summary.get("near_features") or []
    if passing:
        verdict = "PASSED"
        branch_decision = (
            "At least one proprietary-flow agreement/conflict feature survived the limited 2023/2024/2025 pilot. "
            "Continue with robustness and source-hole audits before any promotion language."
        )
    elif near:
        verdict = "MIXED"
        branch_decision = (
            "Some proprietary-flow features kept validation and confirmation directionally aligned, but the fixed dev gate did not pass. "
            "Keep as weak offline evidence only."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "The limited-source proprietary-flow pilot did not produce a feature worth carrying forward. "
            "Do not tune proprietary-flow rank variants on this target."
        )

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "source": source_summary,
        "predictive": predictive_summary,
        "protocol": {
            "warmup": f"{WARMUP_START}..2022-12-31",
            "dev": f"{DEV_START}..{DEV_END}",
            "validation": f"{VALIDATION_START}..{VALIDATION_END}",
            "confirmation": f"{CONFIRMATION_START}..{CONFIRMATION_END}",
            "no_tuning_window": "2026+",
            "promotion_note": "limited 2022+ source; pass means continue, not promote",
        },
    }
    details_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "features": _json_safe(results.to_dict(orient="records")),
                "yearly_ic": _json_safe(yearly.to_dict(orient="records")),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    write_run_summary(
        ts=ts,
        mode="research_branch_proprietary_flow_conflict_agreement",
        name="h348_proprietary_flow_conflict_agreement",
        summary=summary,
        artifacts={
            "feature_results": results_path,
            "yearly_ic": yearly_path,
            "details": details_path,
        },
        metadata={
            "session": 187,
            "hypothesis": "Proprietary-desk flow may capture a distinct local institutional actor surface, especially when it agrees or conflicts with foreign flow.",
            "protocol": summary["protocol"],
            "feature_cols": FEATURE_COLS,
        },
    )

    print("H348 proprietary-flow conflict/agreement pilot")
    print("=" * 72)
    print(f"verdict: {verdict}")
    print(f"source row coverage 2023-2025: {source_summary['row_coverage_eval']:.2%}")
    print(f"best feature: {predictive_summary.get('best_feature', {}).get('feature')}")
    print(json.dumps(_json_safe(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
