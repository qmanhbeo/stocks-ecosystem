"""
H510: Bull Participation State Audit

Structural diagnostic for bull-market cash-drag problem.

Question:
Are 2017/2025 structurally different from 2021/2022 in terms of latent state
distribution or symbolic emission rates that could explain why heuristic-trader
becomes cash-heavy in some bull years but not others?

Protocol:
- 2015-2025 only
- Use H509 clustered panel directly (k=6)
- No 2026
- No portfolio construction
- No strategy parameter optimization
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    safe_spearman,
)


BRANCH_NAME = "bull_participation_state_audit"

FAILURE_BULL_YEARS = [2017, 2025]
SUCCESS_CONTRAST_YEARS = [2021, 2022]
SECONDARY_YEARS = [2019, 2024]
ALL_FOCUS_YEARS = sorted(set(FAILURE_BULL_YEARS + SUCCESS_CONTRAST_YEARS + SECONDARY_YEARS))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H510 Bull Participation State Audit")
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
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def load_panel(args: argparse.Namespace) -> pd.DataFrame:
    panel = pd.read_parquet(args.h509_panel_path)
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    panel["year"] = panel["time"].dt.year

    score_col = "s1_xs_proba"
    target_col = "s1_barrier_hit_1d"

    panel = panel.dropna(subset=[score_col, target_col])
    panel = panel[(panel["year"] >= args.start_year) & (panel["year"] <= args.end_year)]
    return panel


def compute_yearly_state_distribution(panel: pd.DataFrame, k: int) -> pd.DataFrame:
    label_col = f"k{k}_cluster_id"
    years = panel["year"].unique()

    out_panel = panel.copy()
    for cid in range(k):
        cluster_col = f"k{k}_cluster_{cid}"
        out_panel[cluster_col] = (out_panel[label_col] == cid).astype(int)

    rows = []
    for year in sorted(years):
        year_panel = out_panel[out_panel["year"] == year]
        total = len(year_panel)

        row = {"year": int(year), "total_rows": int(total), "unique_tickers": int(year_panel["ticker"].nunique())}

        for cid in range(k):
            cluster_col = f"k{k}_cluster_{cid}"

            count = int(year_panel[cluster_col].sum())
            share = float(count / total) if total > 0 else np.nan
            row[f"cluster_{cid}_count"] = count
            row[f"cluster_{cid}_share"] = share

        for state_col in ["state_quiet", "c23", "c24", "c23_fresh_not_yesterday", "cofire_2", "c23_yesterday_carry", "c16_low_c23"]:
            if state_col in year_panel.columns:
                count = int(year_panel[state_col].sum())
                share = float(count / total) if total > 0 else np.nan
                row[f"{state_col}_count"] = count
                row[f"{state_col}_share"] = share

        c16_low_share = year_panel["order_volume_ratio_rank"].apply(lambda x: x <= 0.2 if pd.notna(x) else np.nan).mean()
        row["c16_low_share"] = float(c16_low_share) if pd.notna(c16_low_share) else np.nan

        c16_high_share = year_panel["order_volume_ratio_rank"].apply(lambda x: x >= 0.8 if pd.notna(x) else np.nan).mean()
        row["c16_high_share"] = float(c16_high_share) if pd.notna(c16_high_share) else np.nan

        rows.append(row)

    return pd.DataFrame(rows)


def compute_yearly_ic_by_cluster(panel: pd.DataFrame, k: int) -> pd.DataFrame:
    label_col = f"k{k}_cluster_id"
    score_col = "s1_xs_proba"
    target_col = "s1_barrier_hit_1d"

    years = panel["year"].unique()
    rows = []

    for year in sorted(years):
        year_panel = panel[panel["year"] == year].copy()

        result = safe_spearman(year_panel, score_col, target_col, min_rows=50)
        all_ic = result.get("ic")
        row = {"year": int(year), "all_rows_ic": float(all_ic) if pd.notna(all_ic) else np.nan}

        for cid in range(k):
            cluster_mask = year_panel[label_col] == cid
            if cluster_mask.sum() >= 50:
                cluster_panel = year_panel[cluster_mask]
                result = safe_spearman(cluster_panel, score_col, target_col, min_rows=50)
                ic = result.get("ic")
                row[f"cluster_{cid}_ic"] = float(ic) if pd.notna(ic) else np.nan
                row[f"cluster_{cid}_n"] = int(cluster_mask.sum())
            else:
                row[f"cluster_{cid}_ic"] = np.nan
                row[f"cluster_{cid}_n"] = int(cluster_mask.sum())

        for state_col in ["state_quiet", "c23", "c24", "c23_fresh_not_yesterday", "c16_low_c23"]:
            if state_col in year_panel.columns:
                state_mask = year_panel[state_col] == 1
                if state_mask.sum() >= 50:
                    state_panel = year_panel[state_mask]
                    result = safe_spearman(state_panel, score_col, target_col, min_rows=50)
                    ic = result.get("ic")
                    row[f"{state_col}_ic"] = float(ic) if pd.notna(ic) else np.nan
                    row[f"{state_col}_n"] = int(state_mask.sum())
                else:
                    row[f"{state_col}_ic"] = np.nan
                    row[f"{state_col}_n"] = int(state_mask.sum())

        rows.append(row)

    return pd.DataFrame(rows)


def compute_cluster_transitions_by_year(panel: pd.DataFrame, k: int) -> pd.DataFrame:
    label_col = f"k{k}_cluster_id"

    panel = panel.sort_values(["ticker", "time"]).copy()
    panel["prev_cluster"] = panel.groupby("ticker")[label_col].shift(1)

    years = panel["year"].unique()
    rows = []

    for year in sorted(years):
        year_panel = panel[panel["year"] == year].copy()
        year_panel = year_panel.dropna(subset=["prev_cluster"])

        if len(year_panel) < 100:
            continue

        for cid in range(k):
            from_mask = year_panel["prev_cluster"] == cid
            from_count = int(from_mask.sum())

            if from_count < 100:
                continue

            to_counts = year_panel.loc[from_mask, label_col].value_counts()
            for to_cid in range(k):
                count = int(to_counts.get(to_cid, 0))
                prob = float(count / from_count) if from_count > 0 else np.nan
                rows.append(
                    {
                        "year": int(year),
                        "from_cluster": int(cid),
                        "to_cluster": int(to_cid),
                        "count": count,
                        "prob": prob,
                    }
                )

    return pd.DataFrame(rows)


def compute_year_comparison(dist_df: pd.DataFrame, ic_df: pd.DataFrame) -> pd.DataFrame:
    comparisons = []

    pairs = [
        ("2017 vs 2021", 2017, 2021),
        ("2025 vs 2021", 2025, 2021),
        ("2022 vs 2021", 2022, 2021),
        ("2019 vs 2017", 2019, 2017),
        ("2024 vs 2025", 2024, 2025),
    ]

    for name, y1, y2 in pairs:
        d1 = dist_df[dist_df["year"] == y1].iloc[0] if len(dist_df[dist_df["year"] == y1]) > 0 else None
        d2 = dist_df[dist_df["year"] == y2].iloc[0] if len(dist_df[dist_df["year"] == y2]) > 0 else None

        i1 = ic_df[ic_df["year"] == y1].iloc[0] if len(ic_df[ic_df["year"] == y1]) > 0 else None
        i2 = ic_df[ic_df["year"] == y2].iloc[0] if len(ic_df[ic_df["year"] == y2]) > 0 else None

        if d1 is None or d2 is None:
            continue

        row = {"comparison": name, "year_a": y1, "year_b": y2}

        for col in ["state_quiet_share", "c23_share", "c24_share", "c16_low_share", "c16_high_share"]:
            if col in d1.index and col in d2.index:
                v1 = d1.get(col, np.nan)
                v2 = d2.get(col, np.nan)
                diff = float(v1 - v2) if pd.notna(v1) and pd.notna(v2) else np.nan
                row[f"{col}_diff"] = diff

        if i1 is not None and i2 is not None:
            row["all_rows_ic_a"] = i1.get("all_rows_ic", np.nan)
            row["all_rows_ic_b"] = i2.get("all_rows_ic", np.nan)
            if pd.notna(i1.get("all_rows_ic")) and pd.notna(i2.get("all_rows_ic")):
                row["all_rows_ic_diff"] = float(i1["all_rows_ic"] - i2["all_rows_ic"])

            for cid in range(6):
                ic_col = f"cluster_{cid}_ic"
                if ic_col in i1.index and ic_col in i2.index:
                    v1 = i1.get(ic_col, np.nan)
                    v2 = i2.get(ic_col, np.nan)
                    if pd.notna(v1) and pd.notna(v2):
                        row[f"{ic_col}_diff"] = float(v1 - v2)

        comparisons.append(row)

    return pd.DataFrame(comparisons)


def classify_year_category(year: int) -> str:
    if year in FAILURE_BULL_YEARS:
        return "failure_bull"
    elif year in SUCCESS_CONTRAST_YEARS:
        return "success_contrast"
    elif year in SECONDARY_YEARS:
        return "secondary"
    return "other"


def run_audit(args: argparse.Namespace) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = ROOT / "artifacts" / f"h510_bull_participation_state_audit" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading H509 clustered panel: {args.h509_panel_path}")
    panel = load_panel(args)
    print(f"Panel loaded: {len(panel)} rows, years {panel['year'].min()}-{panel['year'].max()}")

    k = 6

    print("Computing yearly state distribution...")
    yearly_dist = compute_yearly_state_distribution(panel, k)
    print(f"Yearly distribution computed: {len(yearly_dist)} years")

    print("Computing yearly IC by cluster...")
    yearly_ic = compute_yearly_ic_by_cluster(panel, k)
    print(f"Yearly IC computed: {len(yearly_ic)} years")

    print("Computing cluster transitions by year...")
    transitions = compute_cluster_transitions_by_year(panel, k)
    print(f"Transitions computed: {len(transitions)} transition records")

    print("Computing year comparisons...")
    comparisons = compute_year_comparison(yearly_dist, yearly_ic)
    print(f"Comparisons computed: {len(comparisons)}")

    yearly_dist_path = output_dir / "year_state_summary.csv"
    yearly_dist.to_csv(yearly_dist_path, index=False)

    yearly_ic_path = output_dir / "yearly_ic_by_state.csv"
    yearly_ic.to_csv(yearly_ic_path, index=False)

    transitions_path = output_dir / "transition_summary.csv"
    transitions.to_csv(transitions_path, index=False)

    comparisons_path = output_dir / "focus_year_comparison.csv"
    comparisons.to_csv(comparisons_path, index=False)

    focus_years = yearly_dist[yearly_dist["year"].isin(ALL_FOCUS_YEARS)].copy()
    focus_years["year_category"] = focus_years["year"].apply(classify_year_category)
    focus_years_path = output_dir / "focus_years_summary.csv"
    focus_years.to_csv(focus_years_path, index=False)

    print("\n" + "=" * 80)
    print("YEARLY STATE DISTRIBUTION (Focus Years)")
    print("=" * 80)
    focus_cols = ["year", "year_category", "total_rows", "unique_tickers", "state_quiet_share", "c23_share", "c24_share", "c16_low_share", "c16_high_share"]
    focus_cols = [c for c in focus_cols if c in yearly_dist.columns]
    print(focus_years[focus_cols].to_string(index=False))

    print("\n" + "=" * 80)
    print("YEARLY IC BY STATE (Focus Years)")
    print("=" * 80)
    focus_ic = yearly_ic[yearly_ic["year"].isin(ALL_FOCUS_YEARS)].copy()
    focus_ic["year_category"] = focus_ic["year"].apply(classify_year_category)
    ic_cols = ["year", "year_category", "all_rows_ic"]
    for cid in range(k):
        ic_cols.append(f"cluster_{cid}_ic")
    ic_cols = [c for c in ic_cols if c in focus_ic.columns]
    print(focus_ic[ic_cols].to_string(index=False))

    print("\n" + "=" * 80)
    print("FOCUS YEAR COMPARISONS")
    print("=" * 80)
    print(comparisons.to_string(index=False))

    summary = {
        "total_panel_rows": int(len(panel)),
        "k_used": int(k),
        "focus_years": ALL_FOCUS_YEARS,
        "failure_bull_years": FAILURE_BULL_YEARS,
        "success_contrast_years": SUCCESS_CONTRAST_YEARS,
        "secondary_years": SECONDARY_YEARS,
        "failure_bull_avg_quiet_share": float(
            focus_years[focus_years["year_category"] == "failure_bull"]["state_quiet_share"].mean()
        )
        if len(focus_years[focus_years["year_category"] == "failure_bull"]) > 0
        else None,
        "success_contrast_avg_quiet_share": float(
            focus_years[focus_years["year_category"] == "success_contrast"]["state_quiet_share"].mean()
        )
        if len(focus_years[focus_years["year_category"] == "success_contrast"]) > 0
        else None,
        "failure_bull_avg_c23_share": float(
            focus_years[focus_years["year_category"] == "failure_bull"]["c23_share"].mean()
        )
        if len(focus_years[focus_years["year_category"] == "failure_bull"]) > 0
        else None,
        "success_contrast_avg_c23_share": float(
            focus_years[focus_years["year_category"] == "success_contrast"]["c23_share"].mean()
        )
        if len(focus_years[focus_years["year_category"] == "success_contrast"]) > 0
        else None,
    }

    impact_cols = ["c23_share", "c24_share", "c23_fresh_not_yesterday_share", "c16_low_c23_share"]
    for col in impact_cols:
        if col in focus_years.columns:
            fail_vals = focus_years[focus_years["year_category"] == "failure_bull"][col].dropna()
            succ_vals = focus_years[focus_years["year_category"] == "success_contrast"][col].dropna()
            if len(fail_vals) > 0 and len(succ_vals) > 0:
                summary[f"failure_bull_{col}_avg"] = float(fail_vals.mean())
                summary[f"success_contrast_{col}_avg"] = float(succ_vals.mean())
                summary[f"{col}_diff"] = float(fail_vals.mean() - succ_vals.mean())

    summary_path = output_dir / "summary.json"
    import json

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    readme_content = f"""# H510: Bull Participation State Audit

