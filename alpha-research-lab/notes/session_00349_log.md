# Session 349 - H541 Capacity-Volume-Breadth Triple

## Hypothesis
Test tight_capacity (H474) × vol_expansion (H446) × low_breadth (H529). Three confirmed amplifiers combined.

## Command
```bash
cd alpha-research-lab && conda run -n stocks python analysis/h541_capacity_volume_breadth_triple.py
```

## Result
**FAILED (data-gated)** - Volume data loading insufficient (only 100 stock files, NaN for most rows). All vol-related states had 0 rows.

## Key Finding
The volume data from stock parquet files couldn't be loaded reliably. Need alternative vol_expansion definition or data source.

## Partial Result
- tight_low_breadth (two-way): IC=0.1890 (consistent with H531)
- tight_capacity only: IC=0.1588
- low_breadth only: IC=0.1423

## Verdict: FAILED (data-gated)