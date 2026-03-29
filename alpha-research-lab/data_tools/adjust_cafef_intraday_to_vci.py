"""
Adjust raw CafeF intraday bars onto the local VCI-adjusted daily price backbone.

Problem:
    CafeF MatchPrice exposes raw traded session prices.
    Local `gia_lich_su_<TICKER>_1D.parquet` files are treated in this repo as
    VCI-adjusted historical prices.

Fix:
    For each ticker-day with both sources available, compute:
        price_factor = vci_daily_close / cafef_intraday_last_close

    Then multiply CafeF intraday OHLC prices by `price_factor`.
    Volume is left unchanged because the local daily backbone appears price-
    adjusted but not volume-adjusted.

Outputs:
    Adjusted intraday bars:
        data/stock/gia_lich_su_<TICKER>_<ADJUSTED_LABEL>.parquet

    Daily audit factors:
        data/stock/_cafef_adjustment_factors/gia_lich_su_<TICKER>_<RAW_LABEL>_to_<ADJUSTED_LABEL>.parquet

Examples:
    conda run -n stocks python data_tools/adjust_cafef_intraday_to_vci.py --tickers FPT,ACB
    conda run -n stocks python data_tools/adjust_cafef_intraday_to_vci.py --raw-label 1H_CAFEF --adjusted-label 1H_CAFEF_ADJ
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "stock"
FACTOR_DIR = DATA_DIR / "_cafef_adjustment_factors"
FACTOR_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_RAW_LABEL = "1H_CAFEF"
DEFAULT_ADJUSTED_LABEL = "1H_CAFEF_ADJ"
DAILY_INTERVAL = "1D"
EXCLUDE = {"VNINDEX", "VN30"}
BAR_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Adjust CafeF intraday bars onto the VCI daily price backbone")
    parser.add_argument(
        "--tickers",
        type=str,
        help="Comma-separated tickers. Defaults to all tickers with existing raw CafeF files for --raw-label.",
    )
    parser.add_argument(
        "--raw-label",
        type=str,
        default=DEFAULT_RAW_LABEL,
        help=f"Input raw CafeF intraday label (default: {DEFAULT_RAW_LABEL})",
    )
    parser.add_argument(
        "--adjusted-label",
        type=str,
        default=DEFAULT_ADJUSTED_LABEL,
        help=f"Output adjusted intraday label (default: {DEFAULT_ADJUSTED_LABEL})",
    )
    parser.add_argument(
        "--factor-dir",
        type=str,
        default=str(FACTOR_DIR),
        help=f"Directory for per-day factor audit files (default: {FACTOR_DIR})",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing adjusted outputs and factor files")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be adjusted without writing files")
    return parser.parse_args()


def build_raw_path(ticker: str, raw_label: str) -> Path:
    return DATA_DIR / f"gia_lich_su_{ticker}_{raw_label}.parquet"


def build_daily_path(ticker: str) -> Path:
    return DATA_DIR / f"gia_lich_su_{ticker}_{DAILY_INTERVAL}.parquet"


def build_adjusted_path(ticker: str, adjusted_label: str) -> Path:
    return DATA_DIR / f"gia_lich_su_{ticker}_{adjusted_label}.parquet"


def build_factor_path(ticker: str, raw_label: str, adjusted_label: str, factor_dir: Path) -> Path:
    factor_dir.mkdir(parents=True, exist_ok=True)
    return factor_dir / f"gia_lich_su_{ticker}_{raw_label}_to_{adjusted_label}.parquet"


def resolve_tickers(raw_tickers: str | None, raw_label: str) -> list[str]:
    if raw_tickers:
        tickers = [ticker.strip().upper() for ticker in raw_tickers.split(",") if ticker.strip()]
        if not tickers:
            raise ValueError("No tickers were parsed from --tickers")
        return tickers

    tickers = []
    for path in sorted(DATA_DIR.glob(f"gia_lich_su_*_{raw_label}.parquet")):
        ticker = path.stem.replace("gia_lich_su_", "").replace(f"_{raw_label}", "").upper()
        if ticker in EXCLUDE:
            continue
        tickers.append(ticker)
    if not tickers:
        raise RuntimeError(f"No raw CafeF files found for label {raw_label} under {DATA_DIR}")
    return tickers


def load_intraday(ticker: str, raw_label: str) -> pd.DataFrame:
    path = build_raw_path(ticker, raw_label)
    if not path.exists():
        raise RuntimeError(f"Missing raw CafeF intraday file for {ticker}: {path}")
    intraday = pd.read_parquet(path)
    required = set(BAR_COLUMNS)
    missing = required - set(intraday.columns)
    if missing:
        raise RuntimeError(f"Raw CafeF file for {ticker} is missing columns: {sorted(missing)}")
    intraday = intraday[BAR_COLUMNS].copy()
    intraday["time"] = pd.to_datetime(intraday["time"], errors="coerce")
    intraday = intraday.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    intraday["session_date"] = intraday["time"].dt.normalize()
    return intraday


def load_daily(ticker: str) -> pd.DataFrame:
    path = build_daily_path(ticker)
    if not path.exists():
        raise RuntimeError(f"Missing VCI daily file for {ticker}: {path}")
    daily = pd.read_parquet(path, columns=["time", "open", "high", "low", "close", "volume"]).copy()
    daily["time"] = pd.to_datetime(daily["time"], errors="coerce").dt.normalize()
    daily = daily.dropna(subset=["time"]).drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)
    return daily.rename(
        columns={
            "time": "session_date",
            "open": "vci_open_adj",
            "high": "vci_high_adj",
            "low": "vci_low_adj",
            "close": "vci_close_adj",
            "volume": "vci_volume",
        }
    )


def build_daily_factor_frame(intraday: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    raw_daily = (
        intraday.sort_values("time")
        .groupby("session_date", sort=True)
        .agg(
            cafef_open_raw=("open", "first"),
            cafef_high_raw=("high", "max"),
            cafef_low_raw=("low", "min"),
            cafef_close_raw=("close", "last"),
            cafef_volume_raw=("volume", "sum"),
            intraday_bar_count=("time", "size"),
        )
        .reset_index()
    )

    merged = raw_daily.merge(daily, on="session_date", how="inner")
    merged = merged.dropna(subset=["cafef_close_raw", "vci_close_adj"]).copy()
    merged = merged[merged["cafef_close_raw"] > 0].copy()
    if merged.empty:
        raise RuntimeError("No overlapping CafeF/VCI dates with valid closing prices")

    merged["price_factor"] = merged["vci_close_adj"] / merged["cafef_close_raw"]
    merged["adj_open_from_cafef"] = merged["cafef_open_raw"] * merged["price_factor"]
    merged["adj_high_from_cafef"] = merged["cafef_high_raw"] * merged["price_factor"]
    merged["adj_low_from_cafef"] = merged["cafef_low_raw"] * merged["price_factor"]
    merged["adj_close_from_cafef"] = merged["cafef_close_raw"] * merged["price_factor"]

    for left, right, out_col in [
        ("adj_open_from_cafef", "vci_open_adj", "open_gap_pct"),
        ("adj_high_from_cafef", "vci_high_adj", "high_gap_pct"),
        ("adj_low_from_cafef", "vci_low_adj", "low_gap_pct"),
        ("adj_close_from_cafef", "vci_close_adj", "close_gap_pct"),
    ]:
        merged[out_col] = np.where(
            merged[right].replace(0, np.nan).notna(),
            (merged[left] / merged[right]) - 1.0,
            np.nan,
        )

    merged["volume_ratio_vs_vci"] = np.where(
        merged["vci_volume"].replace(0, np.nan).notna(),
        merged["cafef_volume_raw"] / merged["vci_volume"],
        np.nan,
    )

    return merged.sort_values("session_date").reset_index(drop=True)


def apply_adjustment(intraday: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    adjusted = intraday.merge(factors[["session_date", "price_factor"]], on="session_date", how="inner")
    if adjusted.empty:
        raise RuntimeError("No overlapping intraday rows remained after joining daily factors")

    for column in ["open", "high", "low", "close"]:
        adjusted[column] = adjusted[column] * adjusted["price_factor"]

    adjusted["volume"] = pd.to_numeric(adjusted["volume"], errors="coerce").fillna(0).round().astype("int64")
    adjusted = adjusted.sort_values("time").drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)
    return adjusted[BAR_COLUMNS]


def finite_median(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    return float(np.median(values))


def finite_max_abs(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    return float(np.max(np.abs(values)))


def summarize_adjustment(ticker: str, factors: pd.DataFrame, adjusted: pd.DataFrame, intraday: pd.DataFrame) -> str:
    raw_days = intraday["session_date"].nunique()
    adjusted_days = factors["session_date"].nunique()
    dropped_days = raw_days - adjusted_days
    max_close_gap_bp = finite_max_abs(factors["close_gap_pct"]) * 1e4
    median_volume_ratio = finite_median(factors["volume_ratio_vs_vci"])
    median_factor = finite_median(factors["price_factor"])
    return (
        f"{ticker}: adjusted {len(adjusted)} bars across {adjusted_days}/{raw_days} days "
        f"(dropped {dropped_days} non-overlap days) | median factor {median_factor:.6f} "
        f"| max close gap {max_close_gap_bp:.4f} bp | median volume ratio {median_volume_ratio:.4f}"
    )


def adjust_one_ticker(
    ticker: str,
    *,
    raw_label: str,
    adjusted_label: str,
    factor_dir: Path,
    overwrite: bool,
) -> tuple[bool, str]:
    adjusted_path = build_adjusted_path(ticker, adjusted_label)
    factor_path = build_factor_path(ticker, raw_label, adjusted_label, factor_dir)

    if adjusted_path.exists() and factor_path.exists() and not overwrite:
        return True, f"{ticker}: adjusted output exists, skipping"

    intraday = load_intraday(ticker, raw_label)
    daily = load_daily(ticker)
    factors = build_daily_factor_frame(intraday, daily)
    adjusted = apply_adjustment(intraday, factors)

    adjusted.to_parquet(adjusted_path, index=False)
    factors.to_parquet(factor_path, index=False)
    return True, summarize_adjustment(ticker, factors, adjusted, intraday)


def main() -> None:
    args = parse_args()
    raw_label = args.raw_label.upper()
    adjusted_label = args.adjusted_label.upper()
    factor_dir = Path(args.factor_dir)
    tickers = resolve_tickers(args.tickers, raw_label)

    print("=" * 60)
    print("CafeF Intraday Adjustment")
    print("=" * 60)
    print(f"Tickers        : {len(tickers)}")
    print(f"Raw label      : {raw_label}")
    print(f"Adjusted label : {adjusted_label}")
    print(f"Factor dir     : {factor_dir}")
    print(f"Output dir     : {DATA_DIR}")
    print("=" * 60)

    if args.dry_run:
        for ticker in tickers[:10]:
            raw_path = build_raw_path(ticker, raw_label)
            daily_path = build_daily_path(ticker)
            print(f"[DRY RUN] {ticker}: raw={raw_path.exists()} daily={daily_path.exists()}")
        return

    success_count = 0
    failed: list[str] = []
    for index, ticker in enumerate(tickers, start=1):
        print(f"[{index}/{len(tickers)}] {ticker}", flush=True)
        try:
            ok, message = adjust_one_ticker(
                ticker,
                raw_label=raw_label,
                adjusted_label=adjusted_label,
                factor_dir=factor_dir,
                overwrite=args.overwrite,
            )
        except Exception as exc:
            ok = False
            message = f"{ticker}: ERROR -- {exc}"

        print(f"  {message}", flush=True)
        if ok:
            success_count += 1
        else:
            failed.append(ticker)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Success: {success_count}/{len(tickers)}")
    if failed:
        print(f"Failed : {', '.join(failed)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
