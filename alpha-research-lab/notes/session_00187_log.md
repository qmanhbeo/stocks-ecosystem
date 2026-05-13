# Session 187 Log - Proprietary-Flow Conflict / Agreement Pilot (2026-04-28)

## Objective

Continue the evergreen loop with data already available on disk:
- keep the live alpha branch unchanged
- avoid `2026` predictive use
- avoid GPU / Ollama / PhoBERT training jobs
- test the next materially different flow interaction after H347: CafeF
  proprietary-desk flow and foreign/proprietary agreement or conflict states

This session stayed long-only.
It did not use `2026` for predictive tuning.

## Branch selection

H347 showed foreign-flow agreement can clean raw `C5`, but not enough to beat
the H340 order-pressure rewrite. The next honest flow branch had to change the
actor surface rather than retune foreign support around `C5`.

The proprietary-trading archive is limited: it starts on `2022-11-01`, so this
pass used a source-limited pilot protocol:
- `2022-11` through `2022-12` as feature warmup only
- `2023` dev
- `2024` validation
- `2025` confirmation
- `2026+` excluded

A pass would mean continue the branch with robustness/source-hole audits, not
signal promotion.

## Experiment

### H348 - Proprietary-Flow Conflict / Agreement

**Hypothesis:**
Proprietary-desk flow may capture a distinct local institutional actor surface,
especially when it agrees or conflicts with foreign flow.

**Command / code:**
`python analysis/h348_proprietary_flow_conflict_agreement.py`

**Inputs:**
- `data/proprietary_trading/cafef/proprietary_trading_daily.parquet`
- `data/foreign_flow/cafef/foreign_flow_daily.parquet`
- daily stock volume panels under `data/stock/`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_085350_h348_proprietary_flow_conflict_agreement_research_branch_proprietary_flow_conflict_agreement.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | no predeclared proprietary-flow feature clears the limited-source pilot |
| proprietary source rows | `50,918` | total raw rows |
| predictive source coverage | `15.58%` | rows with proprietary records over 2023-2025 stock panel |
| predictive rows | `258,375` | S1-compatible 2023-2025 panel |
| predictive tickers / dates | `394 / 748` | missing proprietary rows treated as zero |
| feature count | `8` | standalone prop ranks plus foreign/prop agreement/conflict ranks |
| best feature | `xs_prop_buy_share_5d_rank` | positive dev only |
| best dev IC | `+0.0144` | clears dev threshold |
| best validation IC | `-0.0216` | flips sign in 2024 |
| best confirmation IC | `-0.0110` | remains negative in 2025 |
| best S1 corr | `-0.0143` | orthogonal but unstable |
| passing / near features | `0 / 0` | no directionally stable feature |

**Result:**
The proprietary-flow pilot fails. The best row clears the dev threshold, but it
flips negative in validation and stays negative in confirmation. The
foreign/proprietary agreement and conflict features are also unstable or near
zero.

**Verdict: FAILED**

## Branch decision

Do not tune proprietary-flow rank variants on the current next-day S1 target.
The raw proprietary-trading surface remains available, but this pilot does not
justify a continued standalone/agreement/conflict branch under the present
data window.

If the daily side-channel branch continues, it should move to a genuinely
different contract, such as official-source bridge features or sector-specific
ownership pressure, not more proprietary-flow thresholds.

## Memory changes

Updated:
- `notes/live_state.md`
- `notes/findings-00271-00300.md`
- `notes/signal_library.md`

Added:
- `analysis/h348_proprietary_flow_conflict_agreement.py`

Durable finding:
- `F288`

No durable dead-end file exists in the current repo note convention, so the
negative proprietary-flow pilot is recorded in the active findings chunk and
signal library.

## Verification

Completed:
- `python -m py_compile analysis/h348_proprietary_flow_conflict_agreement.py`
- `python analysis/h348_proprietary_flow_conflict_agreement.py`

The script was rerun after removing a harmless pandas `FutureWarning`; the
artifact above is from the clean rerun.

## Next step

Continue the evergreen loop with a distinct branch. Do not continue H348 with
more prop-flow rank, agreement, or conflict threshold variants on the same
target.
