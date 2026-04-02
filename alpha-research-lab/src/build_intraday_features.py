"""
build_intraday_features.py -- Extract daily features from FPT 1H intraday data.

The 1H data captures intraday price dynamics invisible at daily resolution:
- First-hour momentum: how strong was the open?
- Morning vs afternoon: is PM following AM direction?
- Intraday reversal: does high-vol morning predict afternoon reversal?
- Volume timing: where is the volume concentrated?

Output: data/features/fpt_intraday_daily.parquet
  date, fh_ret, am_ret, pm_ret, pm_vs_am, vol_am_frac,
  intraday_hi_low (=daily range from 1H), open_close_pct

NOTE: Only available from 2023-09 onward (VCI API limitation).
Features are aligned to trading date (no look-ahead).

Run: conda run -n stocks python src/build_intraday_features.py
"""
import pandas as pd
import numpy as np
from pathlib import Path
from src.repo_paths import data_path


FPT_1H_FILE = data_path("stock/gia_lich_su_FPT_1H.parquet")
OUT_DIR  = data_path("features")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "fpt_intraday_daily.parquet"


def main():
    df = pd.read_parquet(FPT_1H_FILE)
    df["time"] = pd.to_datetime(df["time"])
    df["date"] = df["time"].dt.date
    df = df.sort_values("time").reset_index(drop=True)
    print(f"Loaded {len(df)} hourly bars, {df['date'].nunique()} trading days")

    records = []
    for date, day_df in df.groupby("date"):
        day_df = day_df.sort_values("time")
        if len(day_df) < 2:
            continue

        # Session split: morning = 10:00-11:30, afternoon = 13:00-15:00
        # Vietnamese market hours: 9:00 ATO, 9:15-11:30 morning, 13:00-15:00 afternoon
        hours = day_df["time"].dt.hour
        am_mask  = hours <= 11
        pm_mask  = hours >= 13
        all_open  = day_df.iloc[0]["open"]
        all_close = day_df.iloc[-1]["close"]
        daily_high = day_df["high"].max()
        daily_low  = day_df["low"].min()
        daily_vol  = day_df["volume"].sum()

        # First hour return (open to end of first bar)
        fh_ret = (day_df.iloc[0]["close"] - all_open) / all_open if all_open > 0 else 0

        # AM session return
        am_df = day_df[am_mask]
        am_ret = (am_df.iloc[-1]["close"] / am_df.iloc[0]["open"] - 1) if len(am_df) >= 1 and am_df.iloc[0]["open"] > 0 else 0

        # PM session return
        pm_df = day_df[pm_mask]
        pm_ret = (pm_df.iloc[-1]["close"] / pm_df.iloc[0]["open"] - 1) if len(pm_df) >= 1 and pm_df.iloc[0]["open"] > 0 else 0

        # PM vs AM: does afternoon follow morning direction?
        pm_vs_am = pm_ret - am_ret

        # Volume concentration in morning
        am_vol = day_df[am_mask]["volume"].sum()
        vol_am_frac = am_vol / daily_vol if daily_vol > 0 else 0.5

        # Intraday range normalized by close
        intraday_range = (daily_high - daily_low) / all_close if all_close > 0 else 0

        # Open-to-close return
        open_close_pct = (all_close - all_open) / all_open if all_open > 0 else 0

        records.append({
            "date": pd.Timestamp(date),
            "fh_ret": fh_ret,
            "am_ret": am_ret,
            "pm_ret": pm_ret,
            "pm_vs_am": pm_vs_am,
            "vol_am_frac": vol_am_frac,
            "intraday_range_1h": intraday_range,
            "open_close_pct": open_close_pct,
            "n_bars": len(day_df),
        })

    out = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    out.to_parquet(OUT_FILE, index=False)
    print(f"\nSaved {len(out)} trading days to {OUT_FILE}")
    print(f"Date range: {out['date'].min().date()} to {out['date'].max().date()}")
    print(f"\nSample stats:")
    print(out[["fh_ret","am_ret","pm_ret","pm_vs_am","vol_am_frac"]].describe().round(4))


if __name__ == "__main__":
    main()
