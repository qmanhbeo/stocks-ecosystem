# Session 192 Log - H340 Entry-Label Transfer Audit (2026-04-28)

## Objective

Continue the evergreen loop after H352 narrowed event-v2 to offline evidence:
- keep the live alpha branch unchanged
- avoid `2026` predictive use
- avoid heavyweight local-model jobs
- test whether the strong H340 C5 buy-volume rewrite transfers to the
  entry-alpha candidate-book label contract

This session stayed long-only.
It did not use `2026` for predictive tuning.

## Branch selection

H340 is the preferred same-day daily-state rewrite of bullish `C5`. H341 showed
that exec-rate stacking does not improve it, and H347/H348/H351 closed the
flow-side attempts to improve the same branch.

The next money-relevant question was whether H340 helps the stock-specific
entry book. If the state is deployable beyond a daily IC rewrite, it should
improve buy-now labels and cycle returns among existing entry candidates after
matching against the entry prior.

## Experiment

### H353 - H340 Entry-Label Transfer

**Hypothesis:**
The H340 same-day buy-volume pressure state should improve the entry-alpha
candidate contract if it is useful as an entry router. Active H340 rows should
show positive validation and confirmation entry-label and return lifts after
matching by date and entry-prior bucket, and should beat raw positive `C5`.

**Command / code:**
`python analysis/h353_h340_entry_label_transfer.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_c5_order_pressure_split.json`
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_labels_cycle5.parquet`
- `data/features/entry_alpha/entry_scores_daily.parquet`
- `data/order_stats/cafef/order_stats_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_155240_h353_h340_entry_label_transfer_research_branch_h340_entry_label_transfer.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | entry-book evidence but no clean transfer over raw C5 |
| panel rows / tickers / dates | `34,980 / 394 / 1,749` | 2019-2025 entry-candidate panel, 2026 excluded |
| H340 dev support threshold | `0.1149253905` | fixed from H340 |
| best state by rule | `h340_buy_vol_gate` | one-phase return lift only |
| gate validation active rows / dates | `269 / 211` | enough coverage |
| gate validation matched label / net / rel lift | `+0.0223 / +0.0031 / +0.0031` | positive and beats raw C5 validation return lift |
| gate confirmation active rows / dates | `161 / 121` | enough coverage |
| gate confirmation matched label / net / rel lift | `+0.0294 / -0.0001 / -0.0001` | label positive but return lift slightly negative |
| strong-support validation matched label / net / rel lift | `+0.0291 / +0.0001 / +0.0001` | positive but below raw C5 validation return lift |
| strong-support confirmation matched label / net / rel lift | `+0.0855 / +0.0028 / +0.0028` | positive and better than raw C5 confirmation return lift |

**Result:**
H340 partially transfers to the entry-candidate book, but not cleanly enough to
promote as an entry prior. The loose H340 gate improves validation returns but
loses confirmation return lift. The stronger H340 support state is positive in
both validation and confirmation, but it does not beat raw positive `C5` in
validation.

**Verdict: MIXED**

## Branch decision

Keep H340 as the preferred daily-state `C5` rewrite, and keep the entry-book
transfer as offline evidence only:
- do not promote H340 as an entry-alpha prior
- do not replace the current entry prior with H340
- only reopen with a stricter small-book integration test if the entry branch
  explicitly needs a C5/order-pressure router

## Memory changes

Updated:
- `notes/live_state.md`
- `notes/findings-271-300.md`
- `notes/signal_library.md`

Added:
- `analysis/h353_h340_entry_label_transfer.py`

Durable finding:
- `F293`

No promoted signal was added.

## Verification

Completed:
- `python -m py_compile analysis/h353_h340_entry_label_transfer.py`
- `python analysis/h353_h340_entry_label_transfer.py`
- read the saved run summary and results artifacts

The broader test suite was not run.

## Next step

Continue the evergreen loop with either a new current-data branch or a source
readiness gate. Do not keep stacking daily side-channel filters around H340.
