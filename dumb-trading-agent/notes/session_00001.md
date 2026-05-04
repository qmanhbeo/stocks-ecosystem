# Session 00001

Date: 2026-05-04

## What Changed

Created `dumb-trading-agent/` folder and initialized memory system:
- `README_for_AGENTS.md`
- `notes/live_state.md`
- `notes/sessions_compact.md` (this file)
- `notes/findings_compact.md`
- `notes/deadends_compact.md`

## Session 1 Activity — Signal Discovery

Read contracts from `alpha-research-lab/`:
- Signal library at `notes/signal_library.md` (primary reference)
- Live state at `notes/live_state.md` (current best signals)

Key signals identified from `data/features/xs_rl_signal_matrix.parquet`:
- **S1 (primary):** Cross-sectional relative momentum, IC +0.149
- **C4:** Open/close asymmetry 5d, IC +0.022
- **C5:** Insider relative size 5d, IC +0.037
- **C6:** Contrarian intra-sector 5d, IC +0.030
- **C7:** Price ceiling count 5d, IC +0.012

Also available:
- C8-C14 additional signals
- Activation state surfaces
- Order pressure (C16)
- Insider quality features

Created reusable import script: `signals.py`
- Loads RL signal matrix (14 signals)
- Loads activation state/meta
- Loads order pressure (C16)
- Loads insider features
- Date range: 2015-01-05 to 2026-03-31
- 397 unique tickers

## Results

`signals.py` tested successfully. 846,520 rows loaded.

## Next Exact Step

Wait for user to define dumb agent strategy (random vs fixed score ranking).

## Durable Promotion

None yet.