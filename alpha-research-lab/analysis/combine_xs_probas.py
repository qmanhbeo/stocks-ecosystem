"""
Combine standard XS proba and barrier XS proba into a single averaged proba file.
This creates X11: (std_XS + barrier_XS) / 2 as the combined XS signal, then ensemble with E32.

Usage:
    python analysis/combine_xs_probas.py
    # Outputs: data/features/xs_combined_fpt_proba.csv
"""
import pandas as pd
from path_utils import data_path

xs_std = pd.read_csv(data_path("features/xs_fpt_proba.csv"), parse_dates=["time"])
xs_barrier = pd.read_csv(data_path("features/xs_barrier_fpt_proba.csv"), parse_dates=["time"])

m = xs_std.merge(xs_barrier[['time', 'xs_proba']], on='time', suffixes=('_std', '_barrier'))
m['xs_proba'] = (m['xs_proba_std'] + m['xs_proba_barrier']) / 2

out = m[['time', 'year', 'xs_proba', 'actual']].copy()
out.to_csv(data_path("features/xs_combined_fpt_proba.csv"), index=False)
print(f"Combined XS proba saved: {len(out)} rows, {out['year'].nunique()} years")
print(f"  Std XS range:     [{m['xs_proba_std'].min():.3f}, {m['xs_proba_std'].max():.3f}]")
print(f"  Barrier XS range: [{m['xs_proba_barrier'].min():.3f}, {m['xs_proba_barrier'].max():.3f}]")
print(f"  Combined range:   [{out['xs_proba'].min():.3f}, {out['xs_proba'].max():.3f}]")
