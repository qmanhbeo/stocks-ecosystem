# Session 27 Log — Signal Parking + Next Experiment Roadmap (2026-03-24)

## Objectives

1. Make a clean, documented decision on whether the XS momentum signal (H54) is production-ready.
2. Formally park it with explicit deployment conditions if not ready.
3. Plan the next experiment directions toward a library of RL-training signals.

## System State (entering)

- **Current champion:** H54 — Full HOSE Rank Portfolio (+25.52% avg edge, Sharpe 9.17, 11/11 years)
- **Honest benchmark:** H52 nested WF (+11.64% avg edge, Sharpe 1.83, 8/9 years)
- **Near-champion:** H87(alpha=0.7) (+25.03% edge, Sharpe 10.25, daily economics near-identical to H54)
- **2026 live validation:** IC +0.1323, gross positive, net slightly negative at 0.30% RT (43 days)
- **Deployment fallback rule:** H54 daily below 0.49% RT; H87 weekly above it
- **Open issue entering this session:** Is H54 production-ready? Should we keep optimizing it?

## Experiments

None run this session. Session 27 is a decision + planning session.

## Decision: H54 Is Parked, Not Production-Ready

### The case for parking

The signal is a validated **ranking feature**, not a validated **executable system**. These are different claims:

| Claim | Status |
|---|---|
| IC > 0 in walk-forward, statistically significant | CONFIRMED (11/11 years) |
| Signal alive in 2026 live holdout | CONFIRMED (IC +0.134) |
| Gross returns positive at T+1 open | CONFIRMED |
| Full fills achievable at T+1 open for all 5 names | NOT TESTED |
| Net P&L positive at realistic cost over full year | NOT CONFIRMED (partial-year net negative) |
| Signal robust to liquidity restriction | FAILS (top-50 halves IC) |
| Execution infrastructure exists | NO |

The critical unresolved issue is the T+1 open execution window. The entire alpha is concentrated in the gap between signal generation and the opening auction. The model assumes full fills at the opening price — a price, not a tradeable quantity. For mid/small-cap HOSE names, actual fill rates at open are unknown. Until this is tested with real order data, the economic claims are not realized.

### What is NOT a reason to keep optimizing

- Tweaking model hyperparameters, blending strategies, or feature variants will not close the execution gap.
- The H87 vs H54 comparison already showed diminishing returns at the signal level (Sharpe improves, edge stays flat).
- More signal research on this direction has negative expected value until the execution gap is addressed.

### Deployment conditions (to unpark)

1. Real fill data for a sample of T+1 open executions across representative names (large, mid, small cap)
2. Net P&L confirmed positive over at least one full calendar year at actual realized RT costs
3. Execution infrastructure in place (daily signal generation → order placement → fill tracking)

### What H54 is good for right now

- A validated **state feature** for RL training: IC ~0.152 means the model's predicted rank is a genuine signal
- A **benchmark** to compare new signal directions against
- A **paper portfolio monitor** using the 2026 live artifact

## Session Conclusions

1. H54 is parked. Ranking skill is real; execution feasibility is unverified. Do not treat backtest Sharpe as realizable P&L.
2. The research goal shifts: find additional orthogonal learnable signals for RL training, not more variants of xs-momentum.
3. Four new directions are defined (H89-H92), prioritized by effort and orthogonality.

## Findings To Promote

- `F53`: XS momentum signal parked. Deployment gap defined. See findings.md.

## Production System After This Session

H54 remains the best-validated signal. Status changes from "champion under active development" to "parked, monitor-only." No new production artifact.

## Next Session Priority

Start with **H90 (Volume XS features)** — lowest effort, tests a real hypothesis (volume = order-flow demand imbalance, consistent with opening auction mechanism), and uses the existing pipeline with one flag change.

If H90 is a quick kill (< 1 hour of compute), run **H91 (1-day target)** in the same session.

**Full experiment queue:**

| Experiment | Hypothesis | Effort | Orthogonality to H54 |
|---|---|---|---|
| H90 — Volume XS | Volume features add IC via order-flow signal | Low | Medium |
| H91 — 1-day target | 1-day label is purer match to T+1 open alpha | Low | Medium |
| H92 — Sector sub-models | Per-sector models beat pooled on within-sector IC | Medium | Medium |
| H89 — LLM news sentiment | LLM-extracted sentiment provides independent IC | High | High |
