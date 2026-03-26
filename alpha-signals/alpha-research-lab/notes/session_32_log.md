# Session 32 Log — C2 Standalone Insider Portfolio (2026-03-26)

## Objectives
- Resume the pending Session 32 quick win:
  - Test pure insider-signal portfolio
  - On signal days, rank by `insider_net_plan_5d`
  - Measure next-5d relative outperformance

---

## Experiment Setup

**Script added:** `analysis/c2_insider_standalone.py`

**Inputs:**
- `data/features/xs_insider_features.parquet`
- `data/stock/gia_lich_su_*_1D.parquet`

**Method:**
1. Rebuild `future_rel_return_5d` for each stock from existing feature pipeline.
2. Merge with insider feature matrix on `(trading_day, ticker)`.
3. Keep signal rows where `insider_net_plan_5d != 0`.
4. Build event-day long portfolios:
   - Top-1 by insider signal
   - Top-3 by insider signal
   - Top-5 by insider signal
5. Evaluate average 5d relative edge and yearly stability.

**Run:**
```bash
conda run -n stocks python analysis/c2_insider_standalone.py
```

---

## Results

**Artifacts:**
- `artifacts/run_summaries/20260326_150012_c2_insider_standalone_standalone_signal.json`
- `artifacts/run_summaries/20260326_150012_c2_insider_standalone_details.json`

**Coverage / signal stats:**
- Signal rows: 29,513 / 826,402 (**3.57%**)
- Signal days: 2,742 / 2,748 (**99.78%**)
- Standalone IC on signal rows: **+0.0256**, positive in **9/11** years

**Portfolio edge (next-5d relative return):**
- Top-1: **-0.304%**
- Top-3: **+0.049%**
- Top-5: **+0.090%**
- Top-5 Sharpe proxy: **+0.51**
- Top-5 positive years: **5/11**

---

## Interpretation

1. C2 remains a weak but real standalone signal at the IC level.
2. The naive standalone event-day portfolio is **not robust enough** for deployment:
   - modest average edge for Top-5
   - only 5/11 positive years
   - weak risk-adjusted profile
3. C2 is still best treated as an RL-side candidate feature, not a standalone strategy.

---

## Session Conclusion

**Verdict:** C2 standalone strategy test complete; **MIXED/NOT TRADEABLE as-is**.

H93 remains the best executable RL training signal.
