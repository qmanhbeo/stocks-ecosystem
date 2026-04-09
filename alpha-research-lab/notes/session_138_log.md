# Session 138 Log — Attention-Congestion Router (2026-04-09)

## Objective

Formalize and test the first current-data branch from the new wild-frontier
queue:
- `H318` attention-congestion router

Question:
- do the surviving `H310` event-v2 states react differently when the market is
  cognitively overloaded, or is the idea still blocked by missing / flat
  market-attention data?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h318_attention_congestion_router.py`

### H318 - Attention-Congestion Router
**Hypothesis:**
Same-day issuer-specific event-v2 shocks should diffuse more slowly when the
market is already attention-congested. If that is true, high-load or
high-distraction days should show stronger `5d` lift than `1d` lift relative to
the complementary not-high days.

**Command / code:**
`python analysis/h318_attention_congestion_router.py`

**Inputs:**
- `data/features/xs_llm_news_market_daily.parquet`
- `data/news/cafef/raw/*.jsonl`
- `artifacts/run_summaries/latest_research_branch_event_v2_predictive_rescreen.json`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `artifacts/cache/future_rel_return_5d_hose.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_145951_research_branch_attention_congestion_router.json`

| Metric | Value | Note |
|--------|-------|------|
| market-daily rows | `748` | published `xs_llm_news_market_daily.parquet` on `2023-2025` |
| market-daily unique counts | all `1` | audited columns are fully flat in the target window |
| proxy days | `1,096` | raw CafeF daily attention panel on `2023-2025` |
| best primary proxy | `high_distraction` | top-tercile raw load + bottom-tercile mapped share |
| validation lag-gap / fwd5 deltas | `+0.0301 / +0.0154` | primary `event_today_novel20` vs not-high days |
| confirmation lag-gap / fwd5 deltas | `-0.0412 / -0.0057` | same row flips against the thesis |
| best secondary proxy | `high_event_breadth` | best `recent5_low_repeat20` row, still failed |

**Result:**
The intended market-LLM representation is not usable on the target window:
every audited `xs_llm_news_market_daily` column is flat on `2023-2025`, so the
branch had to fall back to raw-archive attention proxies. That proxy pass found
one local validation pocket on the primary same-day state,
`event_today_novel20 × high_distraction`, where the slower-diffusion thesis
looked plausible. But the same row broke in `2025`, and no proxy passed on the
secondary recent-window state. So the branch does not clear a real routing bar
on the current local stack.

**Verdict: MIXED**

---

## Branch decision

`H318` does not justify a broader market-attention router on current local data:
- keep the idea only as weak offline evidence
- treat the published `xs_llm_news_market_daily` surface as unusable for
  `2023-2025` in its current state
- do **not** spend more budget on local attention-congestion tuning until a
  richer market-attention source exists

Next honest current-data queue item:
- `ownership-network-contagion`
  - the attention branch is now narrowed
  - the next creative current-data line is the issuer / insider / large-holder
    network transmission idea

Next honest acquisition queue remains:
- `historical-foreign-flow-source`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h318_attention_congestion_router.py`
- ran `python analysis/h318_attention_congestion_router.py`
- read the saved run summary and detailed results artifacts
