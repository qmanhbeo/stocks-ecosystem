"""
H280: shape+breadth confirmation audit.

This is a strict confirmation pass for the mixed H279 router.
It reuses the frozen H279 gate on the saved panel and splits the
observed rows into validation and confirmation years without retuning.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.additive_selector_research import load_summary_payload, resolve_summary_artifact
from src.run_summary import write_run_summary

H279_LATEST_SUMMARY_PATH = REPO_ROOT / "artifacts/run_summaries/latest_portfolio_router_shape_breadth.json"
VALIDATION_END_YEAR = 2024
CONFIRMATION_START_YEAR = 2025


def _summary_stats(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {"count": 0.0, "mean_adv": 0.0, "positive_rate": 0.0}
    adv = pd.to_numeric(df["future_hold_advantage"], errors="coerce").dropna()
    if adv.empty:
        return {"count": 0.0, "mean_adv": 0.0, "positive_rate": 0.0}
    return {
        "count": float(len(adv)),
        "mean_adv": float(adv.mean()),
        "positive_rate": float((adv > 0.0).mean()),
    }


def _split_label(year: int) -> str:
    if year <= VALIDATION_END_YEAR:
        return "validation"
    if year >= CONFIRMATION_START_YEAR:
        return "confirmation"
    return "ignored"


def main() -> None:
    summary_payload = load_summary_payload(H279_LATEST_SUMMARY_PATH)
    panel_path = resolve_summary_artifact(H279_LATEST_SUMMARY_PATH, "panel")
    panel = pd.read_parquet(panel_path)
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    panel["split"] = panel["time"].dt.year.map(_split_label)
    panel = panel.loc[panel["split"].isin(["validation", "confirmation"])].copy()

    fixed_shape_threshold = float(summary_payload["summary"]["stats"]["shape_threshold"])
    fixed_breadth_gap_min = float(summary_payload["summary"]["stats"]["breadth_gap_min"])
    panel["router_gate"] = (
        pd.to_numeric(panel["shape_score"], errors="coerce") >= fixed_shape_threshold
    ) & (pd.to_numeric(panel["breadth_gap"], errors="coerce") >= fixed_breadth_gap_min)
    panel["shape_gate"] = pd.to_numeric(panel["shape_score"], errors="coerce") >= fixed_shape_threshold
    panel["breadth_gate"] = pd.to_numeric(panel["breadth_gap"], errors="coerce") >= fixed_breadth_gap_min

    rows = []
    for split in ("validation", "confirmation"):
        split_frame = panel.loc[panel["split"] == split]
        rows.append({"split": split, "group": "router_gate", **_summary_stats(split_frame.loc[split_frame["router_gate"]])})
        rows.append({"split": split, "group": "shape_only", **_summary_stats(split_frame.loc[split_frame["shape_gate"]])})
        rows.append({"split": split, "group": "all_rows", **_summary_stats(split_frame)})

    results = pd.DataFrame(rows)

    validation_router = results.loc[(results["split"] == "validation") & (results["group"] == "router_gate")].iloc[0]
    validation_baseline = results.loc[(results["split"] == "validation") & (results["group"] == "all_rows")].iloc[0]
    confirmation_router = results.loc[(results["split"] == "confirmation") & (results["group"] == "router_gate")].iloc[0]
    confirmation_baseline = results.loc[(results["split"] == "confirmation") & (results["group"] == "all_rows")].iloc[0]
    confirmation_shape = results.loc[(results["split"] == "confirmation") & (results["group"] == "shape_only")].iloc[0]

    confirmation_lift = float(confirmation_router["mean_adv"] - confirmation_baseline["mean_adv"])
    validation_lift = float(validation_router["mean_adv"] - validation_baseline["mean_adv"])

    verdict = "FAILED"
    if confirmation_router["mean_adv"] > confirmation_baseline["mean_adv"]:
        verdict = "MIXED"
        if (
            validation_router["mean_adv"] > validation_baseline["mean_adv"]
            and float(confirmation_shape["mean_adv"]) > 0.0
        ):
            verdict = "PASSED"

    best_confirmation_row = (
        panel.loc[panel["split"] == "confirmation"]
        .sort_values("shape_score", ascending=False)
        .iloc[0]
        .to_dict()
    )

    summary = {
        "verdict": verdict,
        "validation_end_year": VALIDATION_END_YEAR,
        "confirmation_start_year": CONFIRMATION_START_YEAR,
        "shape_threshold": fixed_shape_threshold,
        "breadth_gap_min": fixed_breadth_gap_min,
        "validation": {
            "router": validation_router.to_dict(),
            "baseline": validation_baseline.to_dict(),
            "lift_over_baseline": validation_lift,
        },
        "confirmation": {
            "router": confirmation_router.to_dict(),
            "baseline": confirmation_baseline.to_dict(),
            "shape_only": confirmation_shape.to_dict(),
            "lift_over_baseline": confirmation_lift,
            "lift_over_shape_only": float(confirmation_router["mean_adv"] - confirmation_shape["mean_adv"]),
        },
        "best_confirmation_row": {
            "shape_score": best_confirmation_row.get("shape_score"),
            "breadth_gap": best_confirmation_row.get("breadth_gap"),
            "future_hold_advantage": best_confirmation_row.get("future_hold_advantage"),
            "router_gate": best_confirmation_row.get("router_gate"),
        },
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "artifacts" / "portfolio_baselines"
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / f"{ts}_h280_shape_breadth_confirmation_results.parquet"
    panel_path_out = out_dir / f"{ts}_h280_shape_breadth_confirmation_panel.parquet"
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h280_shape_breadth_confirmation_summary.json"
    results.to_parquet(results_path, index=False)
    panel[["time", "ticker", "split", "shape_score", "breadth_gap", "future_hold_advantage", "router_gate"]].to_parquet(
        panel_path_out, index=False
    )
    details_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="portfolio_router_shape_breadth_confirmation",
        name="h280_shape_breadth_confirmation_audit",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "panel": str(panel_path_out),
            "details": str(details_path),
        },
        metadata={
            "session": 109,
            "source_summary": str(H279_LATEST_SUMMARY_PATH.relative_to(REPO_ROOT)),
            "validation_end_year": VALIDATION_END_YEAR,
            "confirmation_start_year": CONFIRMATION_START_YEAR,
        },
    )

    print("H280 confirmation stats")
    print(results.to_string(index=False))


if __name__ == "__main__":
    main()
