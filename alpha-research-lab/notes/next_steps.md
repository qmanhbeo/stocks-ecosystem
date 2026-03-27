# Next Steps & Session History

This is the live small-brain file for current state, recent direction, and next priorities.
Use `notes/session_26_log.md` for the latest full session detail.

---

## Current State

**Session status:** Session 37 complete (H106 C3 dispersion regime REJECTED; dense signal search closed, 2026-03-27)

### Current production system

**H54 - Full HOSE Rank Portfolio**
- +25.52% avg edge, Sharpe 9.17, 11/11 positive years (2015-2025)
- IC +0.1515 vs +0.088 on the older 52-stock universe
- No external VIX filter
- 2026 live validation through 2026-03-11: IC +0.1323, gross/trade +0.155%, net/trade -0.145% @0.30% RT
- Run:
  `conda run -n stocks python analysis/h40_rank_portfolio.py --probas data/features/xs_barrier_all_probas_hose_full.parquet --no-vix-filter`

### Important reference systems

**H52 - Honest benchmark**
- +11.64% avg edge, Sharpe 1.83, 8/9 positive years
- Run:
  `conda run -n stocks python analysis/h52_nested_wf_params.py`

**H87(alpha=0.7) - Sharpe-optimized near-champion**
- +25.03% avg edge, Sharpe 10.25, 11/11 positive years
- Built from H77 + H86 classifier probas blended with regressor scores
- Saved artifact: `data/features/xs_blend_h87_alpha0.7.parquet`
- Executable economics are only marginally different from H54 on daily H=1
- Higher-cost fallback: weekly H=5 becomes better than H54 daily above roughly `0.49%` RT

**H43 - Historical previous champion**
- +13.75% avg edge, Sharpe 4.58, 11/11 positive years
- Contamination documented

### What Session 26 established

- H87a (H77 + H86 classifier) is neutral: +24.75% edge, Sharpe 9.42, IC +0.1502.
- H87(alpha=0.5) narrowly misses the Session 26 target: +24.94% edge, Sharpe 9.94.
- H87(alpha=0.7) clears the target: +25.03% edge, Sharpe 10.25.
- H78 E=1 overturns the old inference: daily rebalancing still wins in executable T+1-open terms.
- H63 no-VIX cost stress gives H54 an exact break-even near 0.54% RT; practical safe zone is `<= 0.50%` RT.
- H87(alpha=0.7) now exists as a saved tradable artifact, but its daily executable economics are almost identical to H54.
- H75 current no-VIX live validation keeps strong IC in 2026 (`+0.1323`) and positive executable gross returns, but net is still slightly negative so far at `0.30%` RT.
- H88 closes the deployment fallback rule: below ~`0.49%` RT use H54 daily; above that use H87 weekly.
- H54 remains champion on raw edge, but H87(alpha=0.7) is now the best "Sharpe > 10 and edge > 25" reference point.

---

## Session History

