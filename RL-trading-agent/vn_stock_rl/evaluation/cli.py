from __future__ import annotations

from typing import Optional

from vn_stock_rl.evaluation.args import namespace_to_evaluate_kwargs, parse_args
from vn_stock_rl.evaluation.metadata import _merge_env_overrides
from vn_stock_rl.evaluation.reporting import _extract_trades, analyze_trades, create_plots
from vn_stock_rl.evaluation.runner import evaluate_model


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    df_history, stats = evaluate_model(**namespace_to_evaluate_kwargs(args))

    if not args.metrics_only:
        analyze_trades(
            df_history,
            args.output,
            buy_fee_rate=float(stats.get("buy_fee_rate", 0.0)),
            sell_fee_rate=float(stats.get("sell_fee_rate", 0.0)),
            capital_gains_tax_rate=float(stats.get("capital_gains_tax_rate", 0.0)),
        )

    print("\n" + "=" * 60)
    print("Evaluation complete!")
    print("=" * 60)
    return 0


__all__ = [
    "main",
    "evaluate_model",
    "_extract_trades",
    "_merge_env_overrides",
    "create_plots",
    "analyze_trades",
]


if __name__ == "__main__":
    raise SystemExit(main())
