# Next Steps & Session History

This is the live small-brain file for current state, recent direction, and next priorities.
Use `notes/session_47_log.md` for the latest full session detail.

---

## Current State

**Session status:** Session 47 complete (H137 nested selection FAIL; focus shifts to simpler honest validation / hedging, 2026-03-28)

### New reality check after Session 47

**H135 - Signal Library Portfolio Baseline (corrected)**
- Session 46 found a scoring bug in the original H135 blend:
  - non-presence signals were averaged in raw scale
  - `C4` and `C5` were not already on a common `0-1` rank scale
  - corrected blend logic now cross-sectionally ranks each non-presence signal by date before averaging
- Corrected H135 baseline under the same execution contract:
  - next-open execution
  - `T+2.5` sellability (`T+3` close decision, `T+4` open exit fill)
  - zero-volume / ceiling / floor tradability blocks
  - 0.30% round-trip cost
  - top-5 equal-weight, 3-day rebalance
- Corrected result:
  - `s1_only`: `-68.33%` total, `-10.01%` annualized
  - `recent_core`: `-46.81%` total, `-5.63%` annualized
  - `full_library`: `+72.10%` total, `+5.11%` annualized
  - benchmark VNINDEX: `+223.17%` total
- Implication: the library is **not dead**, but default construction still underperforms badly.

**H136 - Portfolio Construction Sweep**
- Swept `full_library` across:
  - `top_k = 3, 5, 8, 10`
  - rebalance cadence `= 3, 5, 10`
  - weighting `= equal, linear, square`
  - score gate `= none, 0.521, 0.570, 0.600`
- Best configuration:
  - `top_k = 5`
  - rebalance every `5` signal days
  - `equal` weighting
  - score gate effectively irrelevant (`none`, `0.521`, and `0.570` tied)
- Best result:
  - `+1105.71%` total return
  - `+25.66%` annualized
  - `+273.09%` relative vs VNINDEX
  - information ratio `0.50`
  - max drawdown `-59.76%`
  - `8/11` positive years
- Structural takeaway:
  - rebalance cadence matters more than fancy weighting
  - `5d` and `10d` cadence dominate `3d`
  - `equal` weighting beats `linear` and `square`
  - portfolio construction, not more signal mining, is the dominant frontier right now

**H137 - Nested Walk-Forward Portfolio Selection**
- Tested the honest version of “let the machine choose construction”:
  - expanding train window
  - minimum 4 train years
  - select the best H136-style config on past years only
  - freeze it and test on the next year
  - test years: `2019-2025`
- Out-of-sample stitched result:
  - `+21.38%` total
  - `+2.84%` annualized
  - `-42.46%` relative vs VNINDEX
  - information ratio `-0.08`
  - max drawdown `-55.65%`
- Selected configs were simple, not exotic:
  - mostly `top_k=5`, rebalance every `10` days, `equal` weighting
  - early years briefly chose `top_k=3` or `top_k=10` with `5d` cadence
- Implication:
  - the H136 full-sample winner is not reliable enough to trust directly
  - simple nested config selection does **not** yet justify “ML for construction”
  - the next honest path is smaller, simpler, and more regime-aware, or else move to hedged constructions

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
| 38 | 2026-03-28 | H107 FAIL (overnight decomp); H108 PASS (C5 xs_ins_relative_size IC +0.037); H109 FAIL (52-ticker); H110 FAIL (VNM ETF cross-sectional); H111 PARTIAL (breadth PASS, rotation FAIL) | H93 + C4 + C5 |
| 39 | 2026-03-28 | H112 PASS (C6 contrarian_intra); H113 PENDING; H114 FAIL (VN30); H115 PASS (C7 ceiling); H116 PASS (C8 vol_zscore); H117 PASS (C9 reversal); H118-H120 FAIL; RL matrix built | H93 + C4-C9 |
| 40 | 2026-03-28 | H121 PASS (C10 illiq_level IC +0.021, corr +0.008); H113 fetch failed at 302/394; H122 written not run | H93 + C4-C10 |
| 41 | 2026-03-28 | H122 FAIL (spread proxy); C10 added to RL matrix; C10 pairwise corr vs C4-C9 all low | H93 + C4-C10 |
| 42 | 2026-03-28 | H123 PASS (C11 continuation); H124 standalone PASS but rejected on independence; C11 added to RL matrix, low-beta signal excluded | H93 + C4-C11 |
| 43 | 2026-03-28 | H125/H131/H132 FAIL; H127 standalone PASS but redundant with C8; H128 anti-predictive; H130 PASS (C12 gap absorption) | H93 + C4-C12 |
| 44 | 2026-03-28 | H133 PASS (C13 compression blow-off); H134 PASS (C14 residual close-strength); H126 standalone PASS but redundant with C11 | H93 + C4-C14 |
| 45 | 2026-03-28 | H135 initial realistic portfolio baseline logged as FAIL; later corrected in Session 46 after signal-scale bug fix | H93 + C4-C14 |
| 46 | 2026-03-28 | H135 corrected: full_library baseline turns positive; H136 sweep finds top-5 equal-weight, 5d cadence, +1105.71% total and +25.66% annualized | H93 + C4-C14 |
| 47 | 2026-03-28 | H137 nested walk-forward selection: +21.38% total OOS but -42.46% vs VNINDEX; simple config selection overfits and does not validate ML construction yet | H93 + C4-C14 |

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

