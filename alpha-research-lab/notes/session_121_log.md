# Session 121 Log

## Objective
Audit the two next macro/news branches while the LLM extractor keeps running: the `news-decay-contract` half-life question and the macro-theme router idea.

This session did not change the live branch.
It did not read `2026+`.

## What changed

Added and ran the H291 news decay contract audit script, then added and ran the H292 macro theme router audit script.

Saved artifacts:
- `artifacts/run_summaries/20260405_232606_h291_news_decay_contract_audit_details.json`
- `artifacts/run_summaries/20260405_232606_h291_news_decay_contract_audit_standalone_signal.json`
- `artifacts/run_summaries/20260405_232906_h292_macro_theme_router_audit_details.json`
- `artifacts/run_summaries/20260405_232906_h292_macro_theme_router_audit_standalone_signal.json`

### H291 - News Decay Contract Audit
**Hypothesis:**
The raw CafeF LLM news stream should obey a learnable novelty half-life, where `follow_up`, `new`, and `recycled` stories matter on different forward horizons.

**Command / code:**
`conda run -n stocks python analysis/h291_news_decay_contract_audit.py`

**Inputs:**
- `data/llm_cache/*.jsonl`
- `data/features/xs_llm_news_market_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260405_232606_h291_news_decay_contract_audit_standalone_signal.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | decay exists, but not a clean one-class contract |
| best feature | `follow_up` | strongest 1d class |
| best horizon | `1d` | strongest pooled row |
| mean rho | `+0.0196` | follow-up is real on the shortest horizon |
| daily hit rate | `0.5256` | slightly above chance |
| positive years | `2 / 2` | both active years positive |
| 5d best feature | `follow_up_minus_new` | horizon reshuffle at 5d |
| 30d best feature | `new` | pooled long-horizon ordering changes again |
| panel dates | `366` | nonzero 2015-2017 window |

**Result:**
The half-life signal is real, but the clean contract fails. `follow_up` is the strongest 1d class, yet the 5d horizon shifts to `follow_up_minus_new` rather than preserving `follow_up` itself. That means there is decay structure, but not a stable single-class ordering that would justify promotion as one compact router.

**Verdict: MIXED**

### H292 - Macro Theme Router Audit
**Hypothesis:**
Macro themes should route into the matching sector basket rather than behaving like one pooled macro-news count.

**Command / code:**
`conda run -n stocks python analysis/h292_macro_theme_router_audit.py`

**Inputs:**
- `data/features/xs_llm_news_market_daily.parquet`
- `data/features/xs_sector_rotation_daily.parquet`
- `data/features/event_surface_daily.parquet`
- `data/features/sector_classification.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260405_232906_h292_macro_theme_router_audit_standalone_signal.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | real signal, but not a clean router |
| best basket | `regulated_combo` | combined bank + real-estate basket |
| best feature | `frac_real_estate_theme` | strongest pooled row |
| mean rho | `+0.0988` | strong, but not sector-specific |
| daily hit rate | `1.0000` | positive in both years |
| positive years | `2 / 2` | both active years positive |
| banking matched feature | `frac_banking_theme` | positive but weaker |
| real-estate matched feature | `frac_real_estate_theme` | positive and strongest |
| regulation theme | weak / negative | does not cleanly own the regulated basket |

**Result:**
Macro themes do matter, but the effect is not a crisp sector router. The real-estate theme is the strongest feature even on the combined regulated basket, while banking and regulation are weaker. That looks more like a broad property / balance-sheet state factor than a clean theme-to-sector switch.

**Verdict: MIXED**

## Branch decision

Keep the live branch unchanged.
Keep `C15` as offline evidence only.
Keep `news-marginal-slot` blocked until active-book years have nonzero news coverage.
Park `news-decay-contract` as a mixed evidence line.
Park `macro-theme-router` as a mixed evidence line.
Move the queue to `breadth-activation-gate`.

## Validation

Completed before the runs:
- `conda run -n stocks python analysis/h291_news_decay_contract_audit.py`
- `conda run -n stocks python analysis/h292_macro_theme_router_audit.py`

Completed for the experiments:
- read `artifacts/run_summaries/20260405_232606_h291_news_decay_contract_audit_standalone_signal.json`
- read `artifacts/run_summaries/20260405_232906_h292_macro_theme_router_audit_standalone_signal.json`

Verdict:
- `H291`: **MIXED**
- `H292`: **MIXED**

## Parked Here

Session 121 is the stop point for today. The next active branch is `breadth-activation-gate`, and no further runs were started after the H291/H292 audits.
