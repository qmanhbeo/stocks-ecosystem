"""
H165: Selector agreement / disagreement is informative.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_meta_experiment_utils import add_common_args, load_meta_bundle, quantile_gate, run_and_persist_activation_experiment


def parse_args() -> argparse.Namespace:
    parser = add_common_args(argparse.ArgumentParser())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs, meta_state, meta_source = load_meta_bundle(args)

    jaccard = pd.to_numeric(meta_state["selector_top5_jaccard"], errors="coerce")
    overlap = pd.to_numeric(meta_state["selector_top5_overlap"], errors="coerce")
    top1_agree = pd.to_numeric(meta_state["selector_top1_agree"], errors="coerce") >= 1.0
    shared_gates = {
        "agree__top1": top1_agree,
        "agree__jaccard_q60": quantile_gate(jaccard, 0.60),
        "agree__jaccard_q70": quantile_gate(jaccard, 0.70),
        "agree__overlap_ge3": overlap >= 3.0,
        "agree__mid_disagreement": (jaccard >= 0.20) & (jaccard <= 0.60),
        "agree__top1_or_overlap_ge3": top1_agree | (overlap >= 3.0),
    }
    gates_by_selector = {selector.name: shared_gates for selector in inputs.selectors}

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_selector_agreement",
        name="h165_selector_agreement_gate",
        stem="h165_selector_agreement_gate",
        title="H165: SELECTOR AGREEMENT / DISAGREEMENT",
        extra_summary={"hypothesis": "selector agreement or disagreement contains activation information"},
    )


if __name__ == "__main__":
    main()