## Objective

Determine whether existing C23/C24/C25/C26-family emissions can explain bull-market
participation failure observed by heuristic-trader.

## Context

heuristic-trader reported that strategy failure in strong bull years is mainly an
under-participation / cash-drag problem:
- Failure bull years: 2017, 2025
- Success / contrast years: 2021, 2022
- Secondary comparison years: 2019, 2024

## Method

- Reused H509 clustered panel (k=6)
- Computed yearly distributions of latent clusters and symbolic states
- Computed yearly IC by state to measure signal quality within each state
- Compared distributions across failure vs success bull years

## Key Findings

### Yearly State Distribution (Focus Years)
{_format_table(focus_years[focus_cols])}

### Yearly IC by State
{_format_table(focus_ic[ic_cols])}

### Focus Year Comparisons
{_format_table(comparisons)}

## Output Files

- `year_state_summary.csv` - Full yearly state distribution
- `yearly_ic_by_state.csv` - Yearly IC by cluster and symbolic state
- `focus_years_summary.csv` - Focus years only
- `transition_summary.csv` - Cluster transitions by year
- `focus_year_comparison.csv` - Direct comparisons
- `summary.json` - Machine-readable summary

## Conclusion

See live_state.md for interpretation.
"""

    readme_path = output_dir / "README.md"
    with open(readme_path, "w") as f:
        f.write(readme_content)

    print(f"\nArtifacts saved to: {output_dir}")
    print(f"Summary: {summary_path}")

    return str(output_dir)


def _format_table(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False) if hasattr(df, "to_markdown") else df.to_string(index=False)


def main() -> None:
    run_audit(parse_args())


if __name__ == "__main__":
    main()