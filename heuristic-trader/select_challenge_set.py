#!/usr/bin/env python3
"""
Select baseline + challenger from signal sweep decisions.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from risk_policy import DEFAULT_RISK_POLICY, evaluate_strategy_row, policy_dict


ROOT = Path(__file__).resolve().parent
ARTIFACTS_DIR = ROOT / "artifacts"
SWEEP_DIR = ARTIFACTS_DIR / "signal_sweeps"
CHALLENGE_DIR = ARTIFACTS_DIR / "challenge_sets"
DEFAULT_BASELINE = "ctrl_blend_70_30_depth5"


def _find_latest_sweep() -> Path:
    runs = sorted([p for p in SWEEP_DIR.glob("20*") if p.is_dir()], reverse=True)
    if not runs:
        raise FileNotFoundError(f"No sweep runs found under {SWEEP_DIR}")
    return runs[0]


def _select_challenger(
    df: pd.DataFrame,
    baseline: str,
    *,
    selection_mode: str = "strict",
) -> tuple[str | None, str]:
    if selection_mode not in {"strict", "research", "any"}:
        raise ValueError(f"Unknown selection_mode: {selection_mode}")

    promote = df[(df["strategy_name"] != baseline) & (df["decision_label"] == "PROMOTE_CANDIDATE")]
    if len(promote) > 0:
        best = promote.sort_values(["mean_excess_return", "mean_annualized_return"], ascending=[False, False]).iloc[0]
        return str(best["strategy_name"]), "top PROMOTE_CANDIDATE by mean_excess_return"

    if selection_mode == "strict":
        return None, "no strict-eligible challenger (no PROMOTE_CANDIDATE rows)"

    research = df[(df["strategy_name"] != baseline) & (df["decision_label"] == "RESEARCH_ONLY")]
    if len(research) > 0:
        best = research.sort_values(["mean_excess_return", "mean_annualized_return"], ascending=[False, False]).iloc[0]
        return str(best["strategy_name"]), "fallback top RESEARCH_ONLY by mean_excess_return"

    if selection_mode == "research":
        return None, "no challenger in strict/research tiers"

    fallback = df[df["strategy_name"] != baseline]
    if len(fallback) > 0:
        best = fallback.sort_values(["mean_excess_return", "mean_annualized_return"], ascending=[False, False]).iloc[0]
        return str(best["strategy_name"]), "fallback top non-baseline by mean_excess_return"
    return None, "no eligible challenger"


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select baseline and challenger from sweep outputs.")
    parser.add_argument("--sweep-dir", type=str, default="", help="Optional explicit sweep run directory.")
    parser.add_argument("--baseline", type=str, default=DEFAULT_BASELINE)
    parser.add_argument("--output-dir", type=str, default="", help="Optional explicit output directory.")
    parser.add_argument(
        "--selection-mode",
        type=str,
        choices=["strict", "research", "any"],
        default="strict",
        help="strict=only PROMOTE_CANDIDATE; research=allow RESEARCH_ONLY fallback; any=allow non-baseline fallback.",
    )
    parser.add_argument(
        "--allow-empty-challenge",
        action="store_true",
        help="Do not fail command when no challenger is found for the selected mode.",
    )
    return parser


def main() -> None:
    args = create_argument_parser().parse_args()
    sweep_dir = Path(args.sweep_dir) if args.sweep_dir else _find_latest_sweep()
    decisions_path = sweep_dir / "signal_sweep_decisions.csv"
    if not decisions_path.exists():
        raise FileNotFoundError(f"Missing decisions file: {decisions_path}")

    decisions = pd.read_csv(decisions_path)
    if decisions.empty:
        raise RuntimeError("Decisions file is empty")

    baseline = str(args.baseline)
    baseline_rows = decisions[decisions["strategy_name"] == baseline]
    if len(baseline_rows) == 0:
        raise ValueError(f"Baseline '{baseline}' not found in sweep decisions.")
    baseline_row = baseline_rows.iloc[0]

    challenger, challenger_reason = _select_challenger(
        decisions,
        baseline=baseline,
        selection_mode=str(args.selection_mode),
    )

    out_dir = Path(args.output_dir) if args.output_dir else CHALLENGE_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline_gates = evaluate_strategy_row(baseline_row, policy=DEFAULT_RISK_POLICY)
    challenger_row = decisions[decisions["strategy_name"] == challenger].iloc[0] if challenger else None
    challenger_gates = evaluate_strategy_row(challenger_row, policy=DEFAULT_RISK_POLICY) if challenger_row is not None else {}

    strict_candidate_count = int(
        len(
            decisions[
                (decisions["strategy_name"] != baseline)
                & (decisions["decision_label"] == "PROMOTE_CANDIDATE")
            ]
        )
    )
    ready_for_shadow = bool(challenger_row is not None)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_sweep_dir": str(sweep_dir),
        "baseline_strategy": baseline,
        "challenger_strategy": challenger,
        "challenger_selection_reason": challenger_reason,
        "selection_mode": str(args.selection_mode),
        "strict_candidate_count": strict_candidate_count,
        "has_strict_candidate": strict_candidate_count > 0,
        "ready_for_shadow": ready_for_shadow,
        "risk_policy": policy_dict(DEFAULT_RISK_POLICY),
        "baseline_gates": baseline_gates,
        "challenger_gates": challenger_gates,
    }
    with open(out_dir / "challenge_set.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    rows = [baseline_row.to_dict()]
    if challenger_row is not None:
        rows.append(challenger_row.to_dict())
    pd.DataFrame(rows).to_csv(out_dir / "challenge_strategies.csv", index=False)

    report_lines = [
        "# Challenge Set",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Source sweep: `{payload['source_sweep_dir']}`",
        f"- Baseline: `{baseline}`",
        f"- Challenger: `{challenger}`",
        f"- Challenger reason: {challenger_reason}",
        f"- Selection mode: `{payload['selection_mode']}`",
        f"- Strict candidate count: `{strict_candidate_count}`",
        f"- Ready for shadow: `{ready_for_shadow}`",
        "",
        "## Baseline Gates",
    ]
    for k, v in baseline_gates.items():
        report_lines.append(f"- {k}: {v}")
    if challenger_row is not None:
        report_lines.append("")
        report_lines.append("## Challenger Gates")
        for k, v in challenger_gates.items():
            report_lines.append(f"- {k}: {v}")
    (out_dir / "README.md").write_text("\n".join(report_lines), encoding="utf-8")

    if challenger_row is None and not bool(args.allow_empty_challenge):
        raise RuntimeError(
            "No challenger selected for current mode. "
            "Use --selection-mode research|any or --allow-empty-challenge to bypass."
        )

    print(f"[done] challenge_set={out_dir}")


if __name__ == "__main__":
    main()