See `notes/session_27_log.md` and `notes/findings-031-060.md` (F53) for full rationale.

---

## Session 28 Results (2026-03-24)

- **H90 PASS:** Volume features → IC +0.1599, Sharpe 9.48. `xs_barrier_vol_hose_full.parquet`
- **H91 MIXED:** 1-day target → IC +0.1395, Sharpe 11.63. Lower variance is the key finding. `xs_barrier_1d_hose_full.parquet`
- **H93 PASS:** Volume + 1-day combined → IC +0.1491, edge std **1.60%**, Sharpe **15.08**. **Best RL signal.** `xs_barrier_vol_1d_hose_full.parquet`
- **H94 NEUTRAL:** Sector-relative features on H93 → Sharpe 14.21 (regression). H93 stands.

See `notes/session_28_log.md` and `notes/findings-031-060.md` (F54–F57).

---

## Session 31 Results (2026-03-26)

- **H97 FAIL:** Insider deals → IC +0.1484 (−0.0007 vs H93), Sharpe **10.77** (−4.31 vs H93). 3.57% sparse, same XGBoost failure as news (F66).
- **Standalone IC:** insider_net_plan_5d avg +0.025, 9/11 years positive. Near-zero corr with S1 (−0.027). Added as **C2 candidate**.
- **Data source:** CafeF GDCoDong API discovered (`cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx`) — 394/394 tickers, 2010–2026, free/no auth.
- **KBS/VCI vnstock:** KBS endpoint returns `[]` (unpopulated); VCI wrapper unimplemented.

Infrastructure built: `data_tools/fetch_insider_deals.py`, `data_tools/build_insider_features.py`, `--use-insider` flag in WF.

See `notes/session_31_log.md` and `notes/findings-061-090.md` (F66).

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

See `notes/session_29_log.md` and `notes/findings-061-090.md` (F58–F61).

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

## Session 38 Results (2026-03-28)

**Signal library now has: S1 (confirmed) + C1 + C2 + C4 + C5 (candidates)**

- **H107 (Overnight gap decomposition): FAIL as hypothesis, but reveals C4.**
  overnight_mom_5d IC ≈ 0; intraday_mom_5d IC = −0.034; oc_asym_5d IC = +0.0225 (11/11 years).
  Signal lives in the contrast, not the components. oc_asym_5d → promoted to **C4 candidate**.

- **H108 (Insider quality): PASS.**
  xs_ins_relative_size_5d (net_plan / VolumeBeforeTransaction) IC = +0.0374, 10/11 years, corr = −0.008.
  +46% over raw C2. Position-size normalization is the key dimension. → **C5 candidate** (supersedes C2).

- **H109 (Earnings quality 52 tickers): FAIL.**
  Best: xs_roe_delta_rank IC = +0.0049 (8/11 years). Universe too small. Re-test at 394 tickers.

- **H110 (VNM ETF foreign demand proxy): FAIL.**
  VNM ETF premium is a market-direction signal (date-level IC +0.132 for VNINDEX) but provides no
  cross-sectional stock differentiation. Foreign affinity beta is too noisy.

- **H111 (Sector rotation): PARTIAL PASS.**
  xs_sector_rotation_signal IC = −0.0379 (intra-sector rank anti-predictive: laggards beat leaders).
  xs_sector_breadth_5d (fraction of sector stocks positive): IC = +0.0143, 8/11 years, corr = −0.004. → PASS.
  Queued: H112 = contrarian intra-sector signal (sector_mom_rank × (1 − intra_sector_rank)).

New artifacts:
- `data/features/xs_insider_quality_features.parquet` — xs_ins_relative_size_5d (C5)
- `data/features/xs_sector_rotation_daily.parquet` — xs_sector_breadth_5d
- `data/features/xs_earnings_quality_daily.parquet` — 52-ticker earnings quality
- `data/features/xs_foreign_demand_daily.parquet` — VNM ETF features (not predictive)

## Active Priority: Session 48

### Signal library status after Session 44
| Signal | IC | Corr w/ S1 | Coverage | Status |
|--------|----|------------|----------|--------|
| S1/H93 | +0.149 | N/A | 100% | CONFIRMED |
| C4 oc_asym_5d | +0.023 | +0.147 | 100% | Candidate |
| C5 ins_relative_size | +0.037 | −0.008 | 3.4% | Candidate |
| C6 contrarian_intra_5d | +0.030 | +0.142 | 100% | Candidate (S39) |
| C7 xs_ceiling_count_5d | +0.012 | +0.064 | 100% | Candidate (S39) |
| C8 xs_vol_zscore_5d | +0.011 | +0.068 | 100% | Candidate (S39) |
| C9 xs_reversal_1d | +0.028 | +0.161 | 100% | Candidate (S39) |
| C10 xs_illiq_level_rank | +0.021 | +0.008 | 100% | **NEW S40** |
| C11 xs_ret_60d_lag_rank | +0.010 | +0.008 | 100% | **NEW S42** |
| C12 xs_gap_absorb_3 | +0.028 | +0.131 | 100% | **NEW S43** |
| C13 xs_compress_blowoff_2 | +0.035 | +0.191 | 100% | **NEW S44** |
| C14 xs_clv_volconf_resid_rank | +0.013 | +0.102 | 100% | **NEW S44** |
| C1 keyword news | +0.043 | +0.009 | 0.8% | Candidate (inconsistent) |

Note: RL signal matrix built at `data/features/xs_rl_signal_matrix.parquet` (S1+C4+C5+C6+C7+C8+C9+C10+C11+C12+C13+C14, 826k rows × 16 cols).

### Session 44 experiment results (2026-03-28)
- **H133 PASS** — compression blow-off reversal survives as a new reversal state
  - `xs_compress_blowoff_2`: IC +0.0351, 10/11 years, corr S1 = +0.191, max candidate corr = +0.154 → **C13 candidate**
  - `xs_compress_blowoff_1` and `xs_compress_blowoff_3` are stronger on IC but fail S1 overlap (`+0.321`, `+0.340`)
- **H134 PASS** — residual close-location survives explicit de-duplication vs C8
  - `xs_clv_volconf_resid_rank`: IC +0.0131, 11/11 years, corr S1 = +0.102, max candidate corr = +0.099 → **C14 candidate**
  - H127's core intuition was partly real; it just needed residualization against C8
- **H126 MIXED** — 90d/120d continuation is real but redundant
  - `xs_ret_90d_lag_rank`: IC +0.0108, 11/11 years, corr C11 = +0.775
  - `xs_ret_120d_lag_rank`: IC +0.0109, 10/11 years, corr C11 = +0.664
  - sector-neutral variants fall below the 0.01 gate
  - Verdict: reject as a restatement of C11
- **C13/C14 MATRIX UPDATE** — `data_tools/build_rl_signal_matrix.py` now exports `c13_compress_blowoff_2` and `c14_clv_volconf_resid_rank`
  - resulting matrix: `data/features/xs_rl_signal_matrix.parquet` (826,404 rows x 16 cols)
- **PAIRWISE CHECK** — C13 remains orthogonal to the current promoted set
  - max corr vs existing candidates: +0.154
  - corr vs C12: +0.006
- **PAIRWISE CHECK** — C14 remains orthogonal to the current promoted set
  - max corr vs existing candidates: +0.099
  - corr vs C13: -0.002

### Session 43 experiment results (2026-03-28)
- **H125 FAIL** — residualized beta has no surviving edge
  - `xs_beta_resid_60d_rank`: IC -0.0019
  - `xs_low_beta_resid_60d`: IC +0.0019
- **H127 MIXED** — close-location with volume confirmation passes standalone but is a duplicate of C8
  - `xs_clv_volconf_5d_rank`: IC +0.0149, 11/11 years, corr S1 = +0.105
  - pairwise corr vs C8 = +0.903 → rejected as redundant
  - plain close-location ranks are anti-predictive
- **H128 FAIL** — compression breakout continuation is strongly wrong-way
  - best feature `xs_compress_breakout_2`: IC -0.0351
  - the tested breakout-follow-through thesis is anti-predictive
- **H130 PASS** — confirmed gap absorption adds a new microstructure axis
  - `xs_gap_absorb_1`: IC +0.0117, 11/11 years, corr C4 = +0.298 → passes but weaker
  - `xs_gap_absorb_2`: IC +0.0334, 10/11 years, corr C4 = +0.453 → redundant with C4
  - `xs_gap_absorb_3`: IC +0.0284, 11/11 years, corr S1 = +0.131, corr C4 = +0.202 → **C12 candidate**
- **H131 FAIL** — sector breadth shock has no standalone value
  - best feature `xs_breadth_shock_laggard`: IC -0.0034
- **H132 FAIL** — conditional liquidity release remains below threshold
  - best feature `xs_liq_release_1`: IC +0.0067
- **C12 MATRIX UPDATE** — `data_tools/build_rl_signal_matrix.py` now exports `c12_gap_absorb_3`
  - resulting matrix: `data/features/xs_rl_signal_matrix.parquet` (826,404 rows x 14 cols)
- **PAIRWISE CHECK** — C12 remains orthogonal to the current promoted set
  - corr vs C4: +0.202
  - corr vs C5: +0.005
  - corr vs C6: -0.032
  - corr vs C7: +0.037
  - corr vs C8: +0.027
  - corr vs C9: -0.004
  - corr vs C10: -0.146
  - corr vs C11: -0.017

### Session 40-43 experiment results (2026-03-28)
- **H121 PASS** — xs_illiq_level_rank IC +0.021 (10/11 years), corr S1=+0.008 → **C10 candidate**
  - Script: `analysis/h121_amihud_illiquidity_standalone.py`
  - Artifact: `artifacts/run_summaries/20260328_113807_h121_amihud_illiquidity_standalone_signal.json`
- **H113 FAIL** — Earnings quality 394T: best IC=+0.006 (xs_eps_yoy_rank), all below 0.01 gate. Path closed.
- **H122 FAIL** — Bid-ask spread (Corwin-Schultz) tested and rejected
  - Script: `analysis/h122_bid_ask_spread_standalone.py`
  - Artifact: `artifacts/run_summaries/20260328_120457_h122_bid_ask_spread_standalone_signal.json`
- **H123 PASS** — 60d excess-return rank passed with IC +0.0101 (9/11 years), corr S1=+0.008. The reversal orientation failed, so the promoted signal is medium-term continuation.
  - Script: `analysis/h123_3m_reversal_standalone.py`
  - Artifact: `artifacts/run_summaries/20260328_121637_h123_3m_reversal_standalone_signal.json`
  - Promoted to **C11**
- **H124 MIXED** — low-beta orientation passed standalone (IC +0.0131, 7/11 years) but beta regime is redundant with C10.
  - Script: `analysis/h124_beta_regime_standalone.py`
  - Artifact: `artifacts/run_summaries/20260328_121804_h124_beta_regime_standalone_signal.json`
  - Pairwise corr vs C10: +0.5524
  - **Rejected** for RL state
- **C10/C11 MATRIX UPDATE** — `data_tools/build_rl_signal_matrix.py` now exports `c10_illiq_level_rank` and `c11_ret_60d_lag_rank`
  - Resulting matrix: `data/features/xs_rl_signal_matrix.parquet` (826,404 rows x 13 cols)
- **PAIRWISE CHECK** — C10 remains orthogonal to the other candidates
  - corr vs C4: -0.1224
  - corr vs C5: +0.0313
  - corr vs C6: +0.0150
  - corr vs C7: +0.0044
  - corr vs C8: +0.0184
  - corr vs C9: +0.0012
  - corr vs C11: -0.0686
- **PAIRWISE CHECK** — H124 low-beta signal does not qualify as an RL candidate
  - corr vs C10: +0.5524
  - corr vs S1: -0.0051
  - Low-beta is mostly the same axis as illiquidity/size, so it stays out of the matrix

### Session 45 experiment results (2026-03-28)
- **H135 IMPLEMENTED** — realistic deterministic portfolio baseline for the promoted RL signal library
  - script: `analysis/h135_signal_library_portfolio_baseline.py`
  - engine: `src/deterministic_portfolio.py`
  - tradability artifact published: `data/features/execution/tradability_daily.parquet`
- **INITIAL BASELINE RESULT WAS WRONG-SCALED**
  - the first `full_library` blend averaged raw signal columns directly
  - Session 46 found that `C4` and `C5` were not on a common `0-1` rank scale inside the matrix
  - the Session 45 `full_library` fail should be treated as a logging artifact, not the final scientific verdict
- **CAPACITY STRESS REMAINS VALID**
  - `1B VND` notional with `1% ADV20` participation leaves the system ~`99.9%` in cash
  - capacity is still a first-order stress dimension, not a safe default constant

### Session 46 experiment results (2026-03-28)
- **H135 CORRECTED** — non-presence signals are now cross-sectionally ranked by date before blending
  - `s1_only`: `-68.33%` total, `-10.01%` annualized, IR `-0.57`
  - `recent_core`: `-46.81%` total, `-5.63%` annualized, IR `-0.40`
  - `full_library`: `+72.10%` total, `+5.11%` annualized, IR `-0.05`
  - benchmark VNINDEX: `+223.17%` total over the same 2015-2025 window
- **H136 PASS** — deterministic portfolio construction materially improves monetization
  - script: `analysis/h136_portfolio_construction_sweep.py`
  - best configuration: `top_k=5`, rebalance every `5` signal days, `equal` weighting
  - score gate is effectively irrelevant in the winning region (`none`, `0.521`, `0.570` tie)
  - best result: `+1105.71%` total, `+25.66%` annualized, `+273.09%` relative vs VNINDEX, IR `0.50`, max DD `-59.76%`, `8/11` positive years
- **SWEEP PATTERN**
  - `5d` cadence dominates the grid; `10d` is the next-best regime; `3d` is materially worse
  - `equal` weighting beats `linear` and `square`
  - `top_k=5` is best absolute performer; `top_k=8/10` are competitive but lower
- **STRATEGIC VERDICT**
  - do not pivot to RL yet
  - the next honest bottleneck is validating and capacity-stressing the deterministic portfolio candidate
  - RL should be treated as a later overlay that must beat this deterministic baseline

### Session 47 experiment results (2026-03-28)
- **H137 IMPLEMENTED** — nested walk-forward portfolio-construction selection
  - script: `analysis/h137_nested_portfolio_selection.py`
  - helper module: `src/portfolio_construction_search.py`
  - protocol: pick the best H136-style config on train years only, then test on the next year
- **H137 FAIL** — simple ML-style config selection does not validate out of sample
  - stitched OOS test years `2019-2025`
  - `+21.38%` total, `+2.84%` annualized
  - `-42.46%` relative vs VNINDEX
  - information ratio `-0.08`
  - max drawdown `-55.65%`
- **SELECTION PATTERN**
  - selected configs are mostly simple:
    - `top_k=5`, `rebalance_every=10`, `equal` weighting chosen `4/7` test years
    - early years briefly choose `top_k=3`, `5d`, `equal`
    - one year chooses `top_k=10`, `5d`, `equal`
  - this is not a case where exotic weighting or thresholding saves the result
- **STRATEGIC VERDICT**
  - direct “machine learns the best config” is not production-ready from this dataset
  - full-sample H136 winner is too optimistic
  - next work should either simplify further or move toward hedged constructions instead of adding more ML complexity

### Session 48 next queue (in order)

1. **Honest fixed-rule validation on the reduced menu**
   - compare a tiny candidate set only:
     - `top_k=5`, `cadence=10`, `equal`
     - `top_k=5`, `cadence=5`, `equal`
     - `top_k=3`, `cadence=5`, `equal`
   - test whether one simple rule is robust enough without yearly re-selection
2. **If long-only still cannot beat benchmark honestly**
   - move to hedged constructions
   - benchmark-hedged / long-short lite
   - sector-neutral variants
3. **Capacity and fee stress**
   - only on the reduced-menu candidates that survive honest validation
4. **Do not expand ML complexity yet**
   - no larger selector model
   - no portfolio RL overlay until a deterministic honest baseline is competitive

### Remaining blocked paths
- **H98 LLM Sentiment** — PARKED (runtime/throughput bottleneck; re-open when local inference restored)
- **H95 Foreign flow** — BLOCKED (historical daily data not available via vnstock)
- **Order book imbalance** — BLOCKED (intraday data not available historically)

---

## Working Rules

- 2026 data: monitor-only. Do not use for tuning.
- For any material experiment, save a compact result summary and update notes.
- Archived reasoning lives in session logs; this file stays lean.