| Session | Date | Key Result | Best System After |
|---------|------|-----------|-------------------|
| 01 | 2026-03-16 | Framework built; baselines run | None (OHLCV = 0 edge) |
| 02 | 2026-03-16 | OHLCV exhaustion confirmed (F2) | None |
| 03 | 2026-03-16 | Relative momentum discovered -> E8 +0.73% (F4, F6) | E8 +0.73% |
| 04 | 2026-03-16 | XS model: 53-55% acc all 11 years (F7); single-stock feature space exhausted | XS model |
| 05 | 2026-03-16 | 9 new signal directions all failed; ensemble infrastructure built; X2 +3.87% (F10a, F10b) | X2 +3.87% |
| 06 | 2026-03-16 | Ensemble breakthrough X3 +10.28%; VIX filter X8 +8.76% (F11, F13) | X8 +8.76% |
| 07 | 2026-03-16 | Triple barrier E32 fixes 2021; X8-E32 +13.96% (F14); 10d horizon failed (F15) | X8-E32 +13.96% |
| 08 | 2026-03-16 | Barrier XS near-fixes 2022; H22 +15.13% Sharpe 1.52 (F16, F17) | H22 +15.13% |
| 09 | 2026-03-17 | Methodology audit; H23 multi-stock +21.94% 11/11 (F18-F20) | H23 +21.94%* |
| 10 | 2026-03-17 | Macro regime filters; H26 FPT +23.97% Sharpe 2.04; H27 portfolio Sharpe 2.80 (F21, F22) | H26 +23.97% |
| 11 | 2026-03-17 | New data; TAIEX+KOSPI H23 Sharpe 3.72 (F23, F24) | H23+TAIEX +20.94% |
| 12 | 2026-03-17 | Model arch sweep; H38 VIX[15,30] +18.71% FPT champion (F25) | H38 +18.71% (FPT) |
| 13 | 2026-03-17 | Rank portfolio H43: IC=+0.088, 11/11 years, Sharpe 4.58 (F26) | H43 +13.75% |
| 14 | 2026-03-17 | H44 portfolio refinements: daily rebalancing optimal | H43 unchanged |
| 15 | 2026-03-17 | H45 dollar: +0.409%/trade, 9.1%/yr net; turnover reduction kills strategy (F27-F29) | H43 confirmed |
| 16 | 2026-03-18 | Contamination eliminated: H52 honest +11.64% Sharpe 1.83; H50a VIX-clean +11.85% (F30-F31) | H43 (pub: H52) |
| 17 | 2026-03-18 | Universe expansion 52->393 stocks: H54 +25.52% Sharpe 9.17 (F32) | H54 +25.52% |
| 18 | 2026-03-18 | H54 validated: H55 +1.037%/trade liquid, H56 honest Sharpe 7.35, H57 no survivorship bias (F33-F35) | H54 (confirmed) |
| 19-23 | 2026-03-18/19 | Kill tests, execution audit, 2026 holdout (H75): IC=+0.1323 PASS, gross +0.258%, net -0.042% @0.30%RT | H54 (cost-limited) |
| 24 | 2026-03-19 | H84 FAIL, H78 NEUTRAL, H85 FAIL (F36-F38) | H54 unchanged |
| 25 | 2026-03-19 | H77-H86 all NEUTRAL/FAIL; 1% barrier optimal (F39); H54 remains champion | H54 unchanged |
| 26 | 2026-03-19 | H87 alpha=0.7 operationalized; H75 live IC +0.1323; H54/H87 crossover ~0.49% RT | H54 unchanged |
| 27 | 2026-03-24 | H54 parked (deployment gap); next-signal search begins | H54 PARKED |
| 28 | 2026-03-24 | H90 PASS (vol IC+0.0084); H91 MIXED (1d Sharpe 11.63); H93 PASS (Sharpe 15.08, std 1.60%); H94 NEUTRAL | H93 = best RL signal |
| 29 | 2026-03-24 | H89 FAIL (news too sparse, IC −0.0044); H92 FAIL (sector sub-models < pooled); H95 DEFERRED (no hist foreign flow) | H93 unchanged |
| 30 | 2026-03-25 | H96 FAIL (rolling news IC −0.0008); H97 BLOCKED (API 403); H99 FAIL (body extraction IC −0.0128); news path exhausted | H93 unchanged |
| 31 | 2026-03-26 | H97 FAIL (insider IC −0.0007, Sharpe 15.08→10.77); C2 candidate added; CafeF GDCoDong API discovered | H93 unchanged |
| 32 | 2026-03-26 | C2 standalone tested: IC +0.0256 (9/11 years), but Top-5 edge +0.09% and only 5/11 positive years; not tradeable standalone | H93 unchanged |
| 33 | 2026-03-26 | H98 infra implemented (LLM extractor + builder + WF flags); smoke test shows local Ollama timeout in this runtime, full H98 run pending | H93 unchanged |
| 34 | 2026-03-26 | **H98 PARKED**; H100/H101/H102 dense sweeps run — H101 PASS (Sharpe 15.34), H100/H102 FAIL (variance blow-up) | H93/H101 tie-class |
| 35 | 2026-03-26 | Standalone gate enforced; H103 return skewness FAIL; dense standalone checks logged (H100 standalone +, H101 context weak, H103 standalone weak) | H93/H101 tie-class |
| 36 | 2026-03-26 | H104 earnings calendar dense features built; H104 and H105 both FAIL (Sharpe collapse), standalone IC weak | H93/H101 tie-class |
| 37 | 2026-03-27 | H106 C3 regime-conditional IC: dispersion spread ≤2%, p=0.124 — C3 REJECTED; dense search closed | H93 only |

\* Contaminated: stock selection was post-hoc.

---

## XS Momentum Signal Status: PARKED (as of Session 27, 2026-03-24)

The cross-sectional momentum signal (H54) is **parked — not production-ready**.

**What is confirmed:**
- Ranking skill intact: WF IC = +0.152, 2026 live IC = +0.134
- Gross returns positive in backtest and 2026 holdout
- 4/4 robustness tests pass

