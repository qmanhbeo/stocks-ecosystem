"""
H405: Sector Event Lightcone (Neighbor Propagation)
Test whether sector-peer events predict ticker returns even when ticker has no event.
Uses sector as neighbor proxy, Ollama event family as event source.
Compares: ticker-with-event vs sector-peers-with-event vs isolated.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET_COL = "actual"
SCORE_COL = "xs_proba"
BRANCH_NAME = "sector_event_lightcone"
MODE = "research_branch"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H405 Sector Event Lightcone test")
    parser.add_argument("--s1-path", type=str, default=str(ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet"))
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def compute_ic(panel: pd.DataFrame, score_col: str, target_col: str) -> float:
    valid = panel[[score_col, target_col]].dropna()
    if len(valid) < 50:
        return np.nan
    ic, _ = spearmanr(valid[score_col], valid[target_col])
    return ic


def compute_yearly_ics(panel: pd.DataFrame, score_col: str, target_col: str) -> dict[int, float]:
    panel = panel.copy()
    panel["year"] = pd.to_datetime(panel["time"]).dt.year
    ics = {}
    for year, year_df in panel.groupby("year"):
        ic = compute_ic(year_df, score_col, target_col)
        ics[year] = ic
    return ics


def main():
    args = parse_args()
    
    print("Loading S1 panel...")
    panel = pd.read_parquet(
        args.s1_path,
        columns=["ticker", "time", SCORE_COL, TARGET_COL],
    )
    panel = panel[panel["time"] >= f"{args.start_year}-01-01"]
    panel = panel[panel["time"] <= f"{args.end_year}-12-31"]
    
    print("Loading Ollama events...")
    ollama = pd.read_parquet(
        ROOT / "data/features/news/datasets/ollama_guarded_ticker_day_features.parquet",
        columns=["ticker", "date", "ollama_guarded_article_count_5d", "ollama_guarded_event_family_earnings_share",
                "ollama_guarded_event_family_dividend_share", "ollama_guarded_event_family_guidance_share",
                "ollama_guarded_event_family_macro_or_sector_share"],
    )
    ollama["time"] = pd.to_datetime(ollama["date"])
    ollama = ollama.drop(columns=["date"])
    panel = panel.merge(ollama, on=["ticker", "time"], how="left")
    
    print("Loading sector data...")
    sector = pd.read_parquet(
        ROOT / "data/features/xs_sector_rotation_daily.parquet",
        columns=["ticker", "time", "xs_intra_sector_rank", "xs_sector_mom_5d_rank"],
    )
    panel = panel.merge(sector, on=["ticker", "time"], how="left")
    
    panel = panel[
        panel[SCORE_COL].notna() & 
        panel[TARGET_COL].notna() &
        panel["ollama_guarded_article_count_5d"].notna()
    ].copy()
    
    panel["has_own_event"] = (panel["ollama_guarded_article_count_5d"] > 0).astype(int)
    
    sector_event_count = panel.groupby(["time", "xs_intra_sector_rank"])["ollama_guarded_article_count_5d"].transform("sum")
    panel["sector_event_sum"] = sector_event_count - panel["ollama_guarded_article_count_5d"]
    panel["sector_has_event"] = (panel["sector_event_sum"] > 0).astype(int)
    
    panel["has_own_event_vs_sector"] = (
        (panel["has_own_event"] == 1) & (panel["sector_has_event"] == 1)
    ).astype(int)
    panel["no_own_event_but_sector"] = (
        (panel["has_own_event"] == 0) & (panel["sector_has_event"] == 1)
    ).astype(int)
    panel["sector_event_intensity"] = panel["sector_event_sum"] / (panel["sector_event_sum"].max() + 1)
    
    print(f"\nPanel rows: {len(panel):,}")
    print(f"Has own event: {panel['has_own_event'].sum():,}")
    print(f"Sector has event: {panel['sector_has_event'].sum():,}")
    print(f"No own but sector has: {panel['no_own_event_but_sector'].sum():,}")
    
    ic_c16 = np.nan
    ic_own = compute_ic(panel, "ollama_guarded_article_count_5d", TARGET_COL)
    ic_sector_intensity = compute_ic(panel, "sector_event_intensity", TARGET_COL)
    ic_no_own_sector = compute_ic(panel[panel["no_own_event_but_sector"]==1], "sector_event_intensity", TARGET_COL)
    
    yearly_own = compute_yearly_ics(panel, "ollama_guarded_article_count_5d", TARGET_COL)
    yearly_sector = compute_yearly_ics(panel, "sector_event_intensity", TARGET_COL)
    
    print(f"\n=== H405 Sector Event Lightcone Results ===")
    print(f"\n--- Overall IC ---")
    print(f"  Own event (5d count):   {ic_own:+.5f}")
    print(f"  Sector event intensity: {ic_sector_intensity:+.5f}")
    print(f"  No own + sector intensity (subset): {ic_no_own_sector:+.5f}")
    
    print(f"\n--- Own event by year ---")
    for yr, ic in sorted(yearly_own.items()):
        print(f"    {yr}: {ic:+.5f}")
    
    print(f"\n--- Sector intensity by year ---")
    for yr, ic in sorted(yearly_sector.items()):
        print(f"    {yr}: {ic:+.5f}")
    
    pos_years_own = sum(1 for ic in yearly_own.values() if ic > 0)
    pos_years_sector = sum(1 for ic in yearly_sector.values() if ic > 0)
    print(f"\n--- Positive years ---")
    print(f"  Own event: {pos_years_own}/{len(yearly_own)}")
    print(f"  Sector intensity: {pos_years_sector}/{len(yearly_sector)}")
    
    result = {
        "own_event_ic": ic_own,
        "sector_event_intensity_ic": ic_sector_intensity,
        "no_own_sector_intensity_ic": ic_no_own_sector,
        "own_event_yearly_ic": yearly_own,
        "sector_intensity_yearly_ic": yearly_sector,
    }
    
    artifact_path = (
        ROOT / "artifacts/run_summaries" /
        f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}_{BRANCH_NAME}_{MODE}.json"
    )
    
    import json
    with open(artifact_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nSaved: {artifact_path}")
    
    print(f"\n=== VERDICT ===")
    if ic_sector_intensity > 0.01 and pos_years_sector >= 6:
        print("PASSED: Sector event adds beyond own-ticker")
    elif ic_sector_intensity > ic_own:
        print("MIXED: Sector alone better than own-ticker")
    elif ic_no_own_sector > 0.01:
        print("MIXED: No-own-but-sector subset is positive")
    else:
        print("FAILED: Sector events add no signal")


if __name__ == "__main__":
    main()