# Execution Reality

This is the canonical execution and tradability contract for the stocks workspace.

## Trading Timeline

- Signal is observed at `close[T]`
- Order is submitted after `close[T]`
- Entry fills at `open[T+1]`
- Under Vietnam's minimum `T+2.5` hold convention, a position bought at `open[T+1]`
  cannot be sold before `close[T+3]`
- In the RL environments, sells still execute next open, so the earliest exit fill is `open[T+4]`

The public concept is settlement / earliest sellability. `min_hold_days` is a legacy implementation detail in some RL code paths and must not be treated as the canonical market rule.
If an RL config requests a lower hold threshold, it must be clamped upward to this market floor rather than weakening the rule.

## Strict Core Constraints

These are the shared v1 defaults across research and RL:

- `settlement_lag_days = 2`
- first legal sell decision after a buy at `open[T+1]` is `close[T+3]`
- earliest exit fill is `open[T+4]`
- `earliest_sell_fill_offset_from_entry_open = 3`
- zero-volume day blocks buys
- zero-volume day blocks sells
- ceiling day blocks buys
- floor day blocks sells

## Daily Tradability Artifact

Producer:
- `alpha-research-lab/data_tools/build_tradability_flags.py`

Output:
- `data/features/execution/tradability_daily.parquet`

Columns:
- `time`
- `ticker`
- `has_volume`
- `is_ceiling`
- `is_floor`
- `can_buy_next_open`
- `can_sell_next_open`

## Shared Code

The canonical rule implementation lives in:
- `shared-market-rules/shared_market_rules/`

Both `alpha-research-lab` and `RL-trading-agent` must import these definitions directly instead of re-deriving the rules separately.
