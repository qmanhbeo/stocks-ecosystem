# Session 292 Log

**Date**: 2026-05-05
**Focus**: H411 `volume_triple_storm`

## Summary

- Activated Bright-Mind B23 idea (Volume Triple Storm).
- Added `analysis/h411_volume_triple_storm.py`.
- Tested Triple Storm conditions on Volume vs forward IC.
- Verdict: **FAILED**. Triple Storm does NOT amplify Volume like it amplifies C16.

## H411 - Volume Triple Storm

**Hypothesis:**
Triple Storm conditions amplify Volume signal (like C16-Triple).

**Command / code:**
```bash
python alpha-research-lab/analysis/h411_volume_triple_storm.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1 target)
- `data/features/xs_order_pressure_daily.parquet` (Volume)
- `data/stock/gia_lich_su_VNINDEX_1D.parquet` (Market)

**Protocol:**
- Test years `2018-2025`
- Triple Storm: liquid + market-down + divergence

| State | Forward IC | Note |
|-------|-----------|------|
| Volume alone | +0.07492 | Baseline |
| **Volume+Triple** | **+0.03782** | WORSE! |

**Ablation:**
| Only liquid | +0.08437 |
| Only down | +0.07690 |
| Only div | +0.03206 |

**Saved artifact:**
`artifacts/run_summaries/volume_triple_storm_research_branch.json`

**Verdict: FAILED**

- Triple Storm does NOT amplify Volume like it amplifies C16
- Ablation shows individual conditions also don't help
- C16-specific; not universal signal amplifier

**Next**: Test B24 (Price-Volume Divergence) or stop Volume experiments.

Source anchor: D022