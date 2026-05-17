# Session 339 - 2026-05-17

### H526 - Exit Timing Discovery
**Hypothesis:**
Test if holding-duration (time-since-entry into active state C23) or exit conditions (C24 trigger) predict different realized returns. Entry states are well-tested; exit/timing is the unexplored half.

**Command / code:**
`python analysis/h526_exit_timing_discovery.py`

**Inputs:**
- S1 panel (xs_barrier_vol_1d_hose_full.parquet) 2015-2025
- C16 signals (xs_order_pressure_daily.parquet): order_volume_ratio_rank

**Saved artifact:**
- `artifacts/run_summaries/20260517_142504_exit_timing_discovery_research_branch.json`

| Metric | Value | Note |
|--------|-------|------|
| Baseline IC | 0.1277 | all rows |
| Fresh entry IC | 0.1693 | day 1 in C23 |
| Sustained C23 IC | 0.1712 | day 2+ in C23 |
| Fresh vs sustained lift | -0.0020 | essentially NO difference |
| Day 4+ IC | 0.1697 | sustained better |
| Day 2-3 IC | 0.1424 | weaker (only 788 rows) |
| Exit signal IC | 0.1386 | first day exiting C23 |
| C24 entry | 0 rows | no ceiling data in dataset |

**Result:**
- **FAILED**: Exit timing does NOT predict different IC
- Both fresh entry and sustained positions beat baseline significantly (+0.042 lift)
- The difference between them is only 0.002 IC points - essentially noise
- Exit (first day out of C23) is weaker (IC 0.1386) than being in C23
- Interpretation: Holding duration doesn't matter much; the signal works equally well at entry and as a sustained position

**Verdict: FAILED** - No meaningful exit timing effect found.

**Next step:**
- Try next Eureka idea: Quiet-State Inverse Alpha (are QUIET stocks in active markets contrarian?)
- Or try Multi-Signal Day Superposition (OR of any active state vs single state)