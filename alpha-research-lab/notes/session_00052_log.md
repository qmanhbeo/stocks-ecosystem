# Session 52 Log

## Objective
Wrap the session with an honest live long-only paper-trade attempt:

1. refresh stock data to the latest market close
2. extend live `S1` to the latest trading date
3. rebuild or ad hoc compute the latest `full_library` inputs
4. emit a real paper-trade recommendation only if the data stack is internally consistent

Hard rule remained unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions

## What happened

### Dependency audit
Checked the files needed for a live `full_library` recommendation.

Observed:
- `data/features/xs_rl_signal_matrix.parquet` still ends at `2025-12-31`
- `data/features/xs_barrier_vol_1d_hose_full.parquet` still ends at `2025-12-31`
- `data/features/xs_open_close_asymmetry.parquet` still ends at `2025-12-31`
- `data/features/xs_insider_quality_features.parquet` still ends at `2025-12-31`
- stock-derived helper features such as sector rotation / price-limit / volume-zscore were newer, but not enough to reconstruct the whole live stack by themselves
- existing live `S1` file `data/features/xs_live_validation_h54_2026.parquet` only ran through `2026-03-11`

### Refresh attempt
Tried to refresh stock data for the live paper-trade path.

Operational facts:
- an initial recent-window refresh failed on network access while using `--overwrite`
- `VNINDEX` had to be restored explicitly after that failed attempt
- later refreshes left the local `data/stock/` surface in a mixed state:
  - many tickers now reach `2026-03-27`
  - some remain stale or truncated
  - `VNINDEX` currently only spans a recent slice rather than a full-history file

Representative observed state:
- `AAA`: healthy long history through `2026-03-27`
- `BCG`: stale / truncated, ending `2025-10-08`
- `VNINDEX`: recent slice only, not a full-history file

### Live scorer rerun failure
Tried to rerun:

```bash
conda run -n stocks python analysis/h75_2026_holdout.py --no-vix-filter --save-probas data/features/xs_live_validation_h54_2026.parquet
```

Result:
- failed with `ValueError: No objects to concatenate`

Interpretation:
- the current refreshed stock set is not historically consistent enough for the live scorer to build its required feature frames
- this is an operational data-integrity blocker, not a model-quality verdict

### Ad hoc live recovery
After the official live scorer failed, the session recovered a workable live path by:

- locating a local full-history `VNINDEX` backup at:
  - `../media-output/signal-xs-momentum/data/stock/gia_lich_su_VNINDEX_1D.parquet`
- merging that backup with the refreshed root `VNINDEX` slice to restore benchmark continuity through `2026-03-27`
- rebuilding live `S1` for the full 2026 slice on the fly
  - result: `19,242` scored 2026 rows across `55` dates through `2026-03-27`
- rebuilding the 2026 slices of `C4-C14` on the fly from raw stock / insider / sector / price-limit / volume data
- scoring the latest close under `full_library + k5_r5_eq`

### Live paper-trade state produced
Latest signal date:
- `2026-03-27`

Historical cadence interpretation:
- `k5_r5_eq` did **not** rebalance on that signal date

Running book after the `2026-03-27` execution:
- `ANV`
- `PTB`
- `PTL`
- `VSI`
- cash: `19.57%`

Fresh-entry top-5 snapshot from the same close:
- `PTB`
- `PAC`
- `VNG`
- `APG`
- `DTL`

This was an honest live paper-trade answer, but it was produced through a one-off local recovery path rather than the official repo pipeline.

## Conclusion
The official live pipeline is still operationally incomplete, but the session did end with a valid ad hoc paper-trade state for the `2026-03-27` close.

Current reality at the end of Session 52:
- the canonical root `VNINDEX` parquet was still not a proper full-history file
- the official live `S1` artifact was still stale until the canonical pipeline could be rerun
- the live recommendation itself was known and documented

Post-session update:
- root `data/stock/gia_lich_su_VNINDEX_1D.parquet` has since been refreshed back to full history through `2026-03-27`
- that removes the benchmark file itself as the active blocker
- the remaining operational question is whether the broader refreshed stock universe is now historically consistent enough for the official live scorer

Date clarification:
- `2026-03-28` is a Saturday
- the latest actionable close in the refreshed stock data is `2026-03-27`
- any real recommendation would need to be generated from that Friday close for the next trading session

## Durable takeaway
Recent-window refreshes are not operationally safe for live scoring when downstream models need long lookback history. Refreshing raw stock files without preserving historical continuity can silently invalidate live feature generation and block paper-trade deployment.

A second practical takeaway from this session:
- if the root `VNINDEX` file is truncated, the workspace currently has a local fallback copy under `../media-output/signal-xs-momentum/`
- that fallback is useful for emergency recovery, but it should not replace restoring the canonical root data surface properly

## Next steps
Start the next session in this order:

1. Record the next market-session result against the paper-trade book: `ANV`, `PTB`, `PTL`, `VSI`, cash `19.57%`
2. Verify full historical continuity across root `data/stock/`; root `VNINDEX` is now restored, but the rest of the raw surface still needs validation
3. Verify lookback sufficiency before rerunning any live scorer
4. Rerun `analysis/h75_2026_holdout.py` against the restored canonical benchmark and refresh the official live `S1` artifact
5. Persist the ad hoc live-assembly workflow into a real repo script if live paper trades are going to continue
6. After the operational path is stable, resume the research queue with:
   - `H151`: narrow tradability-conditioned composite centered on `s1_proba`, `c7`, `c12`, `c13`, `c10`, with `c8` optional
   - `H152`: new long-only alpha search explicitly defined inside tradable / liquidity-opening states
