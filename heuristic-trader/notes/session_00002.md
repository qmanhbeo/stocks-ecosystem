# Session 00002

Date: 2026-05-04

## What Changed

Set up trading constraints from RL-trading-agent:

- Created `constraints.py` mirroring `shared-market-rules/`:
  - ExecutionPolicy: decision_timing=close_t, entry_timing=open_t_plus_1
  - Price limit: ±7%
  - Settlement: T+2
  - Minimum hold days: 3 (earliest sell at T+3 fill)
  - Buy/sell blocking rules on zero volume, ceiling, floor
  - TradabilityColumns dataclass
  - earliest_sell_step_after_entry helper
  - Portfolio and Holding classes

Added from full shared-market-rules review:
  - TradabilityColumns for column naming consistency
  - earliest_sell_step_after_entry() function
  - Fixed Holding.holding_age property bug (self_time -> self.entry_time)

Constraints verified:
- `python3 constraints.py` runs successfully

## Results

Vietnam market constraints implemented:
- Price limit: ±7%
- Settlement: T+2
- Min hold days: 3
- Decision timing: close_t
- Entry timing: open_t_plus_1

## Next Exact Step

Wait for user to define dumb agent strategy (random vs fixed score ranking).

## Durable Promotion

- Constraints module created for reuse