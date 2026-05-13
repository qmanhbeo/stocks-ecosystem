# Session 45 Log

## Objective
Implement a realistic deterministic portfolio baseline for the promoted RL signal library and use it
to answer the strategic question: should the lab pivot directly into RL training, or does portfolio
construction still need to be solved first?

## Implementation
Added:
- `src/deterministic_portfolio.py`
  - reusable deterministic backtest engine
  - next-open execution
  - `T+2.5` sellability enforcement (`T+3` close decision, `T+4` open exit fill)
  - zero-volume / ceiling / floor tradability blocks
  - simple ADV participation cap support
  - daily and annual metrics
- `analysis/h135_signal_library_portfolio_baseline.py`
  - compares `s1_only`, `recent_core`, and `full_library`
  - writes compact JSON summary plus daily parquet curves
- `tests/test_deterministic_portfolio.py`
  - early-sell blocking
  - unbuyable-stock blocking

Docs updated:
- `README.md`
- `README_for_AGENTS.md`

Shared artifact published:
- `data/features/execution/tradability_daily.parquet`

## Validation
Passed:
- `python -m py_compile` on the new engine, analysis script, and tests
- `pytest -q tests/test_tradability_flags.py tests/test_deterministic_portfolio.py`
- `git diff --check`

## H135 baseline run
Command:
```bash
conda run -n stocks env PYTHONPATH=/home/manh/stocks/shared-market-rules:/home/manh/stocks/alpha-research-lab \
  python analysis/h135_signal_library_portfolio_baseline.py
```

Contract used in the saved baseline:
- 2015-2025
- top-5 equal-weight
- rebalance every 3 signal days
- 0.30% RT cost (`0.15%` buy + `0.15%` sell)
- no ADV cap in the baseline run
- tradability source = published artifact

Artifact:
- `artifacts/run_summaries/20260328_163735_h135_signal_library_portfolio_baseline_portfolio_baseline.json`
- `artifacts/portfolio_baselines/20260328_163735_h135_signal_library_portfolio_baseline_daily.parquet`

Results:
| Strategy | Total Return | Annualized | Relative vs VNINDEX | Info Ratio | Max DD | Positive Years |
|---|---:|---:|---:|---:|---:|---:|
| `s1_only` | -68.33% | -10.01% | -90.20% | -0.57 | -88.84% | 4/11 |
| `recent_core` | -83.44% | -15.21% | -94.88% | -0.67 | -96.19% | 3/11 |
| `full_library` | -9.76% | -0.94% | -72.08% | -0.24 | -77.25% | 5/11 |

Benchmark:
- VNINDEX total return over the same window: `+223.17%`

## Capacity stress check
Early stress run using:
- portfolio notional = `1B VND`
- `1%` ADV20 participation cap

Artifact:
- `artifacts/run_summaries/20260328_163426_h135_signal_library_portfolio_baseline_portfolio_baseline.json`

Key outcome:
- all strategies stayed `~99.9%` in cash on average
- capacity is a first-order stress variable, not a harmless default assumption

## Verdict
The promoted signal library is not yet a realistic long-only monetization layer.

The practical implication is:
- do **not** treat RL as the next shortcut to money
- solve deterministic portfolio construction first
- then use RL only if it can beat that deterministic baseline under the same execution rules

## Next queue
1. Sweep deterministic portfolio construction on `full_library`:
   - `top_k`
   - rebalance cadence
   - weighting rule (`equal`, `linear`, `square`)
   - optional signal threshold / cash gating
2. Run capacity sensitivity grid:
   - portfolio notional
   - ADV participation cap
3. If long-only still fails, test hedged / sector-neutral constructions before more RL
