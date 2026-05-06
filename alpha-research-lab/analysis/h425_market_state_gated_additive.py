"""
H425: Market-State Gated Additive
Test if different market states prefer different weights.
Based on B51: VNI-up vs VNI-down may prefer different weights.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_signal_research import (  # noqa: E402
    FeaturePanelSpec,
    compute_spearman_ic,
    load_or_build_additive_research_panel,
    write_additive_run_summary,
)
from src.experiment_contract import (  # noqa: E402
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
)
from src.repo_paths import data_path  # noqa: E402

BRANCH_NAME = "market_state_gated_additive"
MODE = "research_branch"
MAX_YEAR = 2025
ORDER_PRESSURE_PATH = data_path("features/xs_order_pressure_daily.parquet")
BENCHMARK_PATH = data_path("stock/gia_lich_su_VNINDEX_1D.parquet")

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis="Test whether VNI up/down market states prefer different fixed Vol/S1 additive weights.",
    start_year=2018,
    end_year=MAX_YEAR,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={
        S1_SCORE_COL: "decision-time S1 probability score",
        "vol_rank": "date-wise rank of order_volume_ratio",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H425 Market-state test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-pressure-path", type=str, default=str(ORDER_PRESSURE_PATH))
    parser.add_argument("--benchmark-path", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    return parser.parse_args()


def compute_ic(panel: pd.DataFrame, score_col: str, target_col: str) -> float:
    return compute_spearman_ic(panel, score_col, target_col, min_rows=50)


def load_vni_returns(path: str | Path) -> pd.DataFrame:
    benchmark_path = Path(path)
    if not benchmark_path.exists():
        raise FileNotFoundError(
            "H425 requires the canonical VNINDEX daily file at "
            f"{benchmark_path}. Refresh or restore data/stock/gia_lich_su_VNINDEX_1D.parquet."
        )
    vni = pd.read_parquet(benchmark_path, columns=["time", "close"])
    vni["time"] = pd.to_datetime(vni["time"], errors="coerce").dt.normalize()
    vni = vni.dropna(subset=["time"]).sort_values("time").drop_duplicates("time")
    vni = vni.rename(columns={"close": "vni_close"})
    vni["vni_ret"] = pd.to_numeric(vni["vni_close"], errors="coerce").pct_change(1)
    return vni[["time", "vni_ret"]]


def main():
    args = parse_args()
    spec = ExperimentSpec(
        name=SPEC.name,
        mode=SPEC.mode,
        hypothesis=SPEC.hypothesis,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        target_columns=SPEC.target_columns,
        score_columns=SPEC.score_columns,
    )

    print("Loading S1 + Volume additive panel...")
    panel_result = load_or_build_additive_research_panel(
        spec=spec,
        cache_name=f"{BRANCH_NAME}_{spec.start_year}_{spec.end_year}",
        s1_path=args.s1_path,
        feature_specs=[
            FeaturePanelSpec(
                name="order_pressure_volume",
                path=Path(args.order_pressure_path),
                columns=("order_volume_ratio",),
                rank_columns={"order_volume_ratio": "vol_rank"},
            )
        ],
    )

    print("Loading VNI...")
    vni = load_vni_returns(args.benchmark_path)

    panel = panel_result.frame.copy()
    panel = panel.merge(vni, on="time", how="left")
    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
        & panel["vni_ret"].notna()
    ].copy()

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    # Create market state: up = VNI > 0, down = VNI < 0
    panel["is_up"] = panel["vni_ret"] > 0

    print(f"\nPanel rows: {len(panel):,}")
    print(f"Up days: {panel['is_up'].sum():,}")
    print(f"Down days: {(~panel['is_up']).sum():,}")

    # Uniform H413
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    # IC by market state
    up_panel = panel[panel["is_up"]]
    down_panel = panel[~panel["is_up"]]

    ic_up = compute_ic(up_panel, "score_h413", S1_TARGET_COL)
    ic_down = compute_ic(down_panel, "score_h413", S1_TARGET_COL)

    print(f"\n=== H425 Market-State Gated Results ===")
    print(f"H413 IC in UP days:   {ic_up:+.5f} (n={len(up_panel):,})")
    print(f"H413 IC in DOWN days: {ic_down:+.5f} (n={len(down_panel):,})")

    # Optimize weights in each state
    best_w_up = (0.10, 0.90)
    best_ic_up = -999
    for wv in [0.05, 0.10, 0.15, 0.20, 0.25]:
        ws = 1 - wv
        test_score = wv * up_panel["vol_rank"] + ws * up_panel[S1_SCORE_COL]
        test_panel = up_panel.copy()
        test_panel["test"] = test_score
        ic = compute_ic(test_panel, "test", S1_TARGET_COL)
        if ic > best_ic_up:
            best_ic_up = ic
            best_w_up = (wv, ws)

    best_w_down = (0.10, 0.90)
    best_ic_down = -999
    for wv in [0.05, 0.10, 0.15, 0.20, 0.25]:
        ws = 1 - wv
        test_score = wv * down_panel["vol_rank"] + ws * down_panel[S1_SCORE_COL]
        test_panel = down_panel.copy()
        test_panel["test"] = test_score
        ic = compute_ic(test_panel, "test", S1_TARGET_COL)
        if ic > best_ic_down:
            best_ic_down = ic
            best_w_down = (wv, ws)

    print(f"\nOptimal in UP:   {best_w_up[0]:.2f}V+{best_w_up[1]:.2f}S => {best_ic_up:+.5f}")
    print(f"Optimal in DOWN: {best_w_down[0]:.2f}V+{best_w_down[1]:.2f}S => {best_ic_down:+.5f}")

    # Compare gated vs uniform
    panel["score_gated"] = np.where(
        panel["is_up"],
        best_w_up[0] * panel["vol_rank"] + best_w_up[1] * panel[S1_SCORE_COL],
        best_w_down[0] * panel["vol_rank"] + best_w_down[1] * panel[S1_SCORE_COL]
    )

    ic_uniform = compute_ic(panel, "score_h413", S1_TARGET_COL)
    ic_gated = compute_ic(panel, "score_gated", S1_TARGET_COL)

    print(f"\n=== Final Comparison ===")
    print(f"Uniform H413:   {ic_uniform:+.5f}")
    print(f"State-gated:     {ic_gated:+.5f}")
    print(f"Delta:         {ic_gated - ic_uniform:+.5f}")

    result = {
        "ic_up_uniform": float(ic_up),
        "ic_down_uniform": float(ic_down),
        "best_w_up": best_w_up,
        "best_w_down": best_w_down,
        "ic_up_opt": float(best_ic_up),
        "ic_down_opt": float(best_ic_down),
        "ic_uniform": float(ic_uniform),
        "ic_gated": float(ic_gated),
        "delta": float(ic_gated - ic_uniform),
    }

    summary_path = write_additive_run_summary(
        spec=spec,
        summary=result,
        artifacts={
            "additive_panel_cache": panel_result.cache_path,
            "additive_panel_manifest": panel_result.manifest_path,
        },
        metadata={
            "order_pressure_path": str(Path(args.order_pressure_path)),
            "benchmark_path": str(Path(args.benchmark_path)),
            "panel_cache_source": panel_result.source,
        },
    )

    print(f"\nSaved: {summary_path}")

    print(f"\n=== VERDICT ===")
    delta = ic_gated - ic_uniform
    if delta > 0.005:
        print("PASSED - gated helps")
    elif delta > 0:
        print("MIXED - marginal")
    else:
        print("FAILED - uniform is best")

    return result


if __name__ == "__main__":
    main()
