# Session 123 Log — LLM News Standalone Gate (2026-04-07)

## Objective
Run the formal `llm-news-gate` experiment (H294): test LLM news sentiment features against the canonical 1d barrier label, compare to C1, and decide whether to promote, park, or kill the branch.

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added and ran the H294 LLM news standalone gate script.

Saved artifact:
- `artifacts/run_summaries/20260407_221151_h294_llm_news_standalone_gate_standalone_signal.json`

### H294 - LLM News Standalone Gate (1d Barrier)
**Hypothesis:**
LLM news sentiment features from `xs_llm_news_ticker_day.parquet` pass the canonical standalone signal gate (IC > 0.01, ≥ 6/8 years positive, corr with S1 < 0.30) when evaluated against the 1d barrier label.

**Command / code:**
`conda run -n stocks python analysis/h294_llm_news_standalone_gate.py`

**Inputs:**
- `data/features/xs_llm_news_ticker_day.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260407_221151_h294_llm_news_standalone_gate_standalone_signal.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | pooled fails consistency; state-gated `novelty/new` passes |
| best pooled feature | `llm_sentiment_raw` | IC +0.047 |
| pooled IC | `+0.047` | above 0.01 gate |
| pooled consistency | `1/2 years` | 2016 negative (−0.014), 2017 positive (+0.159) |
| S1 correlation | `−0.043` | near-zero, highly independent |
| coverage | `0.19%` | below C1 baseline (0.8%) |
| best gated IC | `+0.404` | novelty/follow, 99 rows, 1/1 years |
| `novelty/new` IC | `+0.078` | 2/2 years positive, 1331 rows — new finding |
| `alignment/miss` IC | `+0.136` | 1/2 years |
| `novelty/flat` IC | `−0.285` | anti-predictive |
| data constraint | cache covers 2016–2017 only | 6/8 year gate cannot be applied |

**Result:**
Pooled standalone gate fails on consistency: `llm_sentiment_raw` has IC +0.047 (above threshold) but is only positive in 1/2 available years. The 5d-smoothed and confidence-weighted variants are negative. Coverage is 0.19%, below C1's 0.8%.

State-gated result is materially stronger:
- `novelty/new` (stocks where new information dominates over follow-up): IC +0.078, 2/2 years positive, 1331 rows. This passes both IC and available-year consistency gates and is a new result not captured by H290 (which used 5d return and identified `follow` as the strongest bucket; against the 1d barrier, `new` is the consistent winner).
- `novelty/follow`: IC +0.404 (extraordinary) but only 1 observable year (99 rows). Cannot confirm consistency.
- `alignment/miss`: IC +0.136 but 1/2 years.

S1 correlation is −0.043 — highly independent.

**Verdict: MIXED**

---

## Branch decision

Keep C15 as offline evidence only.
Upgrade the C15 entry in `signal_library.md` to note the `novelty/new` finding against the 1d barrier (2/2 years, IC +0.078).
Keep `news-marginal-slot` blocked until active-book years have nonzero LLM coverage.
Park `llm-news-gate` — data constraint is the primary blocker (cache covers 2016-2017 only). Re-open when extraction completes 2018+ years.
Next queue: no active research branch until LLM extraction produces active-book coverage. Keep live branch frozen.

---

## Validation

Completed before the run:
- `conda run -n stocks python -m py_compile analysis/h294_llm_news_standalone_gate.py`

Completed for the experiment:
- read `artifacts/run_summaries/20260407_221151_h294_llm_news_standalone_gate_standalone_signal.json`

Verdict:
- `H294`: **MIXED**
