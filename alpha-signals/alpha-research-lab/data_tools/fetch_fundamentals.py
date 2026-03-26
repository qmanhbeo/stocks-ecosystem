"""
Fetch FPT quarterly fundamental data (EPS, P/E, ROE, margins, etc.) from vnstock
and save to data/features/fpt_fundamentals.parquet.

Timing: each quarter's data is released ~45 days after quarter end.
We assign a release_date = quarter_end + 45 days to avoid lookahead bias.

Quarter ends:
  Q1 (lengthReport=1): March 31
  Q2 (lengthReport=2): June 30
  Q3 (lengthReport=3): September 30
  Q4 (lengthReport=4): December 31

Run: python data_tools/fetch_fundamentals.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
from vnstock import Vnstock
from pathlib import Path

OUTPUT = Path("data/features/fpt_fundamentals.parquet")

QUARTER_END_MONTH = {1: 3, 2: 6, 3: 9, 4: 12}
LAG_DAYS = 45  # conservative release delay


def quarter_end_date(year: int, q: int) -> pd.Timestamp:
    month = QUARTER_END_MONTH[q]
    # last day of that month
    return pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)


def fetch_fpt_ratios() -> pd.DataFrame:
    stock = Vnstock().stock(symbol="FPT", source="VCI")
    fr = stock.finance.ratio(period="quarter", lang="en")

    # Flatten multi-level columns: ('category_vi', 'metric_en') -> 'metric_en'
    # The second level already has English names from lang="en"
    fr.columns = [c[1] if isinstance(c, tuple) else c for c in fr.columns]

    # Rename meta columns if needed
    rename = {}
    for c in fr.columns:
        cl = c.lower()
        if "year" in cl and "report" in cl:
            rename[c] = "yearReport"
        elif "length" in cl and "report" in cl:
            rename[c] = "lengthReport"
        elif "ticker" in cl:
            rename[c] = "ticker"
    fr = fr.rename(columns=rename)

    print(f"  Fetched {len(fr)} quarters")
    print(f"  Columns: {fr.columns.tolist()[:10]} ...")
    return fr


def build_daily_series(fr: pd.DataFrame) -> pd.DataFrame:
    """Assign release dates and forward-fill to daily granularity."""
    rows = []
    for _, row in fr.iterrows():
        year = int(row["yearReport"])
        q = int(row["lengthReport"])
        if q not in QUARTER_END_MONTH:
            continue
        qend = quarter_end_date(year, q)
        release = qend + pd.Timedelta(days=LAG_DAYS)
        rows.append({"release_date": release, "year": year, "quarter": q, **row})

    df = pd.DataFrame(rows)
    df = df.sort_values("release_date").reset_index(drop=True)
    print(f"  {len(df)} quarterly observations from {df['release_date'].min().date()} to {df['release_date'].max().date()}")

    # Generate daily date range from first release to today
    daily_idx = pd.date_range(df["release_date"].min(), pd.Timestamp.today(), freq="D")
    df_daily = df.set_index("release_date").reindex(daily_idx, method="ffill")
    df_daily.index.name = "date"

    # Keep only fundamental value columns (drop meta)
    drop_cols = ["ticker", "yearReport", "lengthReport", "year", "quarter"]
    value_cols = [c for c in df_daily.columns if c not in drop_cols]

    # Compute momentum features using the quarterly df (before daily expansion)
    df_q = df.set_index(["year", "quarter"]).sort_index()

    def _qoq_change(col):
        """Quarter-over-quarter fractional change."""
        if col not in df_q.columns:
            return None
        s = df_q[col]
        return s.pct_change(1).values  # aligned with df_q order

    def _yoy_change(col):
        """Year-over-year fractional change (same quarter)."""
        if col not in df_q.columns:
            return None
        s = df_q[col]
        return s.pct_change(4).values  # 4 quarters back

    eps_col = next((c for c in df_q.columns if "EPS" in c and "VND" in c), None)
    pe_col  = next((c for c in df_q.columns if c == "P/E"), None)
    roe_col = next((c for c in df_q.columns if "ROE" in c), None)
    npm_col = next((c for c in df_q.columns if "Net Profit Margin" in c), None)

    df_q2 = df_q.copy()
    if eps_col:
        df_q2["eps_qoq"] = df_q[eps_col].pct_change(1)
        df_q2["eps_yoy"] = df_q[eps_col].pct_change(4)
    if pe_col:
        df_q2["pe_zscore"] = (
            (df_q[pe_col] - df_q[pe_col].expanding(min_periods=4).mean())
            / df_q[pe_col].expanding(min_periods=4).std()
        )
    if roe_col:
        df_q2["roe_qoq"] = df_q[roe_col].pct_change(1)
    if npm_col:
        df_q2["npm_qoq"] = df_q[npm_col].pct_change(1)

    # Merge momentum cols back into daily df
    df_q_reset = df_q2.reset_index()
    df_with_dates = df[["release_date", "year", "quarter"]].merge(
        df_q_reset[["year", "quarter"] + [c for c in ["eps_qoq", "eps_yoy", "pe_zscore", "roe_qoq", "npm_qoq"] if c in df_q2.columns]],
        on=["year", "quarter"], how="left"
    ).set_index("release_date")

    daily_momentum = df_with_dates.reindex(daily_idx, method="ffill")
    daily_momentum.index.name = "date"

    # Combine: select core value columns + momentum
    core_cols = [c for c in [eps_col, pe_col, roe_col, npm_col] if c is not None]
    momentum_cols = [c for c in ["eps_qoq", "eps_yoy", "pe_zscore", "roe_qoq", "npm_qoq"] if c in daily_momentum.columns]

    result = pd.concat([
        df_daily[core_cols],
        daily_momentum[momentum_cols]
    ], axis=1)
    result = result.dropna(how="all")

    print(f"  Daily series: {len(result)} rows, columns: {result.columns.tolist()}")
    return result


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    print("Fetching FPT quarterly fundamentals from vnstock...")
    fr = fetch_fpt_ratios()
    print("Building daily series with momentum features...")
    daily = build_daily_series(fr)
    daily.to_parquet(OUTPUT)
    print(f"Saved to {OUTPUT}")
    print(daily.tail(10).to_string())
