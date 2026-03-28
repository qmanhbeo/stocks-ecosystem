# Session 41 Log (2026-03-28)

## Summary

Session 41 closed the last open item from the Session 40 queue and cleaned up the hand-off state.

**Net result:** H122 was run and failed, C10 was added to the RL signal matrix, and C10 was verified to remain orthogonal to the other candidate signals.

## Quick Log Inventory

I checked the experiment log coverage before continuing:

- H118-H120 are documented only as inline tests in `notes/session_39_log.md`
- H121 has full artifacts and is now the source of C10
- H113 has full fail artifacts from two runs
- H122 existed as a script but had not been run; that gap is now closed
- I did not find any H123+ logs or artifacts yet, so those are simply not created or run yet, not missing from the repo

## Experiments

### H122 — Bid-Ask Spread Proxy ❌ FAIL

**Script:** `analysis/h122_bid_ask_spread_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_120457_h122_bid_ask_spread_standalone_signal.json`

Corwin-Schultz effective spread proxy from daily H/L data.

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_spread_level_rank | -0.0097 | 2/11 | -0.066 | fail |
| xs_spread_spike_rank | -0.0301 | 1/11 | -0.062 | fail |
| xs_spread_change_5d | -0.0035 | 2/11 | -0.028 | fail |

**Verdict:** reject

**Interpretation:** the spread estimator is not useful in this market as a standalone signal. The likely failure mode is a mix of price-limit distortion, stale highs/lows, and noisy intraday extremes.

### RL Matrix Update

`data_tools/build_rl_signal_matrix.py` was updated to compute C10 inline from OHLCV, matching the H121 vectorized pattern.

**Output:** `data/features/xs_rl_signal_matrix.parquet`

**Shape:** `826,404 x 12`

**Added column:** `c10_illiq_level_rank`

Coverage after rebuild:

- `c10_illiq_level_rank`: 823,048 / 826,404 rows

### Pairwise Check: C10 vs Other Candidates

C10 stays well below the 0.30 orthogonality threshold against the existing candidates.

| Pair | Spearman rho |
|------|--------------|
| C10 vs C4 | -0.1224 |
| C10 vs C5 | +0.0313 |
| C10 vs C6 | +0.0150 |
| C10 vs C7 | +0.0044 |
| C10 vs C8 | +0.0184 |
| C10 vs C9 | +0.0012 |

## Handoff Notes

- Keep C10 in the RL matrix and the signal library
- H122 is now rejected and should stay in the rejected table
- Next tests to prioritize are H123 and H124
- The current live state is fully captured in `notes/next_steps.md`
