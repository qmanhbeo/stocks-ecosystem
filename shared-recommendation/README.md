# Shared Recommendation

Shared model-agnostic recommendation contracts for the stocks workspace.

Scope:

- artifact path and schema registry
- adapter and policy interfaces
- candidate-table generation engine
- canonical recommendation artifact writing

Registered shared research artifacts now include the C16 order-pressure feature
surface at `data/features/xs_order_pressure_daily.parquet`. It is path/schema
metadata only; recommendation or RL consumers must opt in explicitly before
using it.

Non-goals:

- model training
- portfolio backtesting
- execution simulation

Those remain in the owning repos. This package standardizes the inference boundary only.
