"""
H511: active_manifold_disentangling

Narrow follow-through on H509.

Goal:
- enforce dev-only k-choice discipline
- preserve quiet/C24 structural recovery
- test whether active-manifold subclustering can better separate
  onset/amplification/carry emissions without symbolic labels in clustering
"""

from __future__ import annotations

import argparse
from dataclasses import replace
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


BRANCH_NAME = "active_manifold_disentangling"
MODE = "research_branch"
GLOBAL_K_SWEEP = (4, 5, 6)
ACTIVE_K_SWEEP = (3, 4, 5)
DEV_YEARS = tuple(range(2015, 2023))

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "With dev-only k selection and active-only unsupervised subclustering, "
        "the H509 active manifold can be partially disentangled while preserving "
        "quiet/C24 structural recovery and beating random active partitions."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


FEATURE_COLS = [
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H511 active-manifold disentangling")
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
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--random-seed", type=int, default=511)
    parser.add_argument("--silhouette-sample", type=int, default=60000)
    parser.add_argument("--force-global-k", type=int, choices=[4, 5, 6], default=None)
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
    panel["delta_order_volume_ratio_rank"] = (
        panel["order_volume_ratio_rank"] - panel["lag_order_volume_ratio_rank"]
    )
    panel["delta_buy_sell_imbalance_norm"] = (
        panel["buy_sell_imbalance_norm"] - panel["lag_buy_sell_imbalance_norm"]
    )
    panel = panel.replace([np.inf, -np.inf], np.nan)
    panel = panel.dropna(subset=[S1_SCORE_COL, S1_TARGET_COL]).copy()
    return panel


def _safe_silhouette(
    x_dev: np.ndarray,
    labels: np.ndarray,
    *,
    sample_size: int,
    seed: int,
) -> float:
    if len(x_dev) < 2000:
        return np.nan
    finite_mask = np.isfinite(x_dev).all(axis=1)
    if finite_mask.sum() < 2000:
        return np.nan
    x_clean = x_dev[finite_mask]
    y_clean = labels[finite_mask]
    unique_labels = np.unique(y_clean)
    if len(unique_labels) < 2:
        return np.nan
    n = len(x_clean)
    if n > sample_size:
        rng = np.random.default_rng(seed)
        idx = rng.choice(n, size=sample_size, replace=False)
        x_use = x_clean[idx]
        y_use = y_clean[idx]
    else:
        x_use = x_clean
        y_use = y_clean
    if len(np.unique(y_use)) < 2:
        return np.nan
    return float(silhouette_score(x_use, y_use, metric="euclidean"))


def _cluster_mask(frame: pd.DataFrame, col: str) -> pd.Series:
    return frame[col].fillna(False).astype(bool)


def _jaccard(mask_a: pd.Series, mask_b: pd.Series) -> float:
    a = mask_a.astype(bool)
    b = mask_b.astype(bool)
    inter = int((a & b).sum())
    union = int((a | b).sum())
    if union == 0:
        return np.nan
    return float(inter / union)


def _containment(mask_a: pd.Series, mask_b: pd.Series) -> float:
    a = mask_a.astype(bool)
    b = mask_b.astype(bool)
    denom = int(a.sum())
    if denom == 0:
        return np.nan
    return float(((a & b).sum()) / denom)


def build_overlap_table(
    frame: pd.DataFrame,
    *,
    cluster_cols: list[str],
    symbolic_cols: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ccol in cluster_cols:
        cmask = _cluster_mask(frame, ccol)
        for scol in symbolic_cols:
            smask = _cluster_mask(frame, scol)
            rows.append(
                {
                    "cluster_col": ccol,
                    "symbolic_col": scol,
                    "jaccard": _jaccard(cmask, smask),
                    "contain_cluster_in_symbolic": _containment(cmask, smask),
                    "contain_symbolic_in_cluster": _containment(smask, cmask),
                    "cluster_share": float(cmask.mean()),
                    "symbolic_share": float(smask.mean()),
                }
            )
    return pd.DataFrame(rows)


def build_transition_table(frame: pd.DataFrame, *, label_col: str) -> pd.DataFrame:
    tmp = frame[["ticker", "time", label_col]].copy().sort_values(["ticker", "time"])
    tmp["prev_state"] = tmp.groupby("ticker")[label_col].shift(1)
    tmp = tmp.dropna(subset=["prev_state"])
    tmp["state"] = tmp[label_col].astype(int)
    tmp["prev_state"] = tmp["prev_state"].astype(int)
    out = tmp.groupby(["prev_state", "state"]).size().reset_index(name="count")
    out["prob_from_prev"] = out["count"] / out.groupby("prev_state")["count"].transform("sum")
    out["prob_global"] = out["count"] / out["count"].sum()
    return out.sort_values(["prev_state", "state"]).reset_index(drop=True)


def _fit_kmeans_with_dev_only(
    frame: pd.DataFrame,
    *,
    feature_cols: list[str],
    k: int,
    dev_mask: pd.Series,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    x_raw = frame[feature_cols].replace([np.inf, -np.inf], np.nan)
    imputer = SimpleImputer(strategy="median")
    x_dev_imp = imputer.fit_transform(x_raw.loc[dev_mask])
    scaler = StandardScaler()
    x_dev = scaler.fit_transform(x_dev_imp)

    model = MiniBatchKMeans(
        n_clusters=int(k),
        random_state=int(seed) + int(k),
        n_init=20,
        batch_size=65536,
        max_iter=300,
        reassignment_ratio=0.01,
    )
    model.fit(x_dev)

    x_all = scaler.transform(imputer.transform(x_raw))
    labels_all = model.predict(x_all).astype(int)
    labels_dev = labels_all[dev_mask.values]
    return labels_all, labels_dev, float(model.inertia_)


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)

    required_cols = [
        "state_quiet",
        "c24",
        "c23_fresh_not_yesterday",
        "cofire_2",
        "c23_yesterday_carry",
        *FEATURE_COLS,
    ] + [f"k{k}_cluster_id" for k in GLOBAL_K_SWEEP]
    missing = [col for col in required_cols if col not in panel.columns]
    if missing:
        raise ValueError(f"H511 panel missing required columns: {missing}")

    years = pd.to_datetime(panel["time"], errors="coerce").dt.year
    dev_mask = years.isin(DEV_YEARS)
    if int(dev_mask.sum()) < 10000:
        raise ValueError("Too few dev rows for stable clustering diagnostics.")

    global_rows: list[dict[str, object]] = []
    global_overlap_parts: list[pd.DataFrame] = []
    for k in GLOBAL_K_SWEEP:
        label_col = f"k{k}_cluster_id"
        labels = panel[label_col].astype(int).to_numpy()
        sil = _safe_silhouette(
            panel.loc[dev_mask, FEATURE_COLS].to_numpy(),
            labels[dev_mask.values],
            sample_size=int(args.silhouette_sample),
            seed=int(args.random_seed) + int(k),
        )

        cluster_cols = []
        for cid in range(int(k)):
            ccol = f"h511_k{k}_cluster_{cid}"
            panel[ccol] = (panel[label_col] == cid).astype(int)
            cluster_cols.append(ccol)

        overlap = build_overlap_table(
            panel,
            cluster_cols=cluster_cols,
            symbolic_cols=["state_quiet", "c24"],
        )
        overlap["k"] = int(k)
        global_overlap_parts.append(overlap)

        quiet_subset = overlap.loc[overlap["symbolic_col"] == "state_quiet"].copy()
        c24_subset = overlap.loc[overlap["symbolic_col"] == "c24"].copy()
        quiet_best = quiet_subset.sort_values("contain_cluster_in_symbolic", ascending=False).iloc[0]
        c24_best = c24_subset.sort_values("contain_symbolic_in_cluster", ascending=False).iloc[0]
        global_rows.append(
            {
                "k": int(k),
                "silhouette_dev": sil,
                "quiet_best_cluster_col": str(quiet_best["cluster_col"]),
                "quiet_cluster_in_quiet": float(quiet_best["contain_cluster_in_symbolic"]),
                "quiet_symbolic_in_cluster": float(quiet_best["contain_symbolic_in_cluster"]),
                "c24_best_cluster_col": str(c24_best["cluster_col"]),
                "c24_cluster_in_symbolic": float(c24_best["contain_cluster_in_symbolic"]),
                "c24_symbolic_in_cluster": float(c24_best["contain_symbolic_in_cluster"]),
            }
        )

    global_diag = pd.DataFrame(global_rows).sort_values(["silhouette_dev", "k"], ascending=[False, True])
    global_overlap = pd.concat(global_overlap_parts, ignore_index=True)
    if args.force_global_k is not None:
        forced = global_diag.loc[global_diag["k"] == int(args.force_global_k)]
        if forced.empty:
            raise ValueError(f"Requested force-global-k={args.force_global_k} not found in diagnostics.")
        best_global = forced.iloc[0]
    else:
        best_global = global_diag.iloc[0]
    best_global_k = int(best_global["k"])
    quiet_cluster_col = str(best_global["quiet_best_cluster_col"])
    quiet_cluster_id = int(quiet_cluster_col.split("_")[-1])
    selected_label_col = f"k{best_global_k}_cluster_id"

    panel["h511_global_cluster_id"] = panel[selected_label_col].astype(int)
    panel["h511_is_active"] = (panel["h511_global_cluster_id"] != quiet_cluster_id).astype(int)
    active = panel.loc[panel["h511_is_active"] == 1].copy().reset_index(drop=True)
    active_years = pd.to_datetime(active["time"], errors="coerce").dt.year
    active_dev_mask = active_years.isin(DEV_YEARS)
    if int(active_dev_mask.sum()) < 5000:
        raise ValueError("Too few active dev rows for subclustering.")

    active_k_rows: list[dict[str, object]] = []
    active_overlap_parts: list[pd.DataFrame] = []
    active_results_parts: list[pd.DataFrame] = []
    active_yearly_parts: list[pd.DataFrame] = []
    active_random_parts: list[pd.DataFrame] = []
    active_with_labels: dict[int, pd.DataFrame] = {}

    for subk in ACTIVE_K_SWEEP:
        labels_all, labels_dev, inertia = _fit_kmeans_with_dev_only(
            active,
            feature_cols=FEATURE_COLS,
            k=int(subk),
            dev_mask=active_dev_mask,
            seed=int(args.random_seed),
        )
        sil = _safe_silhouette(
            active.loc[active_dev_mask, FEATURE_COLS].to_numpy(),
            labels_dev,
            sample_size=int(args.silhouette_sample),
            seed=int(args.random_seed) + int(subk) + 1000,
        )

        run = active.copy()
        run["h511_active_cluster_id"] = labels_all.astype(int)
        state_specs = [StateSpec("all_rows", "All active rows", family="active_baseline", primary=True)]
        cluster_cols = []
        for cid in range(int(subk)):
            ccol = f"h511_active_k{subk}_cluster_{cid}"
            run[ccol] = (run["h511_active_cluster_id"] == cid).astype(int)
            cluster_cols.append(ccol)
            state_specs.append(
                StateSpec(
                    ccol,
                    f"Active latent cluster {cid} (k={subk})",
                    family="active_latent",
                    primary=True,
                )
            )
        validate_state_columns(run, [s.name for s in state_specs], spec)
        results, yearly = evaluate_state_specs(
            run,
            state_specs,
            score_col=S1_SCORE_COL,
            target_col=S1_TARGET_COL,
            spec=spec,
        )
        results["active_k"] = int(subk)
        yearly["active_k"] = int(subk)
        active_results_parts.append(results)
        active_yearly_parts.append(yearly)

        rng = np.random.default_rng(int(args.random_seed) + int(subk) + 2000)
        rand_labels = rng.integers(0, int(subk), size=len(run))
        rand_specs = [StateSpec("all_rows", "All active rows", family="active_baseline", primary=True)]
        for cid in range(int(subk)):
            rcol = f"h511_random_k{subk}_cluster_{cid}"
            run[rcol] = (rand_labels == cid).astype(int)
            rand_specs.append(
                StateSpec(
                    rcol,
                    f"Random active cluster {cid} (k={subk})",
                    family="active_random",
                    primary=True,
                )
            )
        rand_results, _ = evaluate_state_specs(
            run,
            rand_specs,
            score_col=S1_SCORE_COL,
            target_col=S1_TARGET_COL,
            spec=spec,
        )
        rand_results["active_k"] = int(subk)
        active_random_parts.append(rand_results)

        overlap = build_overlap_table(
            run,
            cluster_cols=cluster_cols,
            symbolic_cols=["c23_fresh_not_yesterday", "cofire_2", "c23_yesterday_carry", "c24"],
        )
        overlap["active_k"] = int(subk)
        active_overlap_parts.append(overlap)

        base_ic = float(results.loc[results["name"] == "all_rows", "avg_ic"].iloc[0])
        best_ic = float(results.loc[results["family"] == "active_latent", "avg_ic"].max())
        rand_best = float(rand_results.loc[rand_results["family"] == "active_random", "avg_ic"].max())
        overlap_focus = overlap.loc[
            overlap["symbolic_col"].isin(
                ["c23_fresh_not_yesterday", "cofire_2", "c23_yesterday_carry"]
            )
        ]
        max_j_by_symbol = (
            overlap_focus.groupby("symbolic_col")["jaccard"].max().to_dict()
            if not overlap_focus.empty
            else {}
        )
        mean_disentangle_jaccard = float(np.nanmean(list(max_j_by_symbol.values()))) if max_j_by_symbol else np.nan
        strong_non_sparse = int(
            (
                (results["family"] == "active_latent")
                & (results["avg_ic"] > base_ic)
                & (results["pooled_rows"] >= 5000)
                & (results["years"] >= 8)
            ).sum()
        )

        active_k_rows.append(
            {
                "active_k": int(subk),
                "silhouette_dev": sil,
                "inertia_dev": inertia,
                "active_rows": int(len(run)),
                "active_base_ic": base_ic,
                "best_cluster_ic": best_ic,
                "active_lift_vs_active_base": best_ic - base_ic,
                "random_best_cluster_ic": rand_best,
                "active_lift_minus_random_lift": (best_ic - base_ic) - (rand_best - base_ic),
                "strong_non_sparse_clusters": strong_non_sparse,
                "max_jaccard_onset": float(max_j_by_symbol.get("c23_fresh_not_yesterday", np.nan)),
                "max_jaccard_amplified": float(max_j_by_symbol.get("cofire_2", np.nan)),
                "max_jaccard_carry": float(max_j_by_symbol.get("c23_yesterday_carry", np.nan)),
                "mean_disentangle_jaccard": mean_disentangle_jaccard,
            }
        )
        active_with_labels[int(subk)] = run

    active_diag = pd.DataFrame(active_k_rows).sort_values(
        ["silhouette_dev", "active_k"], ascending=[False, True]
    )
    best_active_k = int(active_diag.iloc[0]["active_k"])
    best_active = active_diag.iloc[0]
    chosen_active = active_with_labels[best_active_k].copy()
    chosen_transitions = build_transition_table(chosen_active, label_col="h511_active_cluster_id")

    flag_quiet_recovery = bool(
        pd.notna(best_global["quiet_cluster_in_quiet"]) and float(best_global["quiet_cluster_in_quiet"]) >= 0.95
    )
    flag_c24_recovery = bool(
        pd.notna(best_global["c24_symbolic_in_cluster"])
        and float(best_global["c24_symbolic_in_cluster"]) >= 0.80
    )
    flag_beats_random = bool(
        pd.notna(best_active["active_lift_minus_random_lift"])
        and float(best_active["active_lift_minus_random_lift"]) >= 0.01
    )
    flag_disentangles = bool(
        pd.notna(best_active["mean_disentangle_jaccard"])
        and float(best_active["mean_disentangle_jaccard"]) >= 0.08
    )
    flag_non_sparse = bool(
        pd.notna(best_active["strong_non_sparse_clusters"])
        and int(best_active["strong_non_sparse_clusters"]) >= 2
    )

    flags = {
        "quiet_recovery_preserved": flag_quiet_recovery,
        "c24_recovery_preserved": flag_c24_recovery,
        "active_beats_random": flag_beats_random,
        "active_disentangling_nontrivial": flag_disentangles,
        "active_non_sparse_strength": flag_non_sparse,
    }
    passed = int(sum(int(v) for v in flags.values()))
    if passed >= 5:
        decision = "SUPPORTS active-manifold disentangling"
    elif passed >= 3:
        decision = "MIXED"
    else:
        decision = "DOES NOT SUPPORT active-manifold disentangling"

    global_path = write_dataframe_artifact(global_diag, context, f"{BRANCH_NAME}_global_k_discipline")
    global_overlap_path = write_dataframe_artifact(global_overlap, context, f"{BRANCH_NAME}_global_overlap")
    active_path = write_dataframe_artifact(active_diag, context, f"{BRANCH_NAME}_active_k_discipline")
    active_overlap_path = write_dataframe_artifact(
        pd.concat(active_overlap_parts, ignore_index=True),
        context,
        f"{BRANCH_NAME}_active_overlap",
    )
    active_results_path = write_dataframe_artifact(
        pd.concat(active_results_parts, ignore_index=True),
        context,
        f"{BRANCH_NAME}_active_results",
    )
    active_yearly_path = write_dataframe_artifact(
        pd.concat(active_yearly_parts, ignore_index=True),
        context,
        f"{BRANCH_NAME}_active_yearly",
    )
    random_path = write_dataframe_artifact(
        pd.concat(active_random_parts, ignore_index=True),
        context,
        f"{BRANCH_NAME}_active_random_baseline",
    )
    chosen_panel_cols = [
        "time",
        "ticker",
        S1_SCORE_COL,
        S1_TARGET_COL,
        "h511_global_cluster_id",
        "h511_active_cluster_id",
        "c23_fresh_not_yesterday",
        "cofire_2",
        "c23_yesterday_carry",
        "c24",
        *FEATURE_COLS,
    ]
    chosen_panel_cols = [col for col in chosen_panel_cols if col in chosen_active.columns]
    chosen_panel_path = write_dataframe_artifact(
        chosen_active[chosen_panel_cols].copy(),
        context,
        f"{BRANCH_NAME}_chosen_active_panel",
    )
    transition_path = write_dataframe_artifact(
        chosen_transitions,
        context,
        f"{BRANCH_NAME}_chosen_active_transitions",
    )

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "active_rows": int(len(active)),
            "global_k_sweep": list(GLOBAL_K_SWEEP),
            "active_k_sweep": list(ACTIVE_K_SWEEP),
            "selected_global_k_dev_silhouette": int(best_global_k),
            "selected_active_k_dev_silhouette": int(best_active_k),
            "quiet_cluster_id": int(quiet_cluster_id),
            "quiet_cluster_in_quiet": float(best_global["quiet_cluster_in_quiet"]),
            "c24_symbolic_in_cluster": float(best_global["c24_symbolic_in_cluster"]),
            "active_lift_minus_random_lift": float(best_active["active_lift_minus_random_lift"]),
            "mean_disentangle_jaccard": float(best_active["mean_disentangle_jaccard"]),
            "strong_non_sparse_clusters": int(best_active["strong_non_sparse_clusters"]),
            "flag_quiet_recovery_preserved": bool(flags["quiet_recovery_preserved"]),
            "flag_c24_recovery_preserved": bool(flags["c24_recovery_preserved"]),
            "flag_active_beats_random": bool(flags["active_beats_random"]),
            "flag_active_disentangling_nontrivial": bool(flags["active_disentangling_nontrivial"]),
            "flag_active_non_sparse_strength": bool(flags["active_non_sparse_strength"]),
        },
        artifacts={
            "global_k_discipline": global_path,
            "global_overlap": global_overlap_path,
            "active_k_discipline": active_path,
            "active_overlap": active_overlap_path,
            "active_results": active_results_path,
            "active_yearly": active_yearly_path,
            "active_random_baseline": random_path,
            "chosen_active_panel": chosen_panel_path,
            "chosen_active_transitions": transition_path,
        },
        metadata={
            "feature_columns": FEATURE_COLS,
            "k_choice_discipline": (
                "Both global and active k are selected by dev-only silhouette; "
                "IC is diagnostics-only and not used for model selection."
            ),
            "symbolic_overlap_columns": [
                "state_quiet",
                "c24",
                "c23_fresh_not_yesterday",
                "cofire_2",
                "c23_yesterday_carry",
            ],
        },
    )

    print(global_diag.to_string(index=False))
    print(active_diag.to_string(index=False))
    print(chosen_transitions.to_string(index=False))
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
