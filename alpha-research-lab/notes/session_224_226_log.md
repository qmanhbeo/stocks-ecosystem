# Sessions 224-226: New C16 Branches

Date: 2026-05-03
Focus: Test sector-relative, persistence, market-state

## X224: Sector-Relative C16
- Result: IC +0.066 vs baseline +0.078 (-15%)
- **Verdict: FAILED** - removing sector bias hurts signal

## X225: C16 Persistence  
- Result: IC +0.065 vs baseline +0.078 (-17%)
- **Verdict: FAILED** - persistence filter doesn't help

## X226: Market-State Dependent
- Result: **UP days: +0.056**, **DOWN days: +0.098**
- **Diff: -0.043** (down much stronger!)
- **Verdict: PASSED** - C16 works BETTER in down markets (+26%)

## Key Finding

**C16 is a CONTRARIAN signal.** It works when others are selling.
- In bear markets: buy pressure = rare = strong signal
- In bull markets: buy pressure = common = weak signal

This explains WHY C16 works: it's capturing contrarian flow.

## Scripts

- x224_sector_relative.py — FAILED
- x225_c16_persistence.py — FAILED  
- x226_market_state.py — PASSED

## Next Steps

- Strategy change: Use C16 differently in up vs down markets
- Could size up in down markets, size down in up