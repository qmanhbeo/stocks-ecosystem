# Phase 4C targeted extension protocol

**Experiment ID:** `rl-trade-episode-phase4c-target-alignment-20261025`

**Protocol commit:** recorded in the run manifest before execution.

**Source checkout:** `/home/manh/stocks-ecosystem`, reviewed read-only at
`3b7201f8d4fedcf690178368cef8e9a2b0d993bb`.

## Gap and question

H93 and H356 test mostly one-day cross-sectional close-to-close outcomes; neither
tests the exact Phase 4A next-open trade reward or its SELL-versus-HOLD choice.
Phase 4C will measure whether the *existing* observations associate with those
outcomes. It will not fit a new predictive model, select new features, train PPO,
or tune a policy.

## Frozen data and feature contract

- Reuse the Phase 4A read-only preparation path and its 12 training tickers plus
  3 unseen tickers. Preserve the 2015-2019 training, 2020-2022 validation, and
  2023-2025 exploratory partitions.
- `prepare_stock()` enforces the 2025-12-31 cutoff before feature construction;
  causal history before each partition may warm rolling features. No 2026 value
  or statistic may enter a feature, sample, or result.
- Use the exact committed nine normalized market fields, S1/C16 values and
  availability bits, plus the five Phase 4A state fields. The audit inventory
  documents why the implementation has nine market fields despite the request's
  count of eight.
- Treat prices as dividend-adjusted under the user's Phase 4A assumption. Use
  shared OHLCV and tradability files read-only.

## Targets and execution

For an OUT state observed at close index `t`, an entry action fills at
`open[t+1]`. For `h ∈ {3, 10, 20}` trading intervals, the fixed-hold exit fills
at `open[t+1+h]` after an OUT decision at close `t+h`. The label is the exact
unclipped environment reward:

`R_h = (252 / h) * ln(open[t+1+h] / open[t+1]) - ln(1.07)`.

Include a sample only when the next-open buy and exact-horizon sell flags are
legal and the full target stays inside its chronological partition.

For an IN state at close `t`, create hypothetical entry ages `a ∈ {3, 10, 20}`.
The entry fill is `open[t-a]` from a legal buy at close `t-a-1`. Compare SELL
now at `open[t+1]` with HOLD for `h ∈ {3, 10, 20}` more intervals and sell at
`open[t+h+1]`. The target is the exact terminal reward after HOLD minus the
exact terminal reward after SELL now, using total holding intervals `a+1` and
`a+h+1`. Require both sell actions to be legal. Construct the five state
features exactly as Phase 4A does; this synthetic audit sets waiting duration
to zero and episode duration to `a+1` steps.

## Analysis and interpretation

- No model fitting. Calculate Spearman association separately within each
  ticker-calendar-year for each feature/target pair; require at least 40 valid
  rows and nonconstant values. This is a within-stock temporal association,
  distinct from Alpha Lab's cross-sectional daily IC.
- Report equal-ticker-weighted means, medians, positive ticker-year fraction,
  sample counts, and 95% hierarchical ticker/year-block bootstrap intervals
  (2,000 draws, seed `94331`). Keep training-universe and unseen tickers
  separate. Do not treat overlapping observations or trades as independent.
- This fixed-horizon association is not a policy backtest. It cannot establish
  calibrated probabilities, interaction value, tradable net profitability, or
  a PPO learning failure mechanism by itself.
- H2's broad predictive-information verdict will use the existing S1/C16
  out-of-time evidence plus this aligned audit. If broad one-day evidence is
  positive but these trade-aligned associations are weak/mixed, report that
  distinction rather than relabeling the broad evidence.

## Run artifacts

The implementation commit SHA, config hash, prepared per-ticker input hashes,
date cutoff, sample counts, and run date will be written to
`phase4c_metrics.json`. Outputs stay under
`RL-trading-agent/research/trade_episode/phase4c/results/`; no shared data,
Alpha Lab output, or checkpoint is written.
