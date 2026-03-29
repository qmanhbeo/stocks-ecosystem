from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.additive_selector_research import load_summary_payload, resolve_summary_artifact, summary_is_skipped


def load_exit_results(summary_path: Path) -> pd.DataFrame:
    results_path = resolve_summary_artifact(summary_path, "results")
    return pd.read_parquet(results_path)


def resolve_exit_leader(summary_path: Path, *, baseline_variant: str) -> tuple[pd.DataFrame, pd.Series | None]:
    if summary_is_skipped(summary_path):
        return pd.DataFrame(), None
    results = load_exit_results(summary_path)
    promoted = results.loc[results["promoted"]].copy() if "promoted" in results.columns else pd.DataFrame()
    if not promoted.empty:
        return results, promoted.iloc[0]
    non_baseline = results.loc[results["variant"] != baseline_variant].copy()
    if non_baseline.empty:
        return results, None
    ordered = non_baseline.sort_values(
        by=[
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "variant",
        ],
        ascending=[False, False, False, True],
        ignore_index=True,
    )
    return results, ordered.iloc[0]


def resolve_exit_anchor(summary_path: Path, *, baseline_variant: str) -> tuple[pd.DataFrame, pd.Series | None]:
    if summary_is_skipped(summary_path):
        return pd.DataFrame(), None
    results = load_exit_results(summary_path)
    promoted = results.loc[results["promoted"]].copy() if "promoted" in results.columns else pd.DataFrame()
    if not promoted.empty:
        return results, promoted.iloc[0]
    baseline_rows = results.loc[results["variant"] == baseline_variant].copy()
    if baseline_rows.empty:
        return results, None
    return results, baseline_rows.iloc[0]


def extract_exit_spec(row: pd.Series | None) -> tuple[str | None, dict[str, object] | None]:
    if row is None:
        return None, None
    name = row.get("exit_rule_name")
    params = row.get("exit_rule_params")
    if pd.isna(name):
        return None, None
    if isinstance(params, dict):
        return str(name), dict(params)
    return str(name), None


def load_baseline_variant(summary_path: Path, *, default: str = "always_on_baseline") -> str:
    payload = load_summary_payload(summary_path)
    return str(payload.get("summary", {}).get("baseline_variant", default))
