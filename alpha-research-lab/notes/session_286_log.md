# Session 286 Log

**Date**: 2026-05-05
**Focus**: H405 `sector_event_lightcone`

## Summary

- Activated 12th S272/S273 queue item.
- Added `analysis/h405_sector_event_lightcone.py`.
- Tested whether sector-peer events predict returns vs ticker-only events.
- Verdict: **FAILED**. Both own-ticker and sector events negative IC.

## H405 - Sector Event Lightcone

**Hypothesis:**
Ollama event-family shocks may propagate through sector neighbors.

**Command / code:**
```bash
python alpha-research-lab/analysis/h405_sector_event_lightcone.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1)
- `data/features/news/datasets/ollama_guarded_ticker_day_features.parquet` (Ollama)
- `data/features/xs_sector_rotation_daily.parquet` (sector)

**Protocol:**
- No `2026+` rows, test years `2018-2025`
- Own-event vs sector-event intensity vs no-own-but-sector

| State | Overall IC | Positive Years |
|-------|----------|-------------|
| Own event (5d count) | -0.00481 | 1/8 |
| Sector event intensity | -0.00698 | 0/8 |
| No-own + sector (subset) | -0.00572 | - |

**Saved artifact:**
`artifacts/run_summaries/20260505_231629_sector_event_lightcone_research_branch.json`

**Verdict: FAILED**

Sector events add no signal. Both own-ticker and sector event intensity negative IC.
Confirms prior news failures - events as features are not the edge.

**Next**: H406
Source anchor: D020