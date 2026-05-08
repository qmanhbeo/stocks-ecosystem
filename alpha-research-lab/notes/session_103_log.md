# Session 103 Log

## Objective
Run H447 volume_adjusted_price_momentum experiment from the NEW EUREKA queue (item K).

Hypothesis: Price normalized by volume captures "expensive" vs "cheap" moves.
Same return on higher volume = real force (real demand), 
same return on lower volume = fade (crowd blowoff).

This session did not change the live branch.
It did not read 2026+.

## Starting point
- H446 volatility_regime_transition PASSED (vol_expansion +4.49% IC lift)
- Queue had item K: volume_adjusted_price_momentum as next

## What changed
Added:
- `analysis/h447_volume_adjusted_price_momentum.py`

Method:
- Loaded order_stats data, parsed price_change_raw percentage  
- Computed volume_z (standardized total volume by date)
- Created return/volume buckets: high/low return × high/low volume
- Created return_per_volume ratio buckets: expensive (top 20%), cheap (bottom 20%)

Saved artifacts:
- `artifacts/run_summaries/20260508_174916_volume_adjusted_price_momentum_research_branch.json`

## Results

| State | Avg IC | Lift vs Baseline | Positive Years |
|-------|--------|------------------|----------------|
| all_rows (baseline) | 0.1299 | - | 11/11 |
| **low_return_low_vol** | **0.2045** | **+0.0746** | 11/11 |
| cheap_move | 0.1547 | +0.0248 | 11/11 |
| fade_move | 0.1428 | +0.0129 | 11/11 |
| high_return_low_vol | 0.1428 | +0.0129 | 11/11 |
| expensive_move | 0.1424 | +0.0125 | 11/11 |
| real_force (high_return_high_vol) | 0.1109 | -0.0190 | 11/11 |
| low_return_high_vol | 0.0726 | -0.0573 | 10/11 |

## Key Finding: MIXED (OPPOSITE of hypothesis!)

**The hypothesis was INVERTED:**
- Hypothesis: high return + high volume = real force (positive)
- Reality: high return + high volume = WEAKEST (-0.019 IC lift)
- Hypothesis: high return + low volume = fade (negative)
- Reality: high return + low volume = POSITIVE (+0.013 IC lift)

**What actually works:**
- **low_return_low_vol** is the STRONGEST state: IC=0.2045 vs baseline 0.1299 (+7.46% lift!)
- This is a MEAN-REVERSION signal: stocks that moved down with low volume have the best S1 quality next day
- "Cheap moves" (low return + low volume) capture mean reversion, not "real force"

**Interpretation:**
- The original hypothesis was about momentum (real force = sustained)
- The actual finding is about contrarian (cheap moves = reversal opportunity)
- Low-volume down moves may indicate oversold conditions with hidden support

## Verdict: MIXED

The volume-adjusted framework is useful, but the direction is OPPOSITE of hypothesis:
- Use low_return_low_vol as a positive signal (contrarian)
- Do NOT use high_return_high_vol as "real force" - it underperforms

**Dead-end D036**: Original "real force" hypothesis (high return + high volume) is NOT a signal. Use the inverse: low_return_low_vol as contrarian.

**Next Steps**:
- low_return_low_vol is a strong signal but may overlap with existing stock-down signals
- Test if this is independent of stock-down/high-C16 states
- Consider as contrarian conditioner for S1 quality