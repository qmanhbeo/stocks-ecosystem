from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_alpha import BENCHMARK_PATH, RL_MATRIX_PATH, STOCK_DIR, TRADABILITY_PATH
from src.activation_meta import ACTIVATION_META_PATH
from src.entry_alpha import (
    ENTRY_ALPHA_CANDIDATE_PANEL_PATH,
    ENTRY_ALPHA_LABELS_CYCLE5_PATH,
    build_entry_candidate_panel,
    build_entry_labels,
    load_entry_alpha_inputs,
    persist_entry_alpha_artifacts,
)
from src.run_summary import write_run_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H238: build the stock-specific entry-alpha candidate panel")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--activation-meta", type=str, default=str(ACTIVATION_META_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-m-max", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--label-edge-buffer", type=float, default=0.0)
    parser.add_argument("--candidate-panel-out", type=str, default=str(ENTRY_ALPHA_CANDIDATE_PANEL_PATH))
    parser.add_argument("--labels-out", type=str, default=str(ENTRY_ALPHA_LABELS_CYCLE5_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = load_entry_alpha_inputs(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        activation_meta_path=Path(args.activation_meta),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        strategy_name=str(args.strategy),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
    )
    candidate_panel = build_entry_candidate_panel(
        inputs,
        top_m_max=int(args.top_m_max),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
    )
    labels = build_entry_labels(
        candidate_panel,
        price_panel=inputs.price_panel,
        benchmark_open=inputs.benchmark_open,
        horizon_signal_steps=int(args.rebalance_every),
        signal_dates=sorted(pd.to_datetime(inputs.matrix["time"]).drop_duplicates()),
        round_trip_cost=float(args.round_trip_cost),
        label_edge_buffer=float(args.label_edge_buffer),
    )

    candidate_panel_path = Path(args.candidate_panel_out)
    labels_path = Path(args.labels_out)
    persist_entry_alpha_artifacts(
        candidate_panel,
        labels,
        candidate_panel_path=candidate_panel_path,
        labels_path=labels_path,
    )

    labeled = labels["buy_now_label"].notna()
    positive_rate = (
        float(pd.to_numeric(labels.loc[labeled, "buy_now_label"], errors="coerce").mean())
        if bool(labeled.any())
        else None
    )
    summary = {
        "strategy_name": inputs.strategy_name,
        "selector_name": inputs.selector_name,
        "candidate_rows": int(len(candidate_panel)),
        "label_rows": int(len(labels)),
        "dates": int(candidate_panel["time"].nunique()),
        "tickers": int(candidate_panel["ticker"].nunique()),
        "top_m_max": int(args.top_m_max),
        "top_k": int(args.top_k),
        "rebalance_every": int(args.rebalance_every),
        "labeled_rows": int(labeled.sum()),
        "unlabeled_rows": int((~labeled).sum()),
        "buy_now_positive_rate": positive_rate,
        "activation_meta_source": inputs.activation_meta_source,
        "candidate_panel_path": str(candidate_panel_path),
        "labels_path": str(labels_path),
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    write_run_summary(
        ts=ts,
        mode="entry_alpha_candidate_panel",
        name="h238_entry_alpha_candidate_panel",
        summary=summary,
        artifacts={
            "candidate_panel": str(candidate_panel_path),
            "labels": str(labels_path),
        },
        metadata={
            "matrix": str(args.matrix),
            "tradability": str(args.tradability),
            "stock_dir": str(args.stock_dir),
            "benchmark": str(args.benchmark),
            "activation_meta": str(args.activation_meta),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "strategy": str(args.strategy),
            "round_trip_cost": float(args.round_trip_cost),
            "required_holding_age": int(args.required_holding_age),
            "initial_notional_vnd": float(args.initial_notional_vnd),
            "label_edge_buffer": float(args.label_edge_buffer),
        },
    )

    print("\nH238: ENTRY ALPHA CANDIDATE PANEL")
    print(f"strategy={inputs.strategy_name} | selector={inputs.selector_name}")
    print(f"candidate_rows={summary['candidate_rows']:,} | labels={summary['label_rows']:,}")
    print(f"dates={summary['dates']:,} | tickers={summary['tickers']:,} | labeled_rows={summary['labeled_rows']:,}")
    if summary["buy_now_positive_rate"] is not None:
        print(f"buy_now_positive_rate={float(summary['buy_now_positive_rate']):.4f}")
    print(f"candidate_panel={candidate_panel_path}")
    print(f"labels={labels_path}")


if __name__ == "__main__":
    main()
