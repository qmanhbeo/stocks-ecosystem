"""
AP: residual_signal_discovery (H477)

Tests whether S1 still predicts forward returns after removing
vol_expansion correlation. If the residual is non-zero, there
is independent signal beyond vol_expansion. If the residual is zero,
all current strong signals are vol_expansion proxies and the lab needs
new independent dimensions.

Connection: C23-C26 (H463-H471) all share vol_expansion+illiquidity as
the key regime amplifier. This test asks: is there anything LEFT?

Hypothesis:
- After regressing S1 on vol_expansion signal, the residual
  may still contain independent edge.
- If residual IC > 0.01 AND positive years >= 60%, independent signal exists.
- If residual IC <= 0, all S1 quality is vol_expansion-driven.

Ladder:
- PASS: residual IC > 0.01 AND positive years >= 60% — independent signal confirmed
- MIXED: residual IC 0.001-0.01 — marginal residual
- FAIL: residual IC <= 0 — no independent signal, all signals are vol_expansion proxies

Baseline: Random baselines.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    StateSpec,
    build_experiment_context,
    load_s1_decision_panel,
    evaluate_state_specs,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path


BRANCH_NAME = "ap_residual_signal_discovery"
MODE = "research_branch"


def parse_price_change(s):
    if pd.isna(s):
        return np.nan
    try:
        match = re.search(r'\(\s*([+-]?[\d,]+)\s*%\)', str(s))
        if match:
            return float(match.group(1).replace(',', '.'))
        return np.nan
    except:
        return np.nan


def compute_vol_regime(panel: pd.DataFrame, order_stats_path: str) -> pd.DataFrame:
    """Compute vol_expansion regime from order_stats, matching H463-H471."""
    panel = panel.copy()

    order_stats = pd.read_parquet(order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume"]],
        on=["time", "ticker"],
        how="left",
    )

    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]
    panel = panel.sort_values(["ticker", "time"])

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    panel = panel.dropna(subset=["vol_change"])

    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(
        method="average", pct=True
    )
    panel["vol_expansion_rank"] = vol_change_rank.fillna(0.5)
    panel["vol_expansion_signal"] = (panel["vol_expansion_rank"] >= 0.80).astype(float)

    return panel


def compute_s1_residual(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute cross-sectional S1 residual after removing vol_expansion signal.

    For each date, regress S1 on vol_expansion_rank (both cross-sectional ranks)
    and take the residual as the orthogonal signal. This gives us the part of S1
    that is NOT explained by vol_expansion.
    """
    panel = panel.copy()
    s1_col = S1_SCORE_COL
    ve_col = "vol_expansion_rank"

    residuals = []
    for time, grp in panel.groupby("time", sort=False):
        ve_vals = grp[ve_col].values.astype(float)
        s1_vals = grp[s1_col].values.astype(float)

        mask = ~(np.isnan(ve_vals) | np.isnan(s1_vals))
        if mask.sum() < 10:
            residuals.extend([np.nan] * len(grp))
            continue

        ve_clean = ve_vals[mask]
        s1_clean = s1_vals[mask]

        ve_mean = float(np.mean(ve_clean))
        s1_mean = float(np.mean(s1_clean))
        cov = float(np.dot(ve_clean - ve_mean, s1_clean - s1_mean)) / len(ve_clean)
        ve_var = float(np.dot(ve_clean - ve_mean, ve_clean - ve_mean)) / len(ve_clean)

        if ve_var < 1e-10:
            residuals.extend([np.nan] * len(grp))
            continue

        beta = cov / ve_var
        alpha = s1_mean - beta * ve_mean
        predicted = alpha + beta * ve_vals
        residual_vals = s1_vals - predicted

        residuals.extend(residual_vals.tolist())

    panel["s1_residual"] = np.array(residuals)

    panel["s1_residual_rank"] = panel.groupby("time", sort=False)["s1_residual"].rank(
        method="average", na_option="keep", pct=True
    )

    return panel


