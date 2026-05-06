"""
H413: Triple Signal Additive Test
Test Volume + S1 + C16 three-way additive.
Based on H410: additive works with S1. H412: C16 too weak alone.
Hypothesis: S1 rescues C16, Volume adds minor lift.
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
    compute_yearly_spearman_ic,
    load_or_build_additive_research_panel,
    write_additive_run_summary,
)
from src.artifact_contract import atomic_write_json  # noqa: E402
from src.experiment_contract import (  # noqa: E402
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
)
from src.repo_paths import data_path  # noqa: E402

BRANCH_NAME = "triple_signal_additive"
MODE = "research_branch"
MAX_YEAR = 2025
ORDER_PRESSURE_PATH = data_path("features/xs_order_pressure_daily.parquet")

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis="Test whether volume rank plus C16 rank adds to the S1 decision-time score.",
    start_year=2018,
    end_year=MAX_YEAR,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={
        S1_SCORE_COL: "decision-time S1 probability score",
        "vol_rank": "date-wise rank of order_volume_ratio",
        "c16_rank": "date-wise rank of order_pressure_h359_active",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H413 Triple signal additive test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-pressure-path", type=str, default=str(ORDER_PRESSURE_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    return parser.parse_args()


def compute_ic(panel: pd.DataFrame, score_col: str, target_col: str) -> float:
    return compute_spearman_ic(panel, score_col, target_col, min_rows=50)


def compute_yearly_ic(panel: pd.DataFrame, score_col: str, target_col: str) -> dict[int, float]:
    return compute_yearly_spearman_ic(panel, score_col, target_col, min_rows=50)


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

    print("Loading S1 + Order Stats (Volume + C16)...")
    panel_result = load_or_build_additive_research_panel(
        spec=spec,
        cache_name=f"{BRANCH_NAME}_{spec.start_year}_{spec.end_year}",
        s1_path=args.s1_path,
        feature_specs=[
            FeaturePanelSpec(
                name="order_pressure_volume_c16",
                path=Path(args.order_pressure_path),
                columns=("order_volume_ratio", "order_pressure_h359_active"),
                rank_columns={
                    "order_volume_ratio": "vol_rank",
                    "order_pressure_h359_active": "c16_rank",
                },
            )
        ],
    )
    panel = panel_result.frame
    print(f"Merged panel rows: {len(panel):,}")

    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
        & panel["order_pressure_h359_active"].notna()
    ].copy()
    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")

    # Test combinations (following H410 pattern: 25% Volume + 75% S1 is winning combo)
    # Adding C16 on top: 0.2*Vol + 0.6*S1 + 0.2*C16 (or variations)
    panel["v025_s075_c000"] = 0.25 * panel["vol_rank"] + 0.75 * panel[S1_SCORE_COL]
    panel["v020_s060_c020"] = 0.20 * panel["vol_rank"] + 0.60 * panel[S1_SCORE_COL] + 0.20 * panel["c16_rank"]
    panel["v025_s070_c005"] = 0.25 * panel["vol_rank"] + 0.70 * panel[S1_SCORE_COL] + 0.05 * panel["c16_rank"]
    panel["v010_s090_c000"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]
    panel["v015_s070_c015"] = 0.15 * panel["vol_rank"] + 0.70 * panel[S1_SCORE_COL] + 0.15 * panel["c16_rank"]

    ic_s1 = compute_ic(panel, S1_SCORE_COL, S1_TARGET_COL)
    ic_vol = compute_ic(panel, "vol_rank", S1_TARGET_COL)
    ic_c16 = compute_ic(panel, "c16_rank", S1_TARGET_COL)
    ic_h410 = compute_ic(panel, "v025_s075_c000", S1_TARGET_COL)
    ic_trip1 = compute_ic(panel, "v020_s060_c020", S1_TARGET_COL)
    ic_trip2 = compute_ic(panel, "v025_s070_c005", S1_TARGET_COL)
    ic_trip3 = compute_ic(panel, "v010_s090_c000", S1_TARGET_COL)
    ic_trip4 = compute_ic(panel, "v015_s070_c015", S1_TARGET_COL)

    y_s1 = compute_yearly_ic(panel, S1_SCORE_COL, S1_TARGET_COL)
    y_vol = compute_yearly_ic(panel, "vol_rank", S1_TARGET_COL)
    y_h410 = compute_yearly_ic(panel, "v025_s075_c000", S1_TARGET_COL)
    y_trip1 = compute_yearly_ic(panel, "v020_s060_c020", S1_TARGET_COL)

    pos_s1 = sum(1 for v in y_s1.values() if v > 0)
    pos_vol = sum(1 for v in y_vol.values() if v > 0)
    pos_h410 = sum(1 for v in y_h410.values() if v > 0)
    pos_trip1 = sum(1 for v in y_trip1.values() if v > 0)

    print(f"\n=== H413 Triple Signal Additive Results ===")
    print(f"S1 alone:          {ic_s1:+.5f} ({pos_s1}/{len(y_s1)} years)")
    print(f"Volume alone:     {ic_vol:+.5f} ({pos_vol}/{pos_vol} years)")
    print(f"C16 alone:        {ic_c16:+.5f}")
    print(f"H410 (V+S1):      {ic_h410:+.5f} ({pos_h410}/{len(y_h410)} years)")
    print(f"0.2V+0.6S1+0.2C16: {ic_trip1:+.5f} ({pos_trip1}/{len(y_trip1)} years)")
    print(f"0.25V+0.7S1+0.05C16: {ic_trip2:+.5f}")
    print(f"0.1V+0.9S1:       {ic_trip3:+.5f}")
    print(f"0.15V+0.7S1+0.15C16: {ic_trip4:+.5f}")

    combos = {
        "0.2V+0.6S1+0.2C16": ic_trip1,
        "0.25V+0.7S1+0.05C16": ic_trip2,
        "0.1V+0.9S1": ic_trip3,
        "0.15V+0.7S1+0.15C16": ic_trip4,
    }
    best_combo = max(combos, key=combos.get)
    best_ic = combos[best_combo]

    print(f"\n--- Best combo: {best_combo} = {best_ic:+.5f}")

    lift_vs_h410 = best_ic - ic_h410
    result = {
        "ic_s1": float(ic_s1),
        "ic_vol": float(ic_vol),
        "ic_c16": float(ic_c16),
        "ic_h410": float(ic_h410),
        "ic_trip1": float(ic_trip1),
        "ic_trip2": float(ic_trip2),
        "ic_trip3": float(ic_trip3),
        "ic_trip4": float(ic_trip4),
        "best_combo": best_combo,
        "best_ic": float(best_ic),
        "lift_vs_h410": float(lift_vs_h410),
        "pos_s1": pos_s1,
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
            "panel_cache_source": panel_result.source,
            "panel_rows": int(len(panel)),
            "panel_start": panel["time"].min().date().isoformat() if len(panel) else None,
            "panel_end": panel["time"].max().date().isoformat() if len(panel) else None,
        },
    )

    # Preserve the legacy branch pointer while the H410-H425 family migrates.
    legacy_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    atomic_write_json(result, legacy_path)

    print(f"\nSaved: {summary_path}")
    print(f"Legacy summary: {legacy_path}")
    print(f"Lift vs H410 baseline: {lift_vs_h410:+.5f}")

    print(f"\n=== VERDICT ===")
    if best_ic > ic_h410 + 0.005:
        print("PASSED - triple beats H410")
    elif best_ic > ic_h410:
        print("MIXED - triple beats H410 marginally")
    elif best_ic > ic_s1:
        print("MIXED - triple beats S1 alone")
    else:
        print("FAILED - H410 remains best")

    return best_ic


if __name__ == "__main__":
    main()
