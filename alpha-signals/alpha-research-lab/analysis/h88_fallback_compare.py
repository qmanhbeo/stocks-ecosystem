"""
H88: Compare H54 daily against H87 weekly as a higher-cost deployment fallback.

Inputs:
- H54 daily cost-stress summary
- H87(alpha=0.7) weekly cost-stress summary

Outputs:
- crossover round-trip cost where H87 weekly overtakes H54 daily
- compact saved summary for quick agent inspection
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary


H54_SUMMARY = Path(
    "artifacts/run_summaries/20260319_160504_h63_cost_stress_xs_barrier_all_probas_hose_full_cost_stress.json"
)
H87_SUMMARY = Path(
    "artifacts/run_summaries/20260319_162004_h63_cost_stress_xs_blend_h87_alpha0.7_cost_stress.json"
)

COST_POINTS = [0.003, 0.005, 0.007]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def annual_net(strategy: dict, rt_cost: float) -> float:
    return float(strategy["avg_gross_annual"]) - float(strategy["avg_trades_yr"]) * rt_cost


def main():
    h54_payload = load_json(H54_SUMMARY)
    h87_payload = load_json(H87_SUMMARY)

    h54_daily = h54_payload["summary"]["daily_h1"]
    h87_weekly = h87_payload["summary"]["weekly_h5"]

    gross_gap = float(h54_daily["avg_gross_annual"]) - float(h87_weekly["avg_gross_annual"])
    turnover_gap = float(h54_daily["avg_trades_yr"]) - float(h87_weekly["avg_trades_yr"])
    crossover_rt = gross_gap / turnover_gap if turnover_gap > 0 else None

    print("\nH88: HIGHER-COST FALLBACK COMPARISON")
    print("=" * 72)
    print(
        f"H54 daily H=1: gross_ann={float(h54_daily['avg_gross_annual'])*100:+.2f}% | "
        f"trades/yr={float(h54_daily['avg_trades_yr']):.2f} | "
        f"breakeven={float(h54_daily['exact_breakeven_rt'])*100:.2f}% RT"
    )
    print(
        f"H87 weekly H=5: gross_ann={float(h87_weekly['avg_gross_annual'])*100:+.2f}% | "
        f"trades/yr={float(h87_weekly['avg_trades_yr']):.2f} | "
        f"breakeven={float(h87_weekly['exact_breakeven_rt'])*100:.2f}% RT"
    )
    if crossover_rt is not None:
        print(f"\nCrossover cost: {crossover_rt*100:.2f}% RT")

    rows = []
    print(f"\n{'RT cost':>8}  {'H54 daily':>10}  {'H87 weekly':>11}  {'winner':>10}")
    print("  " + "-" * 48)
    for cost in COST_POINTS:
        h54_net = annual_net(h54_daily, cost)
        h87_net = annual_net(h87_weekly, cost)
        winner = "H54_daily" if h54_net >= h87_net else "H87_weekly"
        print(f"  {cost*100:>6.2f}%  {h54_net*100:>+9.2f}%  {h87_net*100:>+10.2f}%  {winner:>10}")
        rows.append(
            {
                "rt_cost": cost,
                "h54_daily_ann_net": round(h54_net, 6),
                "h87_weekly_ann_net": round(h87_net, 6),
                "winner": winner,
            }
        )

    recommendation = (
        "H54_daily_below_crossover_H87_weekly_above"
        if crossover_rt is not None
        else "no_crossover_computed"
    )

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    summary_path = write_run_summary(
        ts=ts,
        mode="fallback_compare",
        name="h88_h54_daily_vs_h87_weekly",
        summary={
            "h54_daily": {
                "avg_gross_annual": float(h54_daily["avg_gross_annual"]),
                "avg_trades_yr": float(h54_daily["avg_trades_yr"]),
                "exact_breakeven_rt": float(h54_daily["exact_breakeven_rt"]),
            },
            "h87_weekly": {
                "avg_gross_annual": float(h87_weekly["avg_gross_annual"]),
                "avg_trades_yr": float(h87_weekly["avg_trades_yr"]),
                "exact_breakeven_rt": float(h87_weekly["exact_breakeven_rt"]),
            },
            "crossover_rt": round(crossover_rt, 6) if crossover_rt is not None else None,
            "comparison_rows": rows,
            "recommendation": recommendation,
        },
        artifacts={
            "h54_cost_summary": str(H54_SUMMARY),
            "h87_cost_summary": str(H87_SUMMARY),
        },
        metadata={"cost_points": COST_POINTS},
    )
    print(f"\nRun summary saved to {summary_path}")


if __name__ == "__main__":
    main()
