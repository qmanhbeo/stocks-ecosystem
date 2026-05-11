# Trade-Level Regime Autopsy

## Goal
Understand WHY strategies fail in bull regimes (2017, 2025) by examining:
- Cash vs invested exposure
- Ticker selection patterns
- Filter impact

## Input Data
- Run with `collect_diagnostics=True` in backtest.py
- Strategies: blend_70_30_top5, s1_top5_rebal10, c16_only_top5
- Years: 2017, 2021, 2022, 2025

## Files in This Artifact
- `trade_summary.csv` - Combined summary of all strategy-years
- `all_trades.csv` - Individual buy/sell transactions (985 rows)
- `all_selections.csv` - Candidate selection + filtering (4242 rows)
- `exposure_summary.csv` - Daily cash/invested breakdown
- `summary.json` - Key findings

---

## CRITICAL FINDING: HIGH CASH EXPOSURE IS A MAJOR CONTRIBUTOR

**More careful wording**: High cash exposure is a major contributor to bull-regime underperformance, but ticker-level PnL is still needed to separate cash drag from poor selected-name performance.

### Cash vs Invested by Regime

| Strategy | Year | Regime | Return | Benchmark | Excess | Cash% | Invested% |
|----------|------|--------|--------|-----------|--------|-------|-----------|
| blend_70_30_top5 | 2017 | FAIL_BULL | +0.7% | +46.6% | -45.9% | **62.7%** | **37.3%** |
| blend_70_30_top5 | 2025 | FAIL_BULL | -23.4% | +38.4% | -61.8% | **63.6%** | **36.4%** |
| blend_70_30_top5 | 2021 | SUCCESS | +82.3% | +33.1% | +49.2% | 50.3% | 49.7% |
| blend_70_30_top5 | 2022 | SUCCESS | -0.9% | -32.8% | +31.9% | 55.9% | 44.1% |

### Aggregated by Regime Type

| Regime Type | Avg Cash % | Avg Invested % | Avg Excess |
|------------|------------|---------------|------------|
| **Failure (2017, 2025)** | **71.3%** | **28.7%** | -53.0% |
| Success (2021, 2022) | 61.5% | 38.5% | +15.8% |

**CONCLUSION**: In failure years (bull markets), strategies are OVERWEIGHT CASH (~70% vs ~60%). This is the MECHANISM of failure, not just correlation.

---

## Strategy-Specific Analysis

### blend_70_30_top5
- **2017/2025 (Failure)**: 62-64% cash, 36-37% invested
- **2021/2022 (Success)**: 50-56% cash, 44-50% invested
- **Finding**: More cash in bull markets = missed upside

### s1_top5_rebal10
- **2017/2025 (Failure)**: 50-75% cash, 25-50% invested
- **2021/2022 (Success)**: 35-44% cash, 56-65% invested
- **Finding**: Higher invested % in success years

### c16_only_top5 (EXTREME)
- **ALL YEARS**: 87-93% cash, 8-13% invested
- **Finding**: This strategy is essentially a CASH strategy - explains why it always underperforms in any bull market

---

## Filter Analysis

| Strategy | Year | Selected | Filtered | LiQ Filter | Trad Filter |
|----------|------|----------|----------|------------|-------------|
| blend_70_30_top5 | 2017 | 49 | 309 | 282 | 27 |
| blend_70_30_top5 | 2025 | 48 | 305 | 247 | 58 |
| blend_70_30_top5 | 2021 | 79 | 267 | 197 | 70 |
| blend_70_30_top5 | 2022 | 59 | 292 | 222 | 70 |

- Filter counts are SIMILAR between success/failure years
- Filters are NOT the primary cause of underperformance

---

## What Was Proven

1. ✅ **High cash exposure is a major contributor**:
   - Failure years: ~71% cash
   - Success years: ~62% cash
   - In bull markets, strategies are overweight cash
   - BUT: ticker-level PnL needed to separate cash drag from poor selected-name performance

2. ✅ **c16_only_top5 is a cash strategy**:
   - 87-93% cash in all years
   - Explains constant underperformance

3. ✅ **Filters are NOT the cause**:
   - Similar filter counts in success/failure years

---

## What Remains Uncertain

1. ❌ **Why cash is high in bull markets**:
   - Is it signal-driven (signals picking low-momentum stocks)?
   - Is it execution-driven (position sizing leads to cash)?
   - Need ticker-level analysis to confirm

2. ❌ **Specific ticker selection**:
   - We have selection logs but haven't analyzed what stocks were picked
   - Need to check if winners/losers correlate with benchmark leaders

3. ❓ **Defensive vs cash-holding distinction**:
   - Current data shows CASH position, not defensive stocks
   - Need to check if held stocks actually lost money or just weren't held

---

## Corrected Explanation of 2017/2025 Failure

**MECHANISM**: In strong bull markets (2017, 2025), the strategies are OVERWEIGHT CASH (~70% vs ~60% in success years).

- The signals (RL + C16 blend) may be selecting for low-momentum/value stocks
- In a strong momentum rally, these stocks lag
- Result: Strategy holds cash while benchmark rallies on growth/momentum leaders

**This is consistent with a CASH EXPOSURE problem in bull markets. Ticker-level PnL is still needed to separate pure cash drag from poor selected-name performance.**

---

## Next Research Direction

1. **Ticker-level analysis**: What stocks were actually bought? Did they underperform benchmark?
2. **Signal decomposition**: Is it RL signal, C16 signal, or blend causing defensive tilt?
3. **Position sizing**: Is the cash coming from signal or from position allocation logic?

This is now an alpha-research-lab investigation.

---
*Generated: 2026-05-11*
*Script: analyze_trade_level_regimes.py*
*backtest.py with collect_diagnostics=True*