**What is NOT closed (deployment gap):**
1. Real fills at T+1 open unverified (partial fills, queue position, mid/small-cap slippage)
2. Net P&L negative at 0.30% RT in 2026 partial year — not yet confirmed positive
3. No execution infrastructure for daily rebalancing
4. Signal degrades to ~half IC in top-50 liquid stocks

**Fallback rule (for reference, if/when deployed):**
- RT cost < 0.49%: use H54 daily
- RT cost > 0.49%: use H87(alpha=0.7) weekly

**Conditions to unpark:** real fill data + net P&L confirmed positive over full year + execution infra.

See `notes/session_27_log.md` and `notes/findings.md` F53 for full rationale.

---

## Session 28 Results (2026-03-24)

- **H90 PASS:** Volume features → IC +0.1599, Sharpe 9.48. `xs_barrier_vol_hose_full.parquet`
- **H91 MIXED:** 1-day target → IC +0.1395, Sharpe 11.63. Lower variance is the key finding. `xs_barrier_1d_hose_full.parquet`
- **H93 PASS:** Volume + 1-day combined → IC +0.1491, edge std **1.60%**, Sharpe **15.08**. **Best RL signal.** `xs_barrier_vol_1d_hose_full.parquet`
- **H94 NEUTRAL:** Sector-relative features on H93 → Sharpe 14.21 (regression). H93 stands.

See `notes/session_28_log.md` and findings F54–F57.

---

## Session 31 Results (2026-03-26)

- **H97 FAIL:** Insider deals → IC +0.1484 (−0.0007 vs H93), Sharpe **10.77** (−4.31 vs H93). 3.57% sparse, same XGBoost failure as news (F66).
- **Standalone IC:** insider_net_plan_5d avg +0.025, 9/11 years positive. Near-zero corr with S1 (−0.027). Added as **C2 candidate**.
- **Data source:** CafeF GDCoDong API discovered (`cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx`) — 394/394 tickers, 2010–2026, free/no auth.
- **KBS/VCI vnstock:** KBS endpoint returns `[]` (unpopulated); VCI wrapper unimplemented.

Infrastructure built: `data_tools/fetch_insider_deals.py`, `data_tools/build_insider_features.py`, `--use-insider` flag in WF.

See `notes/session_31_log.md` and findings F66.

**H93 remains best RL signal (Sharpe 15.08, IC +0.1491, edge std 1.60%).**

---

## Session 32 Results (2026-03-26)

- **C2 standalone test complete:** pure event-day ranking by `insider_net_plan_5d`.
- **Signal quality unchanged:** standalone IC **+0.0256**, 9/11 years positive, 3.57% row coverage.
- **Portfolio quality weak:** Top-1 **−0.304%**, Top-3 **+0.049%**, Top-5 **+0.090%** (5d relative edge).
- **Stability weak:** Top-5 positive in **5/11** years, Sharpe proxy **0.51**.
- **Verdict:** C2 remains RL-candidate context signal, but **not a standalone tradable strategy**.

Artifacts:
- `artifacts/run_summaries/20260326_150012_c2_insider_standalone_standalone_signal.json`
- `artifacts/run_summaries/20260326_150012_c2_insider_standalone_details.json`

See `notes/session_32_log.md`.

---

## Session 30 Results (2026-03-25)

- **H96 FAIL:** Rolling 5d/30d news → IC +0.1483 (−0.0008 vs H93). 5.1% coverage still too sparse (F63).
- **H97 BLOCKED:** vnstock API returns 403 Forbidden in cloud environment. Need local access.
- **H99 FAIL:** Body-text extraction → IC +0.1363 (−0.0128 vs H93). 5.2× more obs but noisier (F64).
- **News path exhausted** (F65): keyword lexicon insufficient. Only H98 (LLM) remains untested.

Infrastructure built: `data_tools/build_rolling_news_sentiment.py`, `--use-rolling-news` and `--news-path` flags in WF.

See `notes/session_30_log.md` for full details.

---

## Session 29 Results (2026-03-24)

- **H89 FAIL:** Keyword news sentiment IC 0.1361 vs H93 0.1405 (−0.0044). Signal too sparse (0.8% coverage). `xs_news_sentiment_daily.parquet` built; need rolling/LLM approach to fix.
- **H92 FAIL:** Banking (20 tickers) IC 0.1077 vs pooled 0.1238 (−0.0161). Real estate (57) IC 0.1308 vs pooled 0.1393 (−0.0085). Pooled model wins — more data outweighs sector specificity.
- **H95 DEFERRED:** Historical daily foreign flow not available via vnstock (F59).
- **Infrastructure built:** `data_tools/fetch_sector_classification.py`, `data_tools/extract_news_sentiment.py`, `--sector` filter in WF (diacritic-normalized), `data/features/sector_classification.parquet` (398 tickers, ICB classification).

