"""
H521: balanced_carry_amplified_search

Follow-through after H519 MIXED result:
- H519 improved carry (+62%) but degraded amplified (-80%)
- Goal: find minimal carry feature set that improves carry WITHOUT degrading amplified
- Strategy: test weak carry features only (simple lags, no flow_persist)
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    StateSpec,
    build_experiment_context,
    evaluate_state_specs,
    restrict_years,
    validate_state_columns,
    write_dataframe_artifact,
)


BRANCH_NAME = "balanced_carry_amplified_search"
MODE = "research_branch"
DEV_YEARS = tuple(range(2015, 2023))
ACTIVE_K = 5

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Testing minimal carry features (simple lags, no flow_persist/imbalance_persist) "
        "should improve carry separation while preserving amplified state."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


BASE_FEATURES = [
    "amihud_log",
    "vol_change",
    "vol_expansion_flag",
    "order_volume_ratio_log",
    "order_volume_ratio_rank",
    "buy_sell_imbalance_norm",
    "buy_count_share",
    "sell_count_share",
    "at_ceiling",
    "ceiling_3d_count",
    "lag_vol_expansion",
    "lag_order_volume_ratio_rank",
    "lag_at_ceiling",
    "lag_buy_sell_imbalance_norm",
    "delta_order_volume_ratio_rank",
    "delta_buy_sell_imbalance_norm",
]

WEAK_CARRY_FEATURES = [
    "lag2_order_volume_ratio_rank",
    "lag2_buy_sell_imbalance_norm",
    "order_pressure_sustain",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H521 balanced carry-amplified search")
    parser.add_argument(
        "--h509-panel-path",
        type=str,
        default=str(
            ROOT
            / "artifacts"
            / "research_branches"
            / "20260510_144827_latent_state_discovery_clustered_panel.parquet"
        ),
    )
    parser.add_argument(
        "--baseline-summary-path",
        type=str,
        default=str(
            ROOT
            / "artifacts"
            / "run_summaries"
            / "20260517_134504_carry_axis_bottleneck_audit_research_branch.json"
        ),
    )
    parser.add_argument("--silhouette-sample", type=int, default=4000)
    parser.add_argument("--random-seed", type=int, default=521)
    parser.add_argument("--force-global-k", type=int, choices=[4], default=4)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = pd.read_parquet(args.h509_panel_path)
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    panel["ticker"] = panel["ticker"].astype(str).str.upper()
    panel = restrict_years(
        panel,
        start_year=int(spec.start_year),
        end_year=int(spec.end_year),
        source="H509 clustered panel",
    )
    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    panel["delta_order_volume_ratio_rank"] = panel["order_volume_ratio_rank"] - panel["lag_order_volume_ratio_rank"]
    panel["delta_buy_sell_imbalance_norm"] = panel["buy_sell_imbalance_norm"] - panel["lag_buy_sell_imbalance_norm"]

    panel["lag2_order_volume_ratio_rank"] = panel.groupby("ticker")["order_volume_ratio_rank"].shift(2)
    panel["lag2_buy_sell_imbalance_norm"] = panel.groupby("ticker")["buy_sell_imbalance_norm"].shift(2)
    panel["order_pressure_sustain"] = (
        panel["order_volume_ratio_rank"].fillna(0.5) + panel["lag_order_volume_ratio_rank"].fillna(0.5)
    ) / 2.0

    panel = panel.replace([np.inf, -np.inf], np.nan)
    panel = panel.dropna(subset=[S1_SCORE_COL, S1_TARGET_COL]).copy()
    return panel


def _safe_silhouette(x: np.ndarray, labels: np.ndarray, *, sample_size: int, seed: int) -> float:
    finite = np.isfinite(x).all(axis=1)
    if int(finite.sum()) < 2000:
        return np.nan
    x = x[finite]
    labels = labels[finite]
    if len(np.unique(labels)) < 2:
        return np.nan
    n = len(x)
    if n > int(sample_size):
        rng = np.random.default_rng(seed)
        idx = rng.choice(n, size=int(sample_size), replace=False)
        x = x[idx]
        labels = labels[idx]
    if len(np.unique(labels)) < 2:
        return np.nan
    return float(silhouette_score(x, labels, metric="euclidean"))


def _jaccard(a: pd.Series, b: pd.Series) -> float:
    aa = a.fillna(False).astype(bool)
    bb = b.fillna(False).astype(bool)
    inter = int((aa & bb).sum())
    union = int((aa | bb).sum())
    if union == 0:
        return np.nan
    return float(inter / union)


def _containment(a: pd.Series, b: pd.Series) -> float:
    aa = a.fillna(False).astype(bool)
    bb = b.fillna(False).astype(bool)
    denom = int(aa.sum())
    if denom == 0:
        return np.nan
    return float(((aa & bb).sum()) / denom)


def build_overlap(frame: pd.DataFrame, cluster_cols: list[str], symbolic_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ccol in cluster_cols:
        cm = frame[ccol]
        for scol in symbolic_cols:
            sm = frame[scol]
            rows.append(
                {
                    "cluster_col": ccol,
                    "symbolic_col": scol,
                    "jaccard": _jaccard(cm, sm),
                    "contain_cluster_in_symbolic": _containment(cm, sm),
                    "contain_symbolic_in_cluster": _containment(sm, cm),
                }
            )
    return pd.DataFrame(rows)


def fit_clusters(
    frame: pd.DataFrame,
    *,
    feature_cols: list[str],
    k: int,
    dev_mask: pd.Series,
    seed: int,
) -> np.ndarray:
    x_raw = frame[feature_cols].replace([np.inf, -np.inf], np.nan)
    imp = SimpleImputer(strategy="median")
    x_dev = imp.fit_transform(x_raw.loc[dev_mask])
    scl = StandardScaler()
    x_dev = scl.fit_transform(x_dev)
    model = MiniBatchKMeans(
        n_clusters=int(k),
        random_state=int(seed) + int(k),
        n_init=20,
        batch_size=65536,
        max_iter=300,
        reassignment_ratio=0.01,
    )
    model.fit(x_dev)
    x_all = scl.transform(imp.transform(x_raw))
    return model.predict(x_all).astype(int)


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(SPEC)
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)

    required = [
        "state_quiet",
        "c24",
        "c23_fresh_not_yesterday",
        "cofire_2",
        "c23_yesterday_carry",
        "k4_cluster_id",
        *BASE_FEATURES,
        *WEAK_CARRY_FEATURES,
    ]
    miss = [c for c in required if c not in panel.columns]
    if miss:
        raise ValueError(f"H521 panel missing required columns: {miss}")

    with open(args.baseline_summary_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)["summary"]

    years = pd.to_datetime(panel["time"], errors="coerce").dt.year
    dev_mask = years.isin(DEV_YEARS)

    gk = int(args.force_global_k)
    panel["h521_global_cluster_id"] = panel[f"k{gk}_cluster_id"].astype(int)
    for i in range(gk):
        panel[f"h521_k{gk}_cluster_{i}"] = (panel["h521_global_cluster_id"] == i).astype(int)
    quiet_overlap = build_overlap(
        panel,
        [f"h521_k{gk}_cluster_{i}" for i in range(gk)],
        ["state_quiet", "c24"],
    )
    quiet_best = quiet_overlap[quiet_overlap["symbolic_col"] == "state_quiet"].sort_values(
        "contain_cluster_in_symbolic", ascending=False
    ).iloc[0]
    c24_best = quiet_overlap[quiet_overlap["symbolic_col"] == "c24"].sort_values(
        "contain_symbolic_in_cluster", ascending=False
    ).iloc[0]
    quiet_cluster_id = int(str(quiet_best["cluster_col"]).split("_")[-1])
    panel["h521_is_active"] = (panel["h521_global_cluster_id"] != quiet_cluster_id).astype(int)
    active = panel[panel["h521_is_active"] == 1].copy().reset_index(drop=True)
    active_years = pd.to_datetime(active["time"], errors="coerce").dt.year
    active_dev_mask = active_years.isin(DEV_YEARS)

    base_feature_cols = [*BASE_FEATURES]
    weak_carry_feature_cols = [*BASE_FEATURES, *WEAK_CARRY_FEATURES]

    runs = {}
    for name, feat_cols in [("base", base_feature_cols), ("weak_carry", weak_carry_feature_cols)]:
        run = active.copy()
        labels = fit_clusters(run, feature_cols=feat_cols, k=ACTIVE_K, dev_mask=active_dev_mask, seed=int(args.random_seed))
        run["h521_active_cluster_id"] = labels
        sil = _safe_silhouette(
            run.loc[active_dev_mask, feat_cols].to_numpy(),
            labels[active_dev_mask.values],
            sample_size=int(args.silhouette_sample),
            seed=int(args.random_seed),
        )
        state_specs = [StateSpec("all_rows", "All active rows", family="active_baseline", primary=True)]
        cluster_cols = []
        for cid in range(ACTIVE_K):
            ccol = f"h521_{name}_cluster_{cid}"
            run[ccol] = (run["h521_active_cluster_id"] == cid).astype(int)
            cluster_cols.append(ccol)
            state_specs.append(StateSpec(ccol, f"Active cluster {cid} ({name})", family="active_latent", primary=True))
        validate_state_columns(run, [s.name for s in state_specs], spec)
        res, yr = evaluate_state_specs(run, state_specs, score_col=S1_SCORE_COL, target_col=S1_TARGET_COL, spec=spec)

        ov = build_overlap(run, cluster_cols, ["c23_fresh_not_yesterday", "cofire_2", "c23_yesterday_carry", "c24"])

        base_ic = float(res.loc[res["name"] == "all_rows", "avg_ic"].iloc[0])
        best_ic = float(res.loc[res["family"] == "active_latent", "avg_ic"].max())
        focus = ov[ov["symbolic_col"].isin(["c23_fresh_not_yesterday", "cofire_2", "c23_yesterday_carry"])]
        mx = focus.groupby("symbolic_col")["jaccard"].max().to_dict()

        runs[name] = {
            "run": run,
            "silhouette": sil,
            "results": res,
            "overlap": ov,
            "base_ic": base_ic,
            "best_ic": best_ic,
            "jaccards": mx,
            "strong_clusters": int(
                (
                    (res["family"] == "active_latent")
                    & (res["avg_ic"] > base_ic)
                    & (res["pooled_rows"] >= 5000)
                    & (res["years"] >= 8)
                ).sum()
            ),
        }

    base = runs["base"]
    weak = runs["weak_carry"]

    quiet_preserved = float(quiet_best["contain_cluster_in_symbolic"]) >= 0.95
    c24_preserved = float(c24_best["contain_symbolic_in_cluster"]) >= 0.80
    beats_random = float(weak["best_ic"] - weak["base_ic"]) >= 0.01
    non_sparse = int(weak["strong_clusters"]) >= 2
    disentangle = float(np.nanmean(list(weak["jaccards"].values()))) >= 0.10
    carry_improves = float(weak["jaccards"].get("c23_yesterday_carry", 0)) > float(baseline.get("carry_jaccard", 0.090010))
    amplified_preserved = float(weak["jaccards"].get("cofire_2", 0)) >= float(baseline.get("amplified_jaccard", 0.151146)) * 0.90

    flags = {
        "quiet_recovery_preserved": bool(quiet_preserved),
        "c24_recovery_preserved": bool(c24_preserved),
        "active_beats_random": bool(beats_random),
        "active_non_sparse_strength": bool(non_sparse),
        "nontrivial_disentangling": bool(disentangle),
        "carry_axis_improved_vs_h518": bool(carry_improves),
        "amplified_axis_preserved": bool(amplified_preserved),
    }
    score = sum(int(v) for v in flags.values())
    if score >= 7:
        decision = "SUPPORTS balanced carry-amplified approach"
    elif score >= 5:
        decision = "MIXED"
    else:
        decision = "DOES NOT SUPPORT balanced approach"

    results_all = pd.concat([base["results"], weak["results"]], ignore_index=True)
    overlap_all = pd.concat([base["overlap"], weak["overlap"]], ignore_index=True)

    diag_path = write_dataframe_artifact(
        pd.DataFrame([
            {
                "run": "base",
                "silhouette": base["silhouette"],
                "onset_jaccard": base["jaccards"].get("c23_fresh_not_yesterday", np.nan),
                "amplified_jaccard": base["jaccards"].get("cofire_2", np.nan),
                "carry_jaccard": base["jaccards"].get("c23_yesterday_carry", np.nan),
            },
            {
                "run": "weak_carry",
                "silhouette": weak["silhouette"],
                "onset_jaccard": weak["jaccards"].get("c23_fresh_not_yesterday", np.nan),
                "amplified_jaccard": weak["jaccards"].get("cofire_2", np.nan),
                "carry_jaccard": weak["jaccards"].get("c23_yesterday_carry", np.nan),
            },
        ]),
        context,
        f"{BRANCH_NAME}_comparison",
    )
    results_path = write_dataframe_artifact(results_all, context, f"{BRANCH_NAME}_results")
    overlap_path = write_dataframe_artifact(overlap_all, context, f"{BRANCH_NAME}_overlap")
    global_overlap_path = write_dataframe_artifact(quiet_overlap, context, f"{BRANCH_NAME}_global_overlap")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "selected_global_k": int(gk),
            "selected_active_k": ACTIVE_K,
            "active_rows": int(len(active)),
            "quiet_cluster_in_quiet": float(quiet_best["contain_cluster_in_symbolic"]),
            "c24_symbolic_in_cluster": float(c24_best["contain_symbolic_in_cluster"]),
            "base_carry_jaccard": float(base["jaccards"].get("c23_yesterday_carry", np.nan)),
            "weak_carry_jaccard": float(weak["jaccards"].get("c23_yesterday_carry", np.nan)),
            "base_amplified_jaccard": float(base["jaccards"].get("cofire_2", np.nan)),
            "weak_carry_amplified_jaccard": float(weak["jaccards"].get("cofire_2", np.nan)),
            "h518_baseline_carry_jaccard": float(baseline.get("carry_jaccard", 0.090010)),
            "h518_baseline_amplified_jaccard": float(baseline.get("amplified_jaccard", 0.151146)),
            "strong_non_sparse_clusters": int(weak["strong_clusters"]),
            "flag_quiet_recovery_preserved": bool(flags["quiet_recovery_preserved"]),
            "flag_c24_recovery_preserved": bool(flags["c24_recovery_preserved"]),
            "flag_active_beats_random": bool(flags["active_beats_random"]),
            "flag_active_non_sparse_strength": bool(flags["active_non_sparse_strength"]),
            "flag_nontrivial_disentangling": bool(flags["nontrivial_disentangling"]),
            "flag_carry_axis_improved_vs_h518": bool(flags["carry_axis_improved_vs_h518"]),
            "flag_amplified_axis_preserved": bool(flags["amplified_axis_preserved"]),
        },
        artifacts={
            "comparison": diag_path,
            "results": results_path,
            "overlap": overlap_path,
            "global_overlap": global_overlap_path,
            "source_baseline_summary": args.baseline_summary_path,
        },
        metadata={
            "base_feature_columns": BASE_FEATURES,
            "weak_carry_feature_columns": WEAK_CARRY_FEATURES,
            "selection_note": "Global k fixed at 4 (C24-preserving), active k=5. Comparing base vs weak_carry features.",
        },
    )

    print(f"Base: carry={base['jaccards'].get('c23_yesterday_carry')}, amplified={base['jaccards'].get('cofire_2')}")
    print(f"Weak: carry={weak['jaccards'].get('c23_yesterday_carry')}, amplified={weak['jaccards'].get('cofire_2')}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()