def load_ohlcv_5d_20d_avg(panel: pd.DataFrame, stock_dir: Path) -> pd.DataFrame:
    """Load 5d and 20d rolling volume from per-ticker OHLCV files for C23 checks."""
    panel = panel.copy()

    ohlcv_dfs = []
    for f in sorted(stock_dir.glob("gia_lich_su_*_1D.parquet")):
        try:
            df = pd.read_parquet(f)
            ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "").upper()
            if "volume" not in df.columns:
                continue
            df = df.copy()
            df["ticker"] = ticker
            df = df.rename(columns={"date": "time"})
            df["time"] = pd.to_datetime(df["time"], errors="coerce")
            df = df.dropna(subset=["time"])
            df = df[df["time"].dt.year <= 2025]
            ohlcv_dfs.append(df[["time", "ticker", "volume"]])
        except Exception:
            continue

    if not ohlcv_dfs:
        return panel

    ohlcv = pd.concat(ohlcv_dfs, ignore_index=True)
    ohlcv = ohlcv.sort_values(["ticker", "time"])
    ohlcv["vol_5d"] = ohlcv.groupby("ticker")["volume"].transform(
        lambda x: x.rolling(5, min_periods=4).mean()
    )
    ohlcv["vol_20d"] = ohlcv.groupby("ticker")["volume"].transform(
        lambda x: x.rolling(20, min_periods=15).mean()
    )

    panel = panel.merge(
        ohlcv[["time", "ticker", "vol_5d", "vol_20d"]],
        on=["time", "ticker"],
        how="left",
    )

    vol_change = (panel["vol_5d"] - panel["vol_20d"]) / panel["vol_20d"].replace(0, np.nan)
    panel["vol_change_pct_ohlcv"] = vol_change

    vol_rank = panel.groupby("time", sort=False)["vol_change_pct_ohlcv"].rank(
        method="average", na_option="keep", pct=True
    )
    panel["vol_expansion_ohlcv_rank"] = vol_rank.fillna(0.5)

    return panel


SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "S1 residual after removing vol_expansion correlation still contains "
        "independent signal. If IC > 0.01 with >= 60% positive years, the lab "
        "has genuine independent edge beyond vol_expansion. If residual is "
        "zero or negative, all current signals are vol_expansion proxies."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={
        S1_SCORE_COL: "decision-time S1 probability score",
        "s1_residual_rank": "S1 residual after removing vol_expansion correlation",
    },
)


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec(
        "high_vol_expansion",
        "vol_expansion_rank >= 0.80",
        family="vol_expansion",
        baseline="all_rows",
    ),
    StateSpec(
        "low_vol_expansion",
        "vol_expansion_rank <= 0.20",
        family="vol_expansion",
        baseline="all_rows",
    ),
    StateSpec(
        "s1_residual_top20",
        "S1 residual rank top 20% (highest orthogonal S1)",
        family="residual",
        baseline="all_rows",
        primary=True,
    ),
    StateSpec(
        "s1_residual_bot20",
        "S1 residual rank bottom 20% (lowest orthogonal S1)",
        family="residual",
        baseline="all_rows",
    ),
    StateSpec(
        "high_vol_exp_top20_s1",
        "High vol expansion AND top 20% S1 residual",
        family="combo",
        baseline="high_vol_expansion",
    ),
    StateSpec(
        "high_vol_exp_bot20_s1",
        "High vol expansion AND bottom 20% S1 residual",
        family="combo",
        baseline="high_vol_expansion",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AP: residual_signal_discovery. Tests S1 after removing vol_expansion correlation."
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument(
        "--order-stats-path", type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
    parser.add_argument(
        "--stock-path", type=str,
        default=str(data_path("stock")),
    )
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )
    panel = compute_vol_regime(panel, args.order_stats_path)
    panel = compute_s1_residual(panel)

    panel = load_ohlcv_5d_20d_avg(panel, Path(args.stock_path))

    panel["all_rows"] = True
    panel["high_vol_expansion"] = panel["vol_expansion_rank"] >= 0.80
    panel["low_vol_expansion"] = panel["vol_expansion_rank"] <= 0.20
    panel["s1_residual_top20"] = panel["s1_residual_rank"] >= 0.80
    panel["s1_residual_bot20"] = panel["s1_residual_rank"] <= 0.20
    panel["high_vol_exp_top20_s1"] = panel["high_vol_expansion"] & panel["s1_residual_top20"]
    panel["high_vol_exp_bot20_s1"] = panel["high_vol_expansion"] & panel["s1_residual_bot20"]

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")
    panel = load_panel(args, spec)
    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results_s1, yearly_s1 = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_res, yearly_res = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col="s1_residual_rank",
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_s1["evaluation_score"] = S1_SCORE_COL
    results_res["evaluation_score"] = "s1_residual_rank"
    yearly_s1["evaluation_score"] = S1_SCORE_COL
    yearly_res["evaluation_score"] = "s1_residual_rank"

    results = pd.concat([results_s1, results_res], ignore_index=True)
    yearly = pd.concat([yearly_s1, yearly_res], ignore_index=True)

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    baseline_raw = results[
        (results["name"] == "all_rows") & (results["evaluation_score"] == S1_SCORE_COL)
    ]
    baseline_ic_raw = float(baseline_raw["avg_ic"].iloc[0]) if not baseline_raw.empty else None

    res_top20_s1 = results[
        (results["name"] == "s1_residual_top20") & (results["evaluation_score"] == S1_SCORE_COL)
    ]
    res_top20_res = results[
        (results["name"] == "s1_residual_top20") & (results["evaluation_score"] == "s1_residual_rank")
    ]

    res_s1_ic = float(res_top20_s1["avg_ic"].iloc[0]) if not res_top20_s1.empty else None
    res_res_ic = float(res_top20_res["avg_ic"].iloc[0]) if not res_top20_res.empty else None
    res_res_years = int(res_top20_res["positive_years"].iloc[0]) if not res_top20_res.empty else 0
    res_res_total = int(res_top20_res["years"].iloc[0]) if not res_top20_res.empty else 0
    res_res_pct = float(res_top20_res["pct_positive_years"].iloc[0]) if not res_top20_res.empty else 0.0

    res_lift_vs_raw = (res_s1_ic - baseline_ic_raw) if res_s1_ic is not None and baseline_ic_raw is not None else None

    if res_res_ic is not None and res_res_ic > 0.01 and res_res_pct >= 0.60:
        decision = "PASSED"
    elif res_res_ic is not None and res_res_ic > 0.001 and res_res_pct >= 0.40:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "vol_expansion_rows": int(panel["high_vol_expansion"].sum()),
            "residual_top20_rows": int(panel["s1_residual_top20"].sum()),
            "baseline_s1_ic": baseline_ic_raw,
            "s1_top20_s1_score_ic": res_s1_ic,
            "residual_top20_s1_residual_score_ic": res_res_ic,
            "residual_top20_pos_years": f"{res_res_years}/{res_res_total}",
            "residual_top20_pct": f"{res_res_pct:.1%}",
            "s1_top20_lift_vs_raw_baseline": res_lift_vs_raw,
            "hypothesis": "S1 residual after removing vol_expansion correlation",
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "scores_evaluated": [S1_SCORE_COL, "s1_residual_rank"],
        },
    )

    print(results.sort_values(["evaluation_score", "avg_ic"], ascending=[True, False]).to_string(index=False))
    print(f"\nBaseline S1 IC (raw): {baseline_ic_raw}")
    print(f"S1 top20 IC (evaluated on S1 score): {res_s1_ic}")
    print(f"S1 top20 IC (evaluated on residual score): {res_res_ic} ({res_res_years}/{res_res_total} positive years, {res_res_pct:.1%})")
    print(f"S1 top20 lift vs raw baseline: {res_lift_vs_raw}")
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()