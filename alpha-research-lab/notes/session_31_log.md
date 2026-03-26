# Session 31 Log — H97 Insider Deals (2026-03-26)

## Objectives
- H97: Insider trading data — probe, fetch, feature-build, and XS WF test
- Unblocked from Session 30 (was 403 Forbidden in cloud; WSL has full access)

## System State (entering)
- H93: best signal — IC +0.1491, Sharpe 15.08 (N=5, no VIX filter), edge std 1.60%, 11/11 years
- C1: candidate signal — standalone IC +0.043, too sparse for XS WF
- News path exhausted (F62–F65)

---

## Data Source Discovery

**KBS API (`kbbuddywts.kbsec.com.vn/iis-server/investment/stockinfo/news/internal-trading/`):**
- Returns HTTP 200 but empty `[]` for all tickers — endpoint exists but has no data

**VCI Company.insider_deals():** Method listed in API wrapper but underlying VCI explorer
has no implementation — AttributeError at runtime.

**CafeF GDCoDong API (confirmed working):**
```
https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx
  ?Symbol=FPT&StartDate=01/01/2015&EndDate=01/01/2026&PageIndex=1&PageSize=500
```
- Returns insider + large-shareholder transaction disclosures
- `ShareHolderCode` prefix: `CEO_` = officers/directors, `LQ_` = related persons, `CORP_` = corporate
- `PublishedDate` = disclosure filing date (safe signal date, no look-ahead)
- `PlanBuyVolume` / `PlanSellVolume` = announced intention at disclosure date
- Date range: 2015–2026 for most tickers

---

## Data Fetch

**Script:** `data_tools/fetch_insider_deals.py`
- Crawled 394 HOSE tickers at 0.2s/request (~80 seconds total)
- All 394 tickers returned data (0 skipped)
- Raw combined: 32,239 insider rows + 14,747 large-shareholder rows
- Cache: `data/insider_cache/<TICKER>.parquet` (394 files)
- Combined: `data/features/xs_insider_deals_raw.parquet`

---

## Feature Engineering

**Script:** `data_tools/build_insider_features.py`
- Grid: 826,404 rows (2,748 trading days × 394 tickers)
- Features: `insider_net_plan_5d/30d`, `insider_net_real_5d/30d`, `insider_buy/sell_flag_5d`, `large_sh_net_plan_5d/30d`
- Backward rolling: shift(1) to prevent look-ahead
- Output: `data/features/xs_insider_features.parquet`

**Coverage:**
| Feature | Non-zero rows | % |
|---------|-------------|---|
| insider_net_plan_5d | 29,513 | 3.57% |
| insider_net_plan_30d | 135,412 | 16.39% |
| insider_net_real_5d | 27,974 | 3.39% |
| insider_net_real_30d | 129,792 | 15.71% |
| large_sh_net_plan_30d | 55,454 | 6.71% |

**Standalone IC (insider_net_plan_5d vs 5d relative return, non-zero rows only):**
- 2019: IC=+0.038 (p=0.042*)
- 2020: IC=+0.061 (p=0.001*)
- 2021: IC=+0.012 (not sig)
- 2023: IC=+0.068 (p=0.004*)
- 2024: IC=+0.048 (p=0.020*)
- Average: +0.0255, 9/11 years positive
- Correlation with H93 proba: −0.027 (near-zero → genuinely independent)

---

## Experiment H97: XS WF with Insider Features

**Command:**
```bash
python cross_sectional_wf.py --use-volume-signals --barrier-pct 0.01 --target-horizon 1 \
  --use-insider \
  --save-all-probas data/features/xs_barrier_vol_1d_insider_hose_full.parquet
```

**Results (portfolio eval with --no-vix-filter):**
| Metric | H93 (baseline) | H97 (+insider) | Delta |
|--------|---------------|----------------|-------|
| IC (Spearman) | +0.1491 | +0.1484 | −0.0007 |
| Sharpe (N=5) | 15.08 | 10.77 | −4.31 |
| Edge std (N=5) | 1.60% | 2.26% | +0.66% |
| Sig years | 11/11 | 11/11 | 0 |

**Artifact:** `data/features/xs_barrier_vol_1d_insider_hose_full.parquet`

**Root cause:** Insider features are sparse (3.57%). XGBoost introduces them as occasional
tree splits, adding variance on the 96.43% of zero rows without proportional gain on event rows.
Same mechanism as news features (F62–F65).

**Verdict: FAIL (F66)**

---

## Infrastructure Created This Session

| Asset | Purpose |
|-------|---------|
| `data_tools/fetch_insider_deals.py` | CafeF GDCoDong crawler for all HOSE tickers |
| `data_tools/build_insider_features.py` | Rolling 5d/30d insider feature builder |
| `data/insider_cache/*.parquet` | Per-ticker raw cache (394 files) |
| `data/features/xs_insider_deals_raw.parquet` | Combined 32k rows raw insider data |
| `data/features/xs_insider_features.parquet` | 826k row feature matrix |
| `data/features/xs_barrier_vol_1d_insider_hose_full.parquet` | H97 WF probas |
| `--use-insider` flag in `cross_sectional_wf.py` | H97 insider feature loading |

---

## Session Conclusions

1. **H93 unchanged** — Sharpe 15.08 remains best signal
2. **H97 FAIL** — insider features hurt Sharpe (−4.31) despite genuine standalone IC (+0.025)
3. **Same root cause as news** — sparsity + XGBoost tree interaction
4. **Insider signal is RL-candidate C2** (like C1/news) — orthogonal to S1 with measurable standalone IC
5. **CafeF GDCoDong is a reliable data source** — all 394 tickers have data, free, no auth required

---

## Production System After This Session

H93 unchanged: IC +0.1491, Sharpe 15.08, edge std 1.60%.
Signal library: S1 = CONFIRMED (unchanged), C1 = CANDIDATE, C2 (insider) = NEW CANDIDATE.

---

## Next Session Priority (Session 32)

| Experiment | Hypothesis | Status |
|---|---|---|
| H98 | LLM news sentiment | Needs LLM API key |
| New direction | Non-sparse signals (fundamental ratios, price patterns) | Open |
| Ensemble approach | RL blending of S1 + C1 + C2 | Requires RL framework |
