"""
H509: latent_state_discovery

Unsupervised latent-state discovery pass for ontology validation.

Core question:
If symbolic labels are removed from state construction, does a similar latent
state ecology reappear from observable emissions alone?

Protocol constraints:
- 2015-2025 only
- dev-fit only (2015-2022) for clustering transforms/models
- frozen assignment on validation (2023-2024) and confirmation (2025)
- predeclared small k sweep only: 4, 5, 6
- no symbolic labels in clustering inputs
"""

from __future__ import annotations

import argparse
import re
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

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
    evaluate_state_specs,
    load_s1_decision_panel,
    safe_spearman,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path


BRANCH_NAME = "latent_state_discovery"
MODE = "research_branch"
K_SWEEP = (4, 5, 6)

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Observable microstructure emissions contain enough information to "
        "rediscover the C23-family latent-state ecology without symbolic "
        "state labels in construction."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H509 latent state discovery")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument(
        "--order-stats-path",
        type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
    parser.add_argument(
        "--c16-path",
        type=str,
        default=str(data_path("features/xs_order_pressure_daily.parquet")),
    )
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    parser.add_argument("--random-seed", type=int, default=509)
    return parser.parse_args()


def _extract_pct(value: object) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    text = str(value).replace(",", ".")
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return np.nan
    m = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return np.nan
    return np.nan


