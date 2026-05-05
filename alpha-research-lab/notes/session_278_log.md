# Session 278 Log

**Date**: 2026-05-05
**Focus**: H397 `barrier_pop_vs_hold_router`

## Summary

- Activated the fourth S272/S273 eureka queue item.
- Added `analysis/h397_barrier_pop_vs_hold_router.py`.
- Retested fixed H364/H383/H385/C16/insider states across 1d, 2d, and 5d
  horizons on buyable rows with a 15 bps per-row cost.
- Verdict: **PASSED**. Active/positive-news strong-flow is a 1d C16 ranker;
  official-supported attention is a 5d payoff state.

## H397 - Barrier Pop Vs Hold Router

**Hypothesis:**
Some states that failed broad 5d candidate allocation may still be valid
next-day pop signals, while official attention states should be judged as
delayed hold signals.

**Command / code:**
```bash
python alpha-research-lab/analysis/h397_barrier_pop_vs_hold_router.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_order_pressure_daily.parquet`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/news/datasets/news_daily_features.parquet`
- OHLCV / VNINDEX stock files through `src/standalone_signal_utils.py`

**Protocol:**
- No `2026+` rows.
- Test years `2018-2025`.
- Fixed state definitions only; no retuning.
- Buyable rows only via `can_buy_next_open`.
- Net relative returns subtract `15` bps per row.
- Horizons: `1d`, `2d`, `5d`.

**Saved artifact:**
`artifacts/run_summaries/20260505_172821_h397_barrier_pop_vs_hold_router_research_branch_barrier_pop_vs_hold_router.json`

| State | Winning Horizon | Metric | Value | Positive Years |
|-------|-----------------|--------|-------|----------------|
| `active_news_strong_flow` | `1d` | C16 IC lift vs strong-flow | `+0.02257` | `6 / 8` |
| `positive_news_strong_flow` | `1d` | C16 IC lift vs strong-flow | `+0.02536` | `7 / 8` |
| `official_supported_delay` | `5d` | net payoff lift vs unsupported | `+0.00650` | `8 / 8` |
| `official_forward_supported_delay` | `5d` | net payoff lift vs unsupported | `+0.00662` | `8 / 8` |
| `h364_positive_ranker` | `1d` | H364 IC lift | `+0.02935` | `1` valid positive year |
| `insider_buy_pop` | none | C5 IC lift | `-0.01546` at 1d | failed |

**Result:**
H383-style active/positive-news strong-flow should be interpreted as a
next-day C16 ranker, not a 5d allocator: the 1d C16 IC lift passed, while 5d
IC lift turned negative. H385-style official-supported states are delayed
payoff/hold states: 5d net payoff lift was strongest and positive in every
year.

H364 positive news had a 1d IC-lift shape but too little valid yearly support
under the current min-row gate. The C5 insider ranker form failed here; this
does not kill S272 `insider_buy_lead`, which is a next-trading-day event-state
audit rather than a C5-within-insider ranker.

**Verdict: PASSED**

**Next action:**
Continue to `insider_pre_reaction_clock`. That branch should use the S272
event-time insider lead framing, not H397's failed C5 rank-within-insider
form.

## Closeout

- Saved artifact was read before the verdict.
- Branch status changed to passed horizon-router evidence.
- No live branch changed.
- Memory write-back done in live state, compact notes, and findings.
- `2026+` data was avoided.
- No heavy job remains active.