See `notes/session_29_log.md` and findings F58–F61.

**H93 remains best RL signal (Sharpe 15.08, IC +0.1491, edge std 1.60%).**

---

## Session 33 Results (2026-03-26)

- **Implemented:** `data_tools/extract_llm_news_features.py` (LLM extraction to `data/llm_cache/`).
- **Implemented:** `data_tools/build_llm_news_features.py` (outputs ticker-day + dense market-daily parquets).
- **WF integrated:** new flags `--use-llm-news`, `--use-llm-market` in `cross_sectional_wf.py`.
- **Smoke verification:** 3-day extraction run writes cache files but all batches timed out (local Ollama unavailable in this environment).
- **Build verification:** both H98 feature parquets built; dense market feature file has zero NaNs.
- **WF verification:** both LLM feature blocks merge and train-path works.

See `notes/session_33_log.md`.

---

## Session 34 Results (2026-03-26)

- **H98 LLM path: PARKED explicitly.** Infrastructure exists, but extraction is too slow/unstable operationally in current runtime.
- **H100 (open/close asymmetry): MIXED/FAIL for RL quality.**
  - IC +0.1541 (+0.005 vs H93), edge +25.36% (+1.21%)
  - Sharpe **11.63** (−3.45 vs H93), std 2.18% (+0.58%)
- **H101 (dispersion regime): PASS (risk-adjusted).**
  - IC +0.1474 (−0.0017 vs H93), edge +23.83% (−0.32%)
  - Sharpe **15.34** (+0.26 vs H93), std 1.55% (−0.05%)
- **H102 (H100+H101): FAIL.**
  - IC +0.1531 (+0.004), edge +25.23% (+1.08%)
  - Sharpe **9.96** (−5.12), std 2.53% (+0.93%)

See `notes/session_34_log.md`.

---

## Session 35 Results (2026-03-26)

- **H103 implemented and tested:** dense return-skewness branch.
- **H103 result:** IC +0.1489 (~flat), edge +24.19% (~flat), Sharpe **10.63** (large drop) => FAIL.
- **Standalone gate added explicitly** via `analysis/standalone_dense_signal_checks.py`.
- **Standalone summary:**
  - H100 proxy (`oc_asym_5d`): IC +0.0273, 10/11 years positive, corr with S1 +0.147.
  - H101 context (`xs_dispersion_z20` vs S1 top5 edge): Spearman −0.0289, p=0.13 (weak).
  - H103 proxy (`ret_skew_z20`): IC +0.0019, 6/11 years positive, corr with S1 −0.0035 (too weak).

See `notes/session_35_log.md`.

---

## Session 36 Results (2026-03-26)

- **H104 implemented:** dense earnings/reporting calendar features (`xs_earnings_calendar_daily.parquet`).
- **H104 result:** IC +0.1480 (−0.0011), edge +24.14% (~flat), Sharpe **11.80** (−3.28) => FAIL.
- **H105 (H101+earnings) result:** IC +0.1466 (−0.0008 vs H101), Sharpe **11.96** (−3.38 vs H101) => FAIL.
- **Standalone gate:** earnings calendar features show weak standalone IC (~0.001 to 0.006 range) and weak context relation with S1.

See `notes/session_36_log.md`.

---

## Active Priority: Session 38

### Dense Signal Search: CLOSED
All OHLCV-derived dense candidates have been tested and rejected (H100–H106). No further
candidates in queue. H93 (S1) is the only confirmed RL signal.

### Remaining blocked paths
- **H98 LLM Sentiment** — PARKED (runtime/throughput bottleneck; re-open when local inference restored)
- **H95 Foreign flow** — BLOCKED (historical daily data not available via vnstock)
- **Order book imbalance** — BLOCKED (intraday data not available historically)

### Options for next phase
1. Declare signal search Phase 1 complete; shift to RL agent development using S1 alone.
2. Wait for H98 LLM to become operational.
3. Identify a new data source (foreign flow, intraday, order book provider).
4. Explore fundamentals-based cross-sectional signals (P/E, P/B rank) — data exists in
   `data/fundamentals_cache/` but not yet tested as a standalone cross-sectional signal.

---

## Working Rules

- 2026 data: monitor-only. Do not use for tuning.
- For any material experiment, save a compact result summary and update notes.
- Archived reasoning lives in session logs; this file stays lean.