def _compute_amihud(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["daily_return"] = out.groupby("ticker")["close"].pct_change()
    out["daily_return_abs"] = out["daily_return"].abs()
    out["turnover"] = out["close"] * out["volume"]
    out["amihud"] = out["daily_return_abs"] / (out["turnover"] + 1e-9)
    return out


def _load_ohlcv_amihud() -> pd.DataFrame:
    stock_dir = data_path("stock")
    parts: list[pd.DataFrame] = []
    for file in stock_dir.glob("gia_lich_su_*_1D.parquet"):
        try:
            part = pd.read_parquet(file, columns=["time", "close", "volume"])
            part["ticker"] = file.stem.replace("gia_lich_su_", "").replace("_1D", "").upper()
            parts.append(part)
        except Exception:
            continue
    if not parts:
        return pd.DataFrame(columns=["time", "ticker", "amihud"])
    merged = pd.concat(parts, ignore_index=True)
    merged["time"] = pd.to_datetime(merged["time"], errors="coerce").dt.normalize()
    merged = merged.dropna(subset=["time", "ticker", "close", "volume"])
    merged = _compute_amihud(merged)
    return merged[["time", "ticker", "amihud"]]


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    c16 = pd.read_parquet(args.c16_path, columns=["time", "ticker", "order_volume_ratio", "order_volume_ratio_rank"])
    c16["time"] = pd.to_datetime(c16["time"], errors="coerce").dt.normalize()
    c16["ticker"] = c16["ticker"].astype(str).str.upper()
    panel = panel.merge(c16, on=["time", "ticker"], how="left")

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats["time"] = pd.to_datetime(order_stats["date"], errors="coerce").dt.normalize()
    order_stats["ticker"] = order_stats["ticker"].astype(str).str.upper()
    order_stats["volume_daily"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    order_stats["vol_change"] = order_stats.groupby("ticker")["volume_daily"].pct_change()
    order_stats["vol_expansion_flag"] = order_stats.groupby("time")["vol_change"].transform(
        lambda x: (x >= x.quantile(0.8)).astype(float)
    )
    order_stats["price_change_pct"] = order_stats["price_change_raw"].map(_extract_pct)
    order_stats["at_ceiling"] = (order_stats["price_change_pct"] >= 6.5).astype(float)
    order_stats["ceiling_3d_count"] = (
        order_stats.groupby("ticker")["at_ceiling"]
        .rolling(3, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    order_stats["buy_sell_imbalance_norm"] = order_stats["buy_sell_volume_imbalance"] / (
        order_stats["volume_daily"] + 1e-9
    )
    order_stats["buy_count_share"] = order_stats["buy_order_count"] / (
        order_stats["buy_order_count"] + order_stats["sell_order_count"] + 1e-9
    )
    order_stats["sell_count_share"] = 1.0 - order_stats["buy_count_share"]

    merge_cols = [
        "time",
        "ticker",
        "vol_change",
        "vol_expansion_flag",
        "at_ceiling",
        "ceiling_3d_count",
        "buy_sell_imbalance_norm",
        "buy_count_share",
        "sell_count_share",
        "buy_order_count",
        "sell_order_count",
        "buy_order_volume",
        "sell_order_volume",
    ]
    panel = panel.merge(order_stats[merge_cols], on=["time", "ticker"], how="left")

    amihud = _load_ohlcv_amihud()
    panel = panel.merge(amihud, on=["time", "ticker"], how="left")

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    panel["amihud_log"] = np.log1p(panel["amihud"] * 1e9)
    panel["order_volume_ratio_log"] = np.log1p(panel["order_volume_ratio"])
    panel["lag_vol_expansion"] = panel.groupby("ticker")["vol_expansion_flag"].shift(1)
    panel["lag_order_volume_ratio_rank"] = panel.groupby("ticker")["order_volume_ratio_rank"].shift(1)
    panel["lag_at_ceiling"] = panel.groupby("ticker")["at_ceiling"].shift(1)
    panel["lag_buy_sell_imbalance_norm"] = panel.groupby("ticker")["buy_sell_imbalance_norm"].shift(1)

    panel = panel.replace([np.inf, -np.inf], np.nan)
    return panel.dropna(subset=[S1_SCORE_COL, S1_TARGET_COL]).copy()


def build_symbolic_posthoc(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Symbolic states for overlap interpretation only.
    These are intentionally excluded from clustering inputs.
    """
    out = panel.copy()
    amihud_p80 = out["amihud"].quantile(0.8)
    out["high_illiq"] = (out["amihud"] >= amihud_p80).astype(int)
    out["buy_heavy"] = (out["order_volume_ratio"] > 1.0).astype(int)
    out["ceiling_2of3"] = (out["ceiling_3d_count"] >= 2.0).astype(int)

    out["c23"] = ((out["high_illiq"] == 1) & (out["vol_expansion_flag"] >= 0.5)).astype(int)
    out["c24"] = (out["ceiling_2of3"] == 1).astype(int)
    out["c26"] = (
        (out["buy_heavy"] == 1)
        & (out["high_illiq"] == 1)
        & (out["vol_expansion_flag"] >= 0.5)
    ).astype(int)
    out["cofire_count"] = out[["c23", "c24", "c26"]].sum(axis=1)
    out["cofire_2"] = (out["cofire_count"] >= 2).astype(int)
    out["c16_low"] = (out["order_volume_ratio_rank"] <= 0.2).astype(int)
    out["c16_low_c23"] = ((out["c16_low"] == 1) & (out["c23"] == 1)).astype(int)

    out["c23_prev"] = out.groupby("ticker")["c23"].shift(1).fillna(0).astype(int)
    out["c23_fresh_not_yesterday"] = ((out["c23"] == 1) & (out["c23_prev"] == 0)).astype(int)
    out["c23_yesterday_carry"] = ((out["c23"] == 0) & (out["c23_prev"] == 1)).astype(int)
    out["state_quiet"] = (out["cofire_count"] == 0).astype(int)
    return out


def _jaccard(mask_a: pd.Series, mask_b: pd.Series) -> float:
    a = mask_a.fillna(False).astype(bool)
    b = mask_b.fillna(False).astype(bool)
    inter = (a & b).sum()
    union = (a | b).sum()
    if union == 0:
        return np.nan
    return float(inter / union)


def _containment(mask_a: pd.Series, mask_b: pd.Series) -> float:
    a = mask_a.fillna(False).astype(bool)
    b = mask_b.fillna(False).astype(bool)
    denom = a.sum()
    if denom == 0:
        return np.nan
    return float((a & b).sum() / denom)


def build_transition_table(panel: pd.DataFrame, *, k: int, label_col: str) -> pd.DataFrame:
    tmp = panel[["ticker", "time", label_col]].copy()
    tmp = tmp.sort_values(["ticker", "time"])
    tmp["prev_state"] = tmp.groupby("ticker")[label_col].shift(1)
    tmp = tmp.dropna(subset=["prev_state"])
    tmp["state"] = tmp[label_col].astype(int)
    tmp["prev_state"] = tmp["prev_state"].astype(int)

    counts = tmp.groupby(["prev_state", "state"]).size().reset_index(name="count")
    total = counts["count"].sum()
    counts["prob_global"] = counts["count"] / total if total > 0 else np.nan
    prev_totals = counts.groupby("prev_state")["count"].transform("sum")
    counts["prob_from_prev"] = counts["count"] / prev_totals
    counts["k"] = int(k)
    return counts.sort_values(["k", "prev_state", "state"]).reset_index(drop=True)


def run_random_partition(
    panel: pd.DataFrame,
    *,
    k: int,
    spec: ExperimentSpec,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed + int(k))
    labels = rng.integers(0, int(k), size=len(panel))
    tmp = panel.copy()
    state_specs = [StateSpec("all_rows", "All rows", family="baseline", primary=True)]
    for cid in range(int(k)):
        col = f"rand_k{k}_cluster_{cid}"
        tmp[col] = (labels == cid).astype(int)
        state_specs.append(
            StateSpec(
                col,
                f"Random cluster {cid} (k={k})",
                family="random_cluster",
                primary=True,
            )
        )
    results, _ = evaluate_state_specs(
        tmp,
        state_specs,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )
    results["k"] = int(k)
    return results


def discover_k(
    panel: pd.DataFrame,
    *,
    k: int,
    feature_cols: list[str],
    spec: ExperimentSpec,
    random_seed: int,
) -> dict[str, object]:
    out_panel = panel.copy()
    years = pd.to_datetime(out_panel["time"], errors="coerce").dt.year
    dev_years = set(spec.phases[0].years)
    dev_mask = years.isin(dev_years)
    if int(dev_mask.sum()) < 10000:
        raise ValueError(f"k={k} has too few dev rows: {int(dev_mask.sum())}")

    x_raw = out_panel[feature_cols].replace([np.inf, -np.inf], np.nan)
    imputer = SimpleImputer(strategy="median")
    x_dev_imp = imputer.fit_transform(x_raw.loc[dev_mask])
    scaler = StandardScaler()
    x_dev = scaler.fit_transform(x_dev_imp)

    model = MiniBatchKMeans(
        n_clusters=int(k),
        random_state=int(random_seed) + int(k),
        n_init=20,
        batch_size=65536,
        max_iter=300,
        reassignment_ratio=0.01,
    )
    model.fit(x_dev)

    x_all = scaler.transform(imputer.transform(x_raw))
    labels = model.predict(x_all)
    label_col = f"k{k}_cluster_id"
    out_panel[label_col] = labels.astype(int)

    state_specs = [StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True)]
    for cid in range(int(k)):
        col = f"k{k}_cluster_{cid}"
        out_panel[col] = (out_panel[label_col] == cid).astype(int)
        state_specs.append(
            StateSpec(
                col,
                f"Latent cluster {cid} (k={k})",
                family="latent_cluster",
                primary=True,
            )
        )

    validate_state_columns(out_panel, [state.name for state in state_specs], spec)
    results, yearly = evaluate_state_specs(
        out_panel,
        state_specs,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )
    results["k"] = int(k)
    yearly["k"] = int(k)

    transitions = build_transition_table(out_panel, k=int(k), label_col=label_col)

    centroid_rows: list[dict[str, object]] = []
    for cid in range(int(k)):
        mask = out_panel[label_col] == cid
        row: dict[str, object] = {
            "k": int(k),
            "cluster_id": int(cid),
            "rows": int(mask.sum()),
            "share": float(mask.mean()),
        }
        center_std = model.cluster_centers_[cid]
        center_raw = scaler.inverse_transform(center_std.reshape(1, -1))[0]
        for idx, feat in enumerate(feature_cols):
            row[f"center_std__{feat}"] = float(center_std[idx])
            row[f"center_raw__{feat}"] = float(center_raw[idx])
        centroid_rows.append(row)
    centroids = pd.DataFrame(centroid_rows)

    phase_rows: list[dict[str, object]] = []
    dev_centers: dict[int, np.ndarray] = {}
    for cid in range(int(k)):
        dev_cluster_mask = (out_panel[label_col] == cid) & dev_mask
        if dev_cluster_mask.any():
            dev_centers[cid] = x_all[dev_cluster_mask.values].mean(axis=0)
        else:
            dev_centers[cid] = np.full(len(feature_cols), np.nan)

    for phase in spec.phases:
        phase_mask = years.isin(set(phase.years))
        phase_total = int(phase_mask.sum())
        for cid in range(int(k)):
            phase_cluster_mask = phase_mask & (out_panel[label_col] == cid)
            rows = int(phase_cluster_mask.sum())
            share = float(rows / phase_total) if phase_total > 0 else np.nan
            if rows > 0:
                phase_center = x_all[phase_cluster_mask.values].mean(axis=0)
            else:
                phase_center = np.full(len(feature_cols), np.nan)
            dev_center = dev_centers[cid]
            if np.isnan(dev_center).all() or np.isnan(phase_center).all():
                dist = np.nan
            else:
                dist = float(np.linalg.norm(phase_center - dev_center))
            phase_rows.append(
                {
                    "k": int(k),
                    "phase": phase.name,
                    "cluster_id": int(cid),
                    "rows": rows,
                    "share": share,
                    "distance_to_dev_center_l2": dist,
                }
            )
    phase_stability = pd.DataFrame(phase_rows)

    return {
        "panel": out_panel,
        "results": results,
        "yearly": yearly,
        "transitions": transitions,
        "centroids": centroids,
        "phase_stability": phase_stability,
        "state_specs": state_specs,
        "label_col": label_col,
    }


def build_overlap_table(
    panel: pd.DataFrame,
    *,
    k_values: tuple[int, ...],
    symbolic_cols: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for k in k_values:
        for cid in range(int(k)):
            cluster_col = f"k{k}_cluster_{cid}"
            if cluster_col not in panel.columns:
                continue
            cluster_mask = panel[cluster_col].fillna(False).astype(bool)
            for sym in symbolic_cols:
                sym_mask = panel[sym].fillna(False).astype(bool)
                rows.append(
                    {
                        "k": int(k),
                        "cluster_id": int(cid),
                        "cluster_col": cluster_col,
                        "symbolic_col": sym,
                        "jaccard": _jaccard(cluster_mask, sym_mask),
                        "contain_cluster_in_symbolic": _containment(cluster_mask, sym_mask),
                        "contain_symbolic_in_cluster": _containment(sym_mask, cluster_mask),
                        "cluster_share": float(cluster_mask.mean()),
                        "symbolic_share": float(sym_mask.mean()),
                    }
                )
    return pd.DataFrame(rows)


def build_ontology_mapping(overlap: pd.DataFrame) -> pd.DataFrame:
    mapping_targets = [
        ("state_quiet", "quiet"),
        ("c23_fresh_not_yesterday", "onset-like"),
        ("cofire_2", "amplification-like"),
        ("c23_yesterday_carry", "carry-like"),
        ("c24", "c24-like queue-friction"),
    ]
    rows: list[dict[str, object]] = []
    for symbolic_col, interpretation in mapping_targets:
        subset = overlap.loc[overlap["symbolic_col"] == symbolic_col].copy()
        if subset.empty:
            rows.append(
                {
                    "symbolic_col": symbolic_col,
                    "interpretation": interpretation,
                    "k": None,
                    "cluster_id": None,
                    "jaccard": None,
                    "contain_cluster_in_symbolic": None,
                    "contain_symbolic_in_cluster": None,
                }
            )
            continue
        subset = subset.sort_values("jaccard", ascending=False)
        best = subset.iloc[0]
        rows.append(
            {
                "symbolic_col": symbolic_col,
                "interpretation": interpretation,
                "k": int(best["k"]),
                "cluster_id": int(best["cluster_id"]),
                "jaccard": float(best["jaccard"]) if pd.notna(best["jaccard"]) else None,
                "contain_cluster_in_symbolic": float(best["contain_cluster_in_symbolic"])
                if pd.notna(best["contain_cluster_in_symbolic"])
                else None,
                "contain_symbolic_in_cluster": float(best["contain_symbolic_in_cluster"])
                if pd.notna(best["contain_symbolic_in_cluster"])
                else None,
            }
        )
    return pd.DataFrame(rows)


def summarize_k(
    *,
    k: int,
    results: pd.DataFrame,
    phase_stability: pd.DataFrame,
    overlap: pd.DataFrame,
    transitions: pd.DataFrame,
    random_results: pd.DataFrame,
) -> dict[str, object]:
    all_row = results.loc[results["name"] == "all_rows"].iloc[0]
    base_ic = float(all_row["avg_ic"]) if pd.notna(all_row["avg_ic"]) else np.nan

    cluster_rows = results.loc[results["family"] == "latent_cluster"].copy()
    cluster_rows = cluster_rows.loc[pd.notna(cluster_rows["avg_ic"])]
    best_cluster_ic = float(cluster_rows["avg_ic"].max()) if not cluster_rows.empty else np.nan
    active_lift = best_cluster_ic - base_ic if np.isfinite(best_cluster_ic) and np.isfinite(base_ic) else np.nan
    strong_non_sparse = int(
        (
            (cluster_rows["avg_ic"] > base_ic)
            & (cluster_rows["pooled_rows"] >= 10000)
            & (cluster_rows["years"] >= 8)
        ).sum()
    )

    quiet_overlap = overlap.loc[
        (overlap["k"] == int(k)) & (overlap["symbolic_col"] == "state_quiet"),
        "contain_cluster_in_symbolic",
    ]
    quiet_overlap_max = float(quiet_overlap.max()) if len(quiet_overlap) else np.nan

    stab = phase_stability.loc[
        (phase_stability["k"] == int(k))
        & (phase_stability["phase"] != "dev")
        & (phase_stability["rows"] >= 500),
        "distance_to_dev_center_l2",
    ]
    median_phase_distance = float(stab.median()) if len(stab) else np.nan

    tr = transitions.loc[transitions["k"] == int(k)].copy()
    self_tr = tr.loc[tr["prev_state"] == tr["state"]]
    mean_self_prob = float(self_tr["prob_from_prev"].mean()) if not self_tr.empty else np.nan

    random_k = random_results.loc[(random_results["k"] == int(k)) & (random_results["family"] == "random_cluster")]
    random_k = random_k.loc[pd.notna(random_k["avg_ic"])]
    random_best_ic = float(random_k["avg_ic"].max()) if not random_k.empty else np.nan
    random_active_lift = random_best_ic - base_ic if np.isfinite(random_best_ic) and np.isfinite(base_ic) else np.nan
    random_gap = active_lift - random_active_lift if np.isfinite(active_lift) and np.isfinite(random_active_lift) else np.nan

    return {
        "k": int(k),
        "base_ic": base_ic,
        "best_cluster_ic": best_cluster_ic,
        "active_lift_vs_all_rows": active_lift,
        "random_best_cluster_ic": random_best_ic,
        "random_active_lift_vs_all_rows": random_active_lift,
        "active_lift_minus_random_lift": random_gap,
        "strong_non_sparse_clusters": strong_non_sparse,
        "quiet_overlap_max": quiet_overlap_max,
        "median_phase_distance_to_dev": median_phase_distance,
        "mean_self_transition_prob": mean_self_prob,
    }


def classify_verdict(best_row: pd.Series) -> tuple[str, dict[str, bool]]:
    flags = {
        "quiet_separation": bool(pd.notna(best_row["quiet_overlap_max"]) and best_row["quiet_overlap_max"] >= 0.70),
        "non_trivial_active_lift": bool(
            pd.notna(best_row["active_lift_vs_all_rows"]) and best_row["active_lift_vs_all_rows"] >= 0.05
        ),
        "beats_random_partition": bool(
            pd.notna(best_row["active_lift_minus_random_lift"]) and best_row["active_lift_minus_random_lift"] >= 0.01
        ),
        "phase_stable": bool(
            pd.notna(best_row["median_phase_distance_to_dev"]) and best_row["median_phase_distance_to_dev"] <= 0.75
        ),
        "non_sparse_strength": bool(
            pd.notna(best_row["strong_non_sparse_clusters"]) and best_row["strong_non_sparse_clusters"] >= 2
        ),
        "persistent_states": bool(
            pd.notna(best_row["mean_self_transition_prob"]) and best_row["mean_self_transition_prob"] >= 0.35
        ),
    }
    passed = sum(int(v) for v in flags.values())
    if passed >= 5:
        verdict = "SUPPORTS latent ontology"
    elif passed >= 3:
        verdict = "MIXED"
    else:
        verdict = "DOES NOT SUPPORT latent ontology"
    return verdict, flags


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)
    panel = build_symbolic_posthoc(panel)

    feature_cols = [
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
    ]
    forbidden_feature_tokens = ("c23", "fresh", "cofire", "carry", "low_c16", "lowc16", "router")
    lower_feature_blob = " ".join(feature_cols).lower()
    if any(token in lower_feature_blob for token in forbidden_feature_tokens):
        raise ValueError("feature set appears to include symbolic label aliases")

    results_all: list[pd.DataFrame] = []
    yearly_all: list[pd.DataFrame] = []
    transitions_all: list[pd.DataFrame] = []
    centroids_all: list[pd.DataFrame] = []
    phase_stability_all: list[pd.DataFrame] = []
    random_all: list[pd.DataFrame] = []

    # Keep all discovered cluster labels on one shared panel for overlap tables.
    clustered_panel = panel.copy()

    for k in K_SWEEP:
        discovered = discover_k(
            clustered_panel,
            k=int(k),
            feature_cols=feature_cols,
            spec=spec,
            random_seed=int(args.random_seed),
        )
        clustered_panel = discovered["panel"]
        results_all.append(discovered["results"])
        yearly_all.append(discovered["yearly"])
        transitions_all.append(discovered["transitions"])
        centroids_all.append(discovered["centroids"])
        phase_stability_all.append(discovered["phase_stability"])
        random_all.append(
            run_random_partition(
                clustered_panel,
                k=int(k),
                spec=spec,
                seed=int(args.random_seed),
            )
        )

    results = pd.concat(results_all, ignore_index=True)
    yearly = pd.concat(yearly_all, ignore_index=True)
    transitions = pd.concat(transitions_all, ignore_index=True)
    centroids = pd.concat(centroids_all, ignore_index=True)
    phase_stability = pd.concat(phase_stability_all, ignore_index=True)
    random_results = pd.concat(random_all, ignore_index=True)

    symbolic_cols = [
        "state_quiet",
        "c23_fresh_not_yesterday",
        "cofire_2",
        "c23_yesterday_carry",
        "c24",
        "c16_low_c23",
        "c23",
    ]
    overlap = build_overlap_table(clustered_panel, k_values=K_SWEEP, symbolic_cols=symbolic_cols)
    ontology_mapping = build_ontology_mapping(overlap)

    k_summary_rows: list[dict[str, object]] = []
    for k in K_SWEEP:
        row = summarize_k(
            k=int(k),
            results=results.loc[results["k"] == int(k)],
            phase_stability=phase_stability,
            overlap=overlap,
            transitions=transitions,
            random_results=random_results,
        )
        k_summary_rows.append(row)
    k_summary = pd.DataFrame(k_summary_rows)
    score = (
        k_summary["active_lift_minus_random_lift"].fillna(-999.0) * 1.0
        + k_summary["strong_non_sparse_clusters"].fillna(0.0) * 0.01
        + k_summary["quiet_overlap_max"].fillna(0.0) * 0.02
        - k_summary["median_phase_distance_to_dev"].fillna(999.0) * 0.005
    )
    best_idx = int(score.idxmax())
    best_row = k_summary.loc[best_idx]
    best_k = int(best_row["k"])
    verdict, verdict_flags = classify_verdict(best_row)

    panel_cols = [
        "time",
        "ticker",
        S1_SCORE_COL,
        S1_TARGET_COL,
        *feature_cols,
        "state_quiet",
        "c23",
        "c24",
        "c23_fresh_not_yesterday",
        "cofire_2",
        "c23_yesterday_carry",
        "c16_low_c23",
    ] + [f"k{k}_cluster_id" for k in K_SWEEP]
    panel_cols = [col for col in panel_cols if col in clustered_panel.columns]
    clustered_panel_out = clustered_panel[panel_cols].copy()

    clustered_panel_path = write_dataframe_artifact(
        clustered_panel_out, context, f"{BRANCH_NAME}_clustered_panel"
    )
    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")
    transitions_path = write_dataframe_artifact(transitions, context, f"{BRANCH_NAME}_transitions")
    centroids_path = write_dataframe_artifact(centroids, context, f"{BRANCH_NAME}_centroids")
    phase_stability_path = write_dataframe_artifact(
        phase_stability, context, f"{BRANCH_NAME}_phase_stability"
    )
    overlap_path = write_dataframe_artifact(overlap, context, f"{BRANCH_NAME}_overlap")
    ontology_mapping_path = write_dataframe_artifact(
        ontology_mapping, context, f"{BRANCH_NAME}_ontology_mapping"
    )
    random_path = write_dataframe_artifact(random_results, context, f"{BRANCH_NAME}_random_baseline")
    k_summary_path = write_dataframe_artifact(k_summary, context, f"{BRANCH_NAME}_k_summary")

    summary_path = context.write_summary(
        summary={
            "decision": verdict,
            "panel_rows": int(len(clustered_panel)),
            "feature_count": int(len(feature_cols)),
            "k_sweep": list(K_SWEEP),
            "best_k": int(best_k),
            "best_k_active_lift_vs_all_rows": float(best_row["active_lift_vs_all_rows"])
            if pd.notna(best_row["active_lift_vs_all_rows"])
            else None,
            "best_k_random_lift_gap": float(best_row["active_lift_minus_random_lift"])
            if pd.notna(best_row["active_lift_minus_random_lift"])
            else None,
            "best_k_quiet_overlap_max": float(best_row["quiet_overlap_max"])
            if pd.notna(best_row["quiet_overlap_max"])
            else None,
            "best_k_median_phase_distance_to_dev": float(best_row["median_phase_distance_to_dev"])
            if pd.notna(best_row["median_phase_distance_to_dev"])
            else None,
            "best_k_strong_non_sparse_clusters": int(best_row["strong_non_sparse_clusters"])
            if pd.notna(best_row["strong_non_sparse_clusters"])
            else None,
            "best_k_mean_self_transition_prob": float(best_row["mean_self_transition_prob"])
            if pd.notna(best_row["mean_self_transition_prob"])
            else None,
            "satisfies_quiet_separation": bool(verdict_flags["quiet_separation"]),
            "satisfies_non_trivial_active_lift": bool(verdict_flags["non_trivial_active_lift"]),
            "satisfies_beats_random_partition": bool(verdict_flags["beats_random_partition"]),
            "satisfies_phase_stable": bool(verdict_flags["phase_stable"]),
            "satisfies_non_sparse_strength": bool(verdict_flags["non_sparse_strength"]),
            "satisfies_persistent_states": bool(verdict_flags["persistent_states"]),
        },
        artifacts={
            "clustered_panel": clustered_panel_path,
            "results": results_path,
            "yearly": yearly_path,
            "transitions": transitions_path,
            "centroids": centroids_path,
            "phase_stability": phase_stability_path,
            "overlap": overlap_path,
            "ontology_mapping": ontology_mapping_path,
            "random_baseline": random_path,
            "k_summary": k_summary_path,
        },
        metadata={
            "feature_columns": feature_cols,
            "k_sweep": list(K_SWEEP),
            "state_construction_note": (
                "Clustering inputs are observable emissions only; symbolic C23/freshness/"
                "cofire/carry/low-C16 states are computed post-hoc for overlap interpretation."
            ),
            "symbolic_overlap_columns": symbolic_cols,
        },
    )

    print(results.sort_values(["k", "avg_ic"], ascending=[True, False], na_position="last").to_string(index=False))
    print(k_summary.sort_values("k").to_string(index=False))
    print(ontology_mapping.to_string(index=False))
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
