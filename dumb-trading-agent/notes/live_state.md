# Live State

## Current

**S00005: Pre-computed lookups working**

- 70%S1/30%C16: ~82% (legacy, ~5min)
- Pre-computed quick run: ~2.5sec

## Cached Artifacts

- cache/vnindex_baseline.parquet
- cache/price_cache.parquet  
- cache/liquid_lookup.joblib (4764 dates)
- cache/trad_lookup.joblib (666k entries)

## Speed 

- Without filters: ~5 sec
- Pre-computed: ~2.5 sec  
- Legacy (truth): ~5 min

## Next (queue)

1. ~~S1 10-day rebal~~ → +43%
2. ~~S1+C16 blend~~ → +52%
3. ~~Blend weight 70/30~~ → +82%
4. Grid search with pre-computed
5. Verify with legacy

## Pointers
- backtest.py, session_00005.py, signals.py