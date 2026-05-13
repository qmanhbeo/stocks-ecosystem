# Session 282 Log

**Date**: 2026-05-05
**Focus**: H401 `anti_signal_annihilation_veto`

## Summary

- Activated the eighth S272/S273 eureka queue item.
- Added `analysis/h401_anti_signal_annihilation_veto.py`.
- Tested fixed top-5 buyable candidate vetoes against no-veto and random
  same-breadth veto controls.
- Verdict: **MIXED**. A tiny `support_count_zero` veto clue exists, but broad
  disagreement veto promotion fails.

## H401 - Anti-Signal Annihilation Veto

**Hypothesis:**
High-ranked long candidates should be vetoed when C16, insider, news,
tradability, and sector side channels disagree with the candidate score.

**Command / code:**
```bash
python alpha-research-lab/analysis/h401_anti_signal_annihilation_veto.py
```

**Inputs:**
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_labels_cycle5.parquet`
- `data/features/xs_order_pressure_daily.parquet`
- `data/features/news/datasets/news_daily_features.parquet`

**Protocol:**
- No `2026+` rows.
- Test years `2019-2025`.
- Top-5 buyable candidate rows only.
- Veto keeps cash in the vetoed slot; denominator stays `K=5`.
- Fixed veto states only; no train-time tuning.
- Benchmarks: no-veto top-5 and random same-breadth vetoes on the same dates.

**Saved artifact:**
`artifacts/run_summaries/20260505_175823_h401_anti_signal_annihilation_veto_research_branch_anti_signal_annihilation_veto.json`

| Veto State | Avg Lift vs No-Veto | Avg Lift vs Random Mean | Positive No-Veto Years | Note |
|------------|---------------------|--------------------------|------------------------|------|
| `support_count_zero` | `+0.000167` | `+0.000152` | `6 / 7` | tiny survivor, fails random p95 |
| `support_count_le1` | `-0.000123` | `+0.000182` | `4 / 7` | too broad |
| `pretty_price_weak_flow` | `-0.000026` | `+0.000190` | `3 / 7` | no no-veto edge |
| `news_hype_weak_flow` | `-0.000075` | `-0.000002` | `3 / 7` | failed |
| `weak_flow_weak_sector` | `-0.000225` | `-0.000123` | `3 / 7` | failed |

**Result:**
The broad annihilation-veto thesis did not pass. Most disagreement masks
reduced top-5 cycle relative return versus no-veto. The only survivor is the
strict `support_count_zero` state: vetoing rows with no C16, insider, news,
tradability, or sector support improved no-veto by `+0.000167` on average and
was positive in `6 / 7` years. That is too small for promotion and did not beat
random same-breadth veto p95 in any year, but it is a plausible future
scale-down clue.

**Verdict: MIXED**

**Next action:**
Continue to `shadow_liquidity_gravity_well`. Do not add a broad veto policy;
carry forward only the strict no-support row as a weak policy clue.

## Closeout

- Saved artifact was read before the verdict.
- Branch status changed to mixed: broad veto blocked, strict no-support clue
  retained.
- No live branch changed.
- Memory write-back done in live state, compact notes, findings, dead ends,
  signal library, and portfolio policy library.
- `2026+` data was avoided.
- No heavy job remains active.
