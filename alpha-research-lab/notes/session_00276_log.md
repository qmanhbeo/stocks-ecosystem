# Session 276 Log

**Date**: 2026-05-05
**Focus**: H395 `weak_signal_quorum_sleeve`

## Summary

- Activated the second S272/S273 eureka queue item.
- Added `analysis/h395_weak_signal_quorum_sleeve.py`.
- Tested whether train-selected low-correlation weak votes can form a stronger
  composite signal than any component or random weak basket.
- Verdict: **PASSED as a strong composite RL-state candidate, not a new
  independent primitive signal**.

## H395 - Weak Signal Quorum Sleeve

**Hypothesis:**
Signals with IC around `0.01-0.05` should not be discarded. Independent weak
votes may become a strong context when they agree, as long as the quorum is
selected using only prior years and remains low-correlation to S1/C16 parents.

**Command / code:**
```bash
python alpha-research-lab/analysis/h395_weak_signal_quorum_sleeve.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/xs_order_pressure_daily.parquet`
- `data/features/news/datasets/news_daily_features.parquet`
- VNINDEX close through `src/standalone_signal_utils.py`

**Protocol:**
- No `2026+` rows.
- Start year `2016`, rolling train-before-test folds, test years `2019-2025`.
- Candidate votes were predeclared:
  C4-C14 weak library votes, official-supported delay, H364 positive news,
  observable VNI-down-2d, January-first-10, and Monday.
- Per test year, a component was eligible only if prior years showed:
  train avg IC `>= +0.005`, positive-year share `>= 60%`, and train absolute
  Spearman correlation `< 0.30` to both S1 and C16.
- Test-year quorum used equal weights only; no fitted component weights.
- Random control: 200 same-size random weak baskets from the low-correlation
  pool in each fold.

**Saved artifact:**
`artifacts/run_summaries/20260505_171827_h395_weak_signal_quorum_sleeve_research_branch_weak_signal_quorum_sleeve.json`

| Metric | Value | Note |
|--------|-------|------|
| Quorum avg IC | `+0.05826` | `7 / 7` positive test years |
| Corr with S1 | `+0.27541` | below `0.30`, but close |
| Corr with C16 | `-0.00685` | independent from order pressure |
| Random weak-basket mean IC | `+0.03748` | quorum lift `+0.02078` |
| Best component avg IC | `+0.03081` | quorum lift `+0.02745` |
| S1 avg IC on same folds | `+0.11663` | parent benchmark, not expected to beat |
| C16 avg IC on same folds | `+0.07711` | parent benchmark |
| 2025 quorum IC | `+0.06032` | confirmation year positive |

**Selected-component pattern:**
Stable selected votes were mostly C-library atoms:
`C4`, `C6`, `C8`, `C9`, `C10`, `C11`, `C12`, `C13`, `C14`, plus
`official_supported_delay`. `C7` and `C5` entered some folds. H364 positive
news and calendar votes were positive/weak or negative but did not pass the
train selection gate.

**Result:**
The weak-vote quorum passed the predeclared strong composite gate. It cleared
IC `> 0.05`, was positive every test year, stayed under the S1/C16 parent-corr
bar, and beat both random weak baskets and the best individual component.

Important caveat: this is not a new independent primitive. It is a composite
of existing candidate signals and one official-delay context vote. Treat it as
an RL aggregate/sleeve candidate and a strong argument not to throw away weak
IC `0.01-0.05` evidence.

**Verdict: PASSED**

**Next action:**
Continue to `parent_echo_residual_harvester`. The immediate question is whether
H395's composite survives residualization or is mostly a controlled aggregate
of already-known C-library atoms.

## Closeout

- Saved artifact was read before the verdict.
- Branch status changed to passed offline/composite signal-library evidence.
- No live branch changed.
- Memory write-back done in live state, compact notes, findings, and signal
  library.
- `2026+` data was avoided.
- No heavy job remains active.
