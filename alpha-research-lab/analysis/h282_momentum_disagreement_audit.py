"""
H282: momentum-disagreement audit.

This tests the queued idea:
    xs_mom_disagree = xs_proba_rank - xs_reversal_1d_rank

The question is whether the disagreement between the primary momentum
signal and the 1-day reversal signal adds standalone predictive value.
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

from src.run_summary import write_run_summary
from src.standalone_signal_utils import load_s1_frame, rank_frame, spearman_stat, yearly_ic, summarize_ic

S1_PATH = REPO_ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet"
C9_PATH = REPO_ROOT / "data/features/xs_shortterm_reversal.parquet"


def _yearly_summary(frame: pd.DataFrame, feature_col: str) -> dict[str, object]:
    rows = yearly_ic(frame, feature_col, "actual")
    summary = summarize_ic(rows)
    summary["yearly"] = rows
    summary["corr_with_s1"] = spearman_stat(frame[feature_col], frame["xs_proba"])
    summary["corr_with_c9"] = spearman_stat(frame[feature_col], frame["xs_reversal_1d"])
    return summary


def main() -> None:
    s1 = load_s1_frame()[["time", "ticker", "xs_proba", "actual"]]
    c9 = pd.read_parquet(C9_PATH)
    c9["time"] = pd.to_datetime(c9["time"], errors="coerce").dt.normalize()
    c9 = c9[["time", "ticker", "xs_reversal_1d"]]

    merged = s1.merge(c9, on=["time", "ticker"], how="inner")
    merged = merged.loc[merged["time"].dt.year.between(2015, 2025)].copy()
    merged["xs_proba_rank"] = merged.groupby("time")["xs_proba"].transform(lambda s: s.rank(method="average", pct=True))
    merged["xs_reversal_1d_rank"] = merged.groupby("time")["xs_reversal_1d"].transform(lambda s: s.rank(method="average", pct=True))
    merged["xs_mom_disagree"] = merged["xs_proba_rank"] - merged["xs_reversal_1d_rank"]

    summary = _yearly_summary(merged, "xs_mom_disagree")
    candidate_corr = spearman_stat(merged["xs_mom_disagree"], merged["xs_proba"])
    c9_corr = spearman_stat(merged["xs_mom_disagree"], merged["xs_reversal_1d"])
    summary_row = {
        "feature_name": "xs_mom_disagree",
        "avg_ic": summary.get("avg_ic"),
        "pct_years_positive": summary.get("pct_years_positive"),
        "years": summary.get("years"),
        "pos_years": summary.get("pos_years"),
        "corr_with_s1": summary.get("corr_with_s1"),
        "corr_with_c9": summary.get("corr_with_c9"),
        "gate_pass": bool(
            (summary.get("avg_ic") or 0.0) > 0.01
            and (summary.get("pct_years_positive") or 0.0) >= 0.60
            and abs(candidate_corr) < 0.30
            and abs(c9_corr) < 0.30
        ),
        "yearly": summary.get("yearly"),
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "artifacts" / "portfolio_baselines"
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / f"{ts}_h282_momentum_disagreement_results.parquet"
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h282_momentum_disagreement_summary.json"
    pd.DataFrame([summary_row]).drop(columns=["yearly"]).to_parquet(results_path, index=False)

    summary_payload = {
        "verdict": "PASSED" if summary_row["gate_pass"] else "MIXED" if (summary_row["avg_ic"] or 0.0) > 0 else "FAILED",
        "best_candidate": {
            "feature_name": summary_row["feature_name"],
            "avg_ic": summary_row["avg_ic"],
            "pct_years_positive": summary_row["pct_years_positive"],
            "years": summary_row["years"],
            "pos_years": summary_row["pos_years"],
            "corr_with_s1": summary_row["corr_with_s1"],
            "corr_with_c9": summary_row["corr_with_c9"],
            "gate_pass": summary_row["gate_pass"],
        },
        "candidate_rows": int(len(merged)),
        "candidate_years": sorted(int(y) for y in merged["time"].dt.year.unique()),
    }
    details_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="signal_library_momentum_disagreement",
        name="h282_momentum_disagreement_audit",
        summary=summary_payload,
        artifacts={
            "results": str(results_path),
            "details": str(details_path),
        },
        metadata={
            "session": 111,
            "source": "xs_barrier_vol_1d_hose_full + xs_shortterm_reversal",
        },
    )

    print("H282 momentum disagreement")
    print(pd.DataFrame([summary_row]).drop(columns=["yearly"]).to_string(index=False))


if __name__ == "__main__":
    main()
