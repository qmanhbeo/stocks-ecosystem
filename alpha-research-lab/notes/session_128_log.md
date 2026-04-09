# Session 128 Log — Bright-Mind Theory Wave (2026-04-08)

## Objective

Run the staged bright-mind theory wave as the smallest honest pass on each branch:
- `H297` activation-pressure interactions
- `H298` calendar-conditioned quality
- `H299` intraday library atoms
- `H300` VN30 boundary pressure
- `H301` CafeF event-surface v2 pilot
- `H302` news-attention disagreement

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added six bounded research scripts:
- `analysis/h297_activation_pressure_interactions.py`
- `analysis/h298_calendar_conditioned_quality.py`
- `analysis/h299_intraday_library_atoms.py`
- `analysis/h300_vn30_boundary_pressure.py`
- `analysis/h301_cafef_event_surface_v2_pilot.py`
- `analysis/h302_news_attention_disagreement.py`

### H297 - Activation Pressure Interactions
**Hypothesis:**
Selector efficacy may be driven more by reserve scarcity, score-gap compression, and blocked-buy concentration than by simple breadth.

**Command / code:**
`python analysis/h297_activation_pressure_interactions.py`

**Inputs:**
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_labels_cycle5.parquet`
- `data/features/activation_meta_daily.parquet`
- `data/features/activation_state_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260408_192023_h297_activation_pressure_interactions_research_branch_activation_pressure_interactions.json`

| Metric | Value | Note |
|--------|-------|------|
| panel dates | `1749` | `2019-2025`, no `2026+` |
| target | `selector_cycle_edge` | selected top-`5` mean cycle-relative return minus candidate-pool mean |
| best interaction | `replacement_pressure_combo` | still the least-bad interaction row |
| best interaction validation rho | `-0.0040` | effectively zero |
| best interaction 2025 rho | `+0.0043` | effectively zero |
| best baseline | `buyable_breadth_all` | stronger than every interaction line |
| best baseline validation rho | `+0.1172` | still weak, but clearly above the interactions |

**Result:**
The activation-pressure interaction branch failed cleanly. Reserve, blocked-buy, and replacement composites never produced a stable relation with next-cycle selector edge, and even the weak baseline states remained stronger than the new interaction rows. This is not enough to justify a selector-state gate branch.

**Verdict: FAILED**

### H298 - Calendar-Conditioned Quality
**Hypothesis:**
Earnings-quality and fundamentals may only turn on near report clocks or fresh company-event windows rather than as always-on features.

**Command / code:**
`python analysis/h298_calendar_conditioned_quality.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_earnings_quality_daily.parquet`
- `data/features/xs_fundamentals_daily.parquet`
- `data/features/xs_earnings_calendar_daily.parquet`
- `data/features/event_surface_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260408_192606_h298_calendar_conditioned_quality_research_branch_calendar_conditioned_quality.json`

| Metric | Value | Note |
|--------|-------|------|
| panel rows | `826,404` | merged `2015-2025` audit panel |
| best candidate | `xs_npm_trend_rank × corporate_action_window` | strongest masked validation line |
| best candidate dev IC | `+0.0111` | barely positive |
| best candidate validation IC | `+0.1650` | strong but very sparse |
| best candidate 2025 IC | `-0.0855` | flips negative in confirmation |
| validation mask share | `1.14%` | too sparse to rescue the family broadly |
| steadier positive slice | `roe_rank × post_q_end_10d` | validation `+0.0161`, confirmation `+0.0408`, but still weak overall |

**Result:**
Conditioning does help in some narrow windows, especially around sparse corporate-action and post-quarter-end slices. But the strongest rows are either too sparse or fail to hold sign into `2025`, and the steadier positives remain too weak to reopen the slow-data family as an active branch.

**Verdict: MIXED**

### H299 - Intraday Library Atoms
**Hypothesis:**
Reduced-shape CafeF `1H` data may still survive as standalone daily atoms on the observed subset even though the router branch failed.

**Command / code:**
`python analysis/h299_intraday_library_atoms.py`

**Inputs:**
- `artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json`
- `artifacts/timing_data/20260403_103038_h258_reduced_shape_intraday_contract_panel.parquet`
- `data/features/xs_rl_signal_matrix.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260408_192203_h299_intraday_library_atoms_research_branch_intraday_library_atoms.json`

| Metric | Value | Note |
|--------|-------|------|
| observed rows | `243,763` | observed reduced-shape overlap only |
| observed dates | `718` | `2023-2025` restarted window |
| best atom | `fade_tension_disagreement` | residualized against `S1/C4/C13` |
| best atom dev / val / 2025 IC | `+0.0318 / +0.0365 / +0.0208` | clean across all three phases |
| best atom max anchor corr | `0.0668` | low redundancy |
| second atom | `intraday_shape_core_disagreement` | `+0.0305 / +0.0252 / +0.0154` |
| raw-shape status | `failed or mixed` | raw atoms stay redundant or sign-unstable |

**Result:**
The raw reduced-shape atoms still do not survive as transportable standalone features. But the disagreement residuals do survive cleanly on the observed subset, which keeps the reduced-shape branch alive as narrow offline evidence rather than closing it entirely.

**Verdict: PASSED**

### H300 - VN30 Boundary Pressure
**Hypothesis:**
VN30 boundary pressure may still matter as a recipient-state overlay on top of existing signals even though broad big-name work failed.

**Command / code:**
`python analysis/h300_vn30_boundary_pressure.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/xs_vn30_rebalancing.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260408_192123_h300_vn30_boundary_pressure_research_branch_vn30_boundary_pressure.json`

| Metric | Value | Note |
|--------|-------|------|
| best interaction | `s1_x_add_pressure` | `rank(S1) × rank(add_pressure)` |
| best interaction dev / val / 2025 IC | `+0.1100 / +0.0994 / +0.0994` | very strong interaction row |
| best raw VN30 feature | `rank_change_rank` | validation only `+0.0026` |
| boundary S1 cohort IC | `+0.0748` | weaker than the rest |
| rest-of-universe S1 IC | `+0.1671` | still owns most of the edge |
| boundary C13 cohort IC | `+0.0217` | also weaker than the rest (`+0.0407`) |

**Result:**
The interaction rows are directionally real, especially when add-pressure is multiplied by the frozen `S1` rank. But the actual boundary cohort is still weaker than the rest of the universe, so this does not justify reopening a VN30 branch. At most it is local overlay evidence.

**Verdict: MIXED**

### H301 - CafeF Event-Surface V2 Pilot
**Hypothesis:**
The local CafeF archive may support a richer company-specific event surface with first-public timestamps and materially more novel company-event coverage than `event_surface_daily`.

**Command / code:**
`python analysis/h301_cafef_event_surface_v2_pilot.py`

**Inputs:**
- `data/news/cafef/raw/*.jsonl`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/execution/tradability_daily.parquet`
- `data/features/event_surface_daily.parquet`
- `data/stock/gia_lich_su_VNINDEX_1D.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260408_192103_h301_cafef_event_surface_v2_pilot_research_branch_cafef_event_surface_v2_pilot.json`

| Metric | Value | Note |
|--------|-------|------|
| seed unique articles | `1,072` | strict title-ticker seed |
| pilot unique articles | `3,933` | alias-expanded event-v2 pilot |
| alias holdout precision | `98.82%` | timestamp integrity preserved |
| novel daily share vs v1 | `74.48%` | materially richer than `event_surface_daily` |
| pilot 5d held-row coverage | `2.30%` | better than seed `0.75%` |
| v1 5d company-proxy coverage | `15.54%` | pilot still far below v1 coverage |
| first-public rows | `5,177` | saved timestamped event rows |

**Result:**
The event-v2 pilot is real. Alias expansion materially increases unique articles and preserves excellent holdout precision, and the daily rows are highly novel versus v1. But coverage remains too sparse relative to the broad v1 company proxies, so the branch stays acquisition evidence only for now.

**Verdict: MIXED**

### H302 - News Attention Disagreement
**Hypothesis:**
The real LLM news edge may be "new information that is not yet crowded by repeated article coverage," not raw pooled sentiment.

**Command / code:**
`python analysis/h302_news_attention_disagreement.py`

**Inputs:**
- `data/features/xs_llm_news_ticker_day.parquet`
- `data/features/xs_news_sentiment_rolling.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_labels_cycle5.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260408_192019_h302_news_attention_disagreement_research_branch_news_attention_disagreement.json`

| Metric | Value | Note |
|--------|-------|------|
| active-book window | `2018-01-01 -> 2025-12-31` | the intended branch contract |
| active-window rows | `652,527` | full zero-filled ticker-day grid |
| nonzero LLM rows | `0` | complete blocker |
| result | `SKIP` | no active-book news surface exists yet |

**Result:**
The branch is still data-blocked, not analytically unresolved. There are zero nonzero LLM ticker-day rows in the active-book years, so the novelty × attention disagreement audit cannot be run honestly yet.

**Verdict: NEUTRAL**

---

## Branch decision

Bright-mind wave result:
- `H297`: kill the activation-pressure interaction branch on the current contract
- `H298`: keep calendar-conditioned quality only as sparse offline evidence; do not reopen the slow-data family broadly
- `H299`: keep reduced-shape disagreement atoms alive as the only surviving theory-wave follow-through
- `H300`: keep VN30 boundary pressure as local overlay evidence only; do not reopen a big-name branch
- `H301`: keep event-surface v2 as acquisition evidence only; no predictive screen yet
- `H302`: keep blocked behind `llm-cache-fill`

Immediate priority stays unchanged:
- `llm-cache-fill`
- then `llm-feature-refresh`

If an offline side branch is intentionally reopened before LLM data is ready, the only clean survivor from this wave is the `H299` disagreement-atom line.

---

## Validation

Completed during the pass:
- ran `python -m py_compile` on all six new analysis scripts
- ran:
  - `python analysis/h297_activation_pressure_interactions.py`
  - `python analysis/h298_calendar_conditioned_quality.py`
  - `python analysis/h299_intraday_library_atoms.py`
  - `python analysis/h300_vn30_boundary_pressure.py`
  - `python analysis/h301_cafef_event_surface_v2_pilot.py`
  - `python analysis/h302_news_attention_disagreement.py`
- read the saved run summaries for all six passes

Verdicts:
- `H297 activation-pressure interactions`: **FAILED**
- `H298 calendar-conditioned quality`: **MIXED**
- `H299 intraday library atoms`: **PASSED**
- `H300 VN30 boundary pressure`: **MIXED**
- `H301 CafeF event-surface v2 pilot`: **MIXED**
- `H302 news attention disagreement`: **NEUTRAL / SKIP**
