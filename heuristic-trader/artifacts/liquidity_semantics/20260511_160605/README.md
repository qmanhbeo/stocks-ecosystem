# Liquidity Semantics Diagnostic Output

Generated: 2026-05-11T16:06:05.735753

## What Was Analyzed

- Analyzed 30 liquidity-divergent rows
- Compared legacy `check_liquid()` vs precomputed `is_liquid()`

## Key Finding

**PROVEN MISMATCH**: The precomputed liquid_lookup was NOT built with the same algorithm as legacy check_liquid(). Two patterns observed:

1. **False Negative in precomputed**: Legacy says liquid, precomputed says NOT liquid (e.g., BSR on 2024-01-15: volume 5.2M > 500K, price_change 2.1% > 0.1%, but ticker NOT in liquid_lookup[date])

2. **False Positive in precomputed**: Legacy says NOT liquid, precomputed says liquid (e.g., POW on 2024-01-15: price_change 0% < 0.1%, but ticker IS in liquid_lookup[date])

- Legacy fallback used: 0 cases (dates DO exist in price cache)
- Exact date missing from price cache: 0 cases

**Root cause hypothesis**: The liquid_lookup.joblib was built with either:
- Different data version (stale cache)
- Different algorithm (strict i>=4 requirement vs lenient max(0,idx-5) window start)

## Output Files

- `sample_liquidity_diagnostics.csv` - Per-row detailed diagnostics
- `summary.json` - Summary statistics
- `README.md` - This file

## What Was NOT Changed

- No backtest behavior modified
- No caches rebuilt
- No research conclusions altered

## Semantic Comparison

| Aspect | Legacy check_liquid() | Precomputed liquid_lookup |
|--------|----------------------|---------------------------|
| Date handling | Falls back to last date if exact date missing | Only contains dates that exist in price cache |
| Window | Variable: max(0, idx-5) to idx+1 | Fixed 5-row positional window |
| Missing date | Uses older window silently | Returns False (fail closed) |

This explains the 512 liquidity divergences found in the first diagnostic.
