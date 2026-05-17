"""
H519: carry_axis_refinement

Follow-through after H518 diagnostic:
- keep H512 discipline (C24-preserving global representation k=4)
- keep H515 active-k=5 (from guarded contract in H517)
- add carry-focused observable features to improve carry-state overlap
  without degrading quiet/C24/amplified gates and lift-gap robustness
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


BRANCH_NAME = "carry_axis_refinement"
MODE = "research_branch"
DEV_YEARS = tuple(range(2015, 2023))
ACTIVE_K_SWEEP = (3, 4, 5, 6)

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Adding carry-focused temporal/flow continuity features to the active-manifold "
        "emissions should improve carry-state separation while preserving H512/H515 "
        "quiet/C24/amplified gates and active-vs-random lift gap."
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

CARRY_FEATURES = [
    "flow_persist_2d",
    "flow_persist_3d",
    "imbalance_persist_2d",
    "imbalance_persist_3d",
    "order_pressure_sustain",
    "vol_flow_ratio",
    "carry_candidate_flag",
    "lag2_order_volume_ratio_rank",
    "lag2_buy_sell_imbalance_norm",
    "flow_accel_2d",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H519 carry-axis refinement")
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
    parser.add_argument("--random-seed", type=int, default=519)
    parser.add_argument("--force-global-k", type=int, choices=[4], default=4)
    parser.add_argument("--force-active-k", type=int, choices=[3, 4, 5, 6], default=5)
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

    panel["flow_abs"] = panel["buy_sell_imbalance_norm"].abs()
    panel["count_skew_abs"] = (panel["buy_count_share"] - panel["sell_count_share"]).abs()
    panel["ceiling_persist_2d"] = panel["at_ceiling"].fillna(0.0) + panel["lag_at_ceiling"].fillna(0.0)
    panel["delta_at_ceiling"] = panel["at_ceiling"].fillna(0.0) - panel["lag_at_ceiling"].fillna(0.0)
    panel["vol_flow_abs"] = panel["vol_expansion_flag"] * panel["flow_abs"]
    panel["vol_count_skew_abs"] = panel["vol_expansion_flag"] * panel["count_skew_abs"]
    panel["vol_non_ceiling"] = panel["vol_expansion_flag"] * (1.0 - panel["at_ceiling"].fillna(0.0))
    panel["vol_ceiling"] = panel["vol_expansion_flag"] * panel["at_ceiling"].fillna(0.0)

    panel["lag2_order_volume_ratio_rank"] = panel.groupby("ticker")["order_volume_ratio_rank"].shift(2)
    panel["lag2_buy_sell_imbalance_norm"] = panel.groupby("ticker")["buy_sell_imbalance_norm"].shift(2)
    panel["lag_flow_abs"] = panel.groupby("ticker")["flow_abs"].shift(1)

    panel["flow_persist_2d"] = panel["flow_abs"].fillna(0.0) + panel["lag_flow_abs"].fillna(0.0)
    panel["flow_persist_3d"] = (
        panel["flow_abs"].fillna(0.0) + panel["lag_flow_abs"].fillna(0.0) + panel.get("lag2_flow_abs", panel["flow_abs"].fillna(0.0)).fillna(0.0)
    )
    panel["imbalance_persist_2d"] = panel["buy_sell_imbalance_norm"].fillna(0.0) + panel["lag_buy_sell_imbalance_norm"].fillna(0.0)
    panel["imbalance_persist_3d"] = (
        panel["buy_sell_imbalance_norm"].fillna(0.0)
        + panel["lag_buy_sell_imbalance_norm"].fillna(0.0)
        + panel.get("lag2_buy_sell_imbalance_norm", panel["buy_sell_imbalance_norm"].fillna(0.0)).fillna(0.0)
    )
    panel["order_pressure_sustain"] = (
        panel["order_volume_ratio_rank"].fillna(0.5) + panel["lag_order_volume_ratio_rank"].fillna(0.5)
    ) / 2.0
    panel["vol_flow_ratio"] = panel["vol_change"].fillna(0.0) / (panel["flow_abs"].fillna(0.001) + 0.001)
    panel["carry_candidate_flag"] = (
        (panel["flow_abs"] < panel["flow_abs"].quantile(0.4))
        & (panel["order_volume_ratio_rank"] > panel["order_volume_ratio_rank"].quantile(0.6))
    ).astype(float)
    panel["flow_accel_2d"] = panel["delta_buy_sell_imbalance_norm"].fillna(0.0) - (
        panel["lag_buy_sell_imbalance_norm"].fillna(0.0) - panel["lag2_buy_sell_imbalance_norm"].fillna(0.0)
    )

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
        *CARRY_FEATURES,
    ]
    miss = [c for c in required if c not in panel.columns]
    if miss:
        raise ValueError(f"H519 panel missing required columns: {miss}")

    with open(args.baseline_summary_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)["summary"]

    years = pd.to_datetime(panel["time"], errors="coerce").dt.year
    dev_mask = years.isin(DEV_YEARS)

    gk = int(args.force_global_k)
    panel["h519_global_cluster_id"] = panel[f"k{gk}_cluster_id"].astype(int)
    for i in range(gk):
        panel[f"h519_k{gk}_cluster_{i}"] = (panel["h519_global_cluster_id"] == i).astype(int)
    quiet_overlap = build_overlap(
        panel,
        [f"h519_k{gk}_cluster_{i}" for i in range(gk)],
        ["state_quiet", "c24"],
    )
    quiet_best = quiet_overlap[quiet_overlap["symbolic_col"] == "state_quiet"].sort_values(
        "contain_cluster_in_symbolic", ascending=False
    ).iloc[0]
    c24_best = quiet_overlap[quiet_overlap["symbolic_col"] == "c24"].sort_values(
        "contain_symbolic_in_cluster", ascending=False
    ).iloc[0]
    quiet_cluster_id = int(str(quiet_best["cluster_col"]).split("_")[-1])
    panel["h519_is_active"] = (panel["h519_global_cluster_id"] != quiet_cluster_id).astype(int)
    active = panel[panel["h519_is_active"] == 1].copy().reset_index(drop=True)
    active_years = pd.to_datetime(active["time"], errors="coerce").dt.year
    active_dev_mask = active_years.isin(DEV_YEARS)

    base_feature_cols = [*BASE_FEATURES]
    carry_feature_cols = [*BASE_FEATURES, *CARRY_FEATURES]

    rows: list[dict[str, object]] = []
    overlap_parts: list[pd.DataFrame] = []
    results_parts: list[pd.DataFrame] = []
    random_parts: list[pd.DataFrame] = []
    yearly_parts: list[pd.DataFrame] = []
    labeled: dict[int, pd.DataFrame] = {}

    for ak in ACTIVE_K_SWEEP:
        run = active.copy()

        if int(ak) == int(args.force_active_k):
            feature_cols = carry_feature_cols
        else:
            feature_cols = base_feature_cols

        labels = fit_clusters(run, feature_cols=feature_cols, k=int(ak), dev_mask=active_dev_mask, seed=int(args.random_seed))
        run["h519_active_cluster_id"] = labels
        sil = _safe_silhouette(
            run.loc[active_dev_mask, feature_cols].to_numpy(),
            labels[active_dev_mask.values],
            sample_size=int(args.silhouette_sample),
            seed=int(args.random_seed) + int(ak),
        )
        state_specs = [StateSpec("all_rows", "All active rows", family="active_baseline", primary=True)]
        cluster_cols = []
        for cid in range(int(ak)):
            ccol = f"h519_active_k{ak}_cluster_{cid}"
            run[ccol] = (run["h519_active_cluster_id"] == cid).astype(int)
            cluster_cols.append(ccol)
            state_specs.append(StateSpec(ccol, f"Active cluster {cid} (k={ak})", family="active_latent", primary=True))
        validate_state_columns(run, [s.name for s in state_specs], spec)
        res, yr = evaluate_state_specs(run, state_specs, score_col=S1_SCORE_COL, target_col=S1_TARGET_COL, spec=spec)
        res["active_k"] = int(ak)
        yr["active_k"] = int(ak)
        results_parts.append(res)
        yearly_parts.append(yr)

        rng = np.random.default_rng(int(args.random_seed) + int(ak) + 3000)
        rnd = rng.integers(0, int(ak), size=len(run))
        rspec = [StateSpec("all_rows", "All active rows", family="active_baseline", primary=True)]
        for cid in range(int(ak)):
            rcol = f"h519_random_k{ak}_cluster_{cid}"
            run[rcol] = (rnd == cid).astype(int)
            rspec.append(StateSpec(rcol, f"Random cluster {cid} (k={ak})", family="active_random", primary=True))
        rres, _ = evaluate_state_specs(run, rspec, score_col=S1_SCORE_COL, target_col=S1_TARGET_COL, spec=spec)
        rres["active_k"] = int(ak)
        random_parts.append(rres)

        ov = build_overlap(run, cluster_cols, ["c23_fresh_not_yesterday", "cofire_2", "c23_yesterday_carry", "c24"])
        ov["active_k"] = int(ak)
        overlap_parts.append(ov)

        base_ic = float(res.loc[res["name"] == "all_rows", "avg_ic"].iloc[0])
        best_ic = float(res.loc[res["family"] == "active_latent", "avg_ic"].max())
        rand_best = float(rres.loc[rres["family"] == "active_random", "avg_ic"].max())
        focus = ov[ov["symbolic_col"].isin(["c23_fresh_not_yesterday", "cofire_2", "c23_yesterday_carry"])]
        mx = focus.groupby("symbolic_col")["jaccard"].max().to_dict()
        rows.append(
            {
                "active_k": int(ak),
                "silhouette_dev": sil,
                "active_base_ic": base_ic,
                "best_cluster_ic": best_ic,
                "active_lift_minus_random_lift": (best_ic - base_ic) - (rand_best - base_ic),
                "max_jaccard_onset": float(mx.get("c23_fresh_not_yesterday", np.nan)),
                "max_jaccard_amplified": float(mx.get("cofire_2", np.nan)),
                "max_jaccard_carry": float(mx.get("c23_yesterday_carry", np.nan)),
                "mean_disentangle_jaccard": float(np.nanmean(list(mx.values()))) if mx else np.nan,
                "strong_non_sparse_clusters": int(
                    (
                        (res["family"] == "active_latent")
                        & (res["avg_ic"] > base_ic)
                        & (res["pooled_rows"] >= 5000)
                        & (res["years"] >= 8)
                    ).sum()
                ),
            }
        )
        labeled[int(ak)] = run

    diag = pd.DataFrame(rows).sort_values(["silhouette_dev", "active_k"], ascending=[False, True])

    forced = diag.loc[diag["active_k"] == int(args.force_active_k)]
    if forced.empty:
        raise ValueError(f"Requested force-active-k={args.force_active_k} not found.")
    best = forced.iloc[0]
    best_ak = int(best["active_k"])

    quiet_preserved = float(quiet_best["contain_cluster_in_symbolic"]) >= 0.95
    c24_preserved = float(c24_best["contain_symbolic_in_cluster"]) >= 0.80
    beats_random = float(best["active_lift_minus_random_lift"]) >= 0.01
    non_sparse = int(best["strong_non_sparse_clusters"]) >= 2
    disentangle = float(best["mean_disentangle_jaccard"]) >= 0.10
    carry_improves = float(best["max_jaccard_carry"]) > float(baseline.get("carry_jaccard", 0.090010))
    amplified_preserved = float(best["max_jaccard_amplified"]) >= float(baseline.get("amplified_jaccard", 0.151146)) * 0.95

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
        decision = "SUPPORTS carry-axis refinement"
    elif score >= 5:
        decision = "MIXED"
    else:
        decision = "DOES NOT SUPPORT carry-axis refinement"

    overlap_all = pd.concat(overlap_parts, ignore_index=True)
    results_all = pd.concat(results_parts, ignore_index=True)
    random_all = pd.concat(random_parts, ignore_index=True)
    yearly_all = pd.concat(yearly_parts, ignore_index=True)

    diag_path = write_dataframe_artifact(diag, context, f"{BRANCH_NAME}_active_k_discipline")
    overlap_path = write_dataframe_artifact(overlap_all, context, f"{BRANCH_NAME}_active_overlap")
    results_path = write_dataframe_artifact(results_all, context, f"{BRANCH_NAME}_active_results")
    random_path = write_dataframe_artifact(random_all, context, f"{BRANCH_NAME}_active_random_baseline")
    yearly_path = write_dataframe_artifact(yearly_all, context, f"{BRANCH_NAME}_active_yearly")
    global_overlap_path = write_dataframe_artifact(quiet_overlap, context, f"{BRANCH_NAME}_global_overlap")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "selected_global_k": int(gk),
            "selected_active_k": int(best_ak),
            "active_rows": int(len(active)),
            "quiet_cluster_in_quiet": float(quiet_best["contain_cluster_in_symbolic"]),
            "c24_symbolic_in_cluster": float(c24_best["contain_symbolic_in_cluster"]),
            "active_lift_minus_random_lift": float(best["active_lift_minus_random_lift"]),
            "max_jaccard_onset": float(best["max_jaccard_onset"]),
            "max_jaccard_amplified": float(best["max_jaccard_amplified"]),
            "max_jaccard_carry": float(best["max_jaccard_carry"]),
            "mean_disentangle_jaccard": float(best["mean_disentangle_jaccard"]),
            "strong_non_sparse_clusters": int(best["strong_non_sparse_clusters"]),
            "h518_baseline_carry_jaccard": float(baseline.get("carry_jaccard", 0.090010)),
            "h518_baseline_amplified_jaccard": float(baseline.get("amplified_jaccard", 0.151146)),
            "flag_quiet_recovery_preserved": bool(flags["quiet_recovery_preserved"]),
            "flag_c24_recovery_preserved": bool(flags["c24_recovery_preserved"]),
            "flag_active_beats_random": bool(flags["active_beats_random"]),
            "flag_active_non_sparse_strength": bool(flags["active_non_sparse_strength"]),
            "flag_nontrivial_disentangling": bool(flags["nontrivial_disentangling"]),
            "flag_carry_axis_improved_vs_h518": bool(flags["carry_axis_improved_vs_h518"]),
            "flag_amplified_axis_preserved": bool(flags["amplified_axis_preserved"]),
        },
        artifacts={
            "active_k_discipline": diag_path,
            "active_overlap": overlap_path,
            "active_results": results_path,
            "active_random_baseline": random_path,
            "active_yearly": yearly_path,
            "global_overlap": global_overlap_path,
            "source_baseline_summary": args.baseline_summary_path,
        },
        metadata={
            "base_feature_columns": BASE_FEATURES,
            "carry_feature_columns": CARRY_FEATURES,
            "selection_note": "Global k fixed at 4 (C24-preserving), active k forced to 5 (guarded contract), carry features added for k=5 only.",
        },
    )

    print(diag.to_string(index=False))
    print(f"quiet_best: {quiet_best.to_dict()}")
    print(f"c24_best: {c24_best.to_dict()}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()