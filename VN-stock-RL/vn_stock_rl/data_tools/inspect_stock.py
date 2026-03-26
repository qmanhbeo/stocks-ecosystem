"""
Inspect parquet stock data files.

Usage:
    python -m vn_stock_rl.data_tools.inspect_stock --ticker ACB --interval 1D
    python -m vn_stock_rl.data_tools.inspect_stock --ticker VNM
    python -m vn_stock_rl.data_tools.inspect_stock  # defaults to ACB 1D
"""

import pandas as pd
import argparse
from pathlib import Path

from vn_stock_rl.external_features import default_stock_data_dir


DEFAULT_DATA_DIR = default_stock_data_dir()


def inspect_file(file_path: str):
    """Inspect a single parquet file and print detailed information."""
    try:
        df = pd.read_parquet(file_path)
    except FileNotFoundError:
        print(f"\n❌ File not found: {file_path}")
        print("   Make sure the file exists in shared research data.")
        print("   Producer-side fetch/build now lives in alpha-signals/alpha-research-lab.")
        return False
    except Exception as e:
        print(f"\n❌ Error reading file: {e}")
        return False

    print(f"\n{'='*60}")
    print(f"FILE: {file_path}")
    print(f"{'='*60}\n")

    # Basic info
    print(f"Shape: {df.shape} (rows, columns)")
    
    # Date range - handle both index and column
    if isinstance(df.index, pd.DatetimeIndex):
        start_date = df.index[0]
        end_date = df.index[-1]
    elif 'time' in df.columns:
        start_date = df['time'].iloc[0]
        end_date = df['time'].iloc[-1]
    else:
        start_date = df.iloc[0, 0]
        end_date = df.iloc[-1, 0]
    
    print(f"Date range: {start_date} to {end_date}")
    print(f"Total days: {len(df)}")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nData types:\n{df.dtypes}")

    # First few rows
    print(f"\n{'='*60}")
    print("FIRST 5 ROWS:")
    print(f"{'='*60}")
    print(df.head())

    # Last few rows
    print(f"\n{'='*60}")
    print("LAST 5 ROWS:")
    print(f"{'='*60}")
    print(df.tail())

    # Summary stats
    print(f"\n{'='*60}")
    print("SUMMARY STATISTICS:")
    print(f"{'='*60}")
    print(df.describe())

    # Check for missing values
    print(f"\n{'='*60}")
    print("MISSING VALUES:")
    print(f"{'='*60}")
    missing = df.isnull().sum()
    if missing.sum() == 0:
        print("✓ No missing values found!")
    else:
        print(missing)
        print(f"\nTotal missing values: {missing.sum()}")
    
    # Check for duplicates
    duplicates = df.duplicated().sum()
    print(f"\n{'='*60}")
    print("DUPLICATES:")
    print(f"{'='*60}")
    if duplicates == 0:
        print("✓ No duplicate rows found!")
    else:
        print(f"⚠️  Found {duplicates} duplicate rows")
    
    # Data quality checks
    print(f"\n{'='*60}")
    print("DATA QUALITY CHECKS:")
    print(f"{'='*60}")
    
    # Check for zeros in OHLCV
    if 'close' in df.columns:
        zero_close = (df['close'] == 0).sum()
        if zero_close > 0:
            print(f"⚠️  {zero_close} rows with close price = 0")
        else:
            print("✓ No zero close prices")
    
    # Check for negative values
    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
    for col in numeric_cols:
        if col != 'time':
            negative = (df[col] < 0).sum()
            if negative > 0:
                print(f"⚠️  {negative} negative values in {col}")
    
    # Check for extreme outliers (beyond 3 std)
    if 'close' in df.columns:
        mean = df['close'].mean()
        std = df['close'].std()
        outliers = ((df['close'] < mean - 3*std) | (df['close'] > mean + 3*std)).sum()
        if outliers > 0:
            print(f"ℹ️  {outliers} potential outliers in close price (>3 std)")
        else:
            print("✓ No extreme outliers in close price")
    
    print(f"\n{'='*60}\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Inspect stock data parquet files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m vn_stock_rl.data_tools.inspect_stock                          # Inspect ACB 1D (default)
  python -m vn_stock_rl.data_tools.inspect_stock --ticker VNM             # Inspect VNM 1D
  python -m vn_stock_rl.data_tools.inspect_stock --ticker HPG --interval 1D
  python -m vn_stock_rl.data_tools.inspect_stock --file data/stock/custom.parquet
        """
    )
    
    parser.add_argument(
        "--ticker",
        type=str,
        default="ACB",
        help="Stock ticker (default: ACB)"
    )
    
    parser.add_argument(
        "--interval",
        type=str,
        default="1D",
        help="Time interval (default: 1D)"
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(DEFAULT_DATA_DIR),
        help=f"Data directory (default: {DEFAULT_DATA_DIR})"
    )
    
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Direct file path (overrides --ticker and --interval)"
    )
    
    args = parser.parse_args()
    
    # Determine file path
    if args.file:
        file_path = args.file
    else:
        ticker = args.ticker.upper()
        file_path = f"{args.data_dir}gia_lich_su_{ticker}_{args.interval}.parquet"
    
    print("\n" + "="*60)
    print("Stock Data Inspector")
    print("="*60)
    
    # Inspect the file
    success = inspect_file(file_path)
    
    if success:
        print("✓ Inspection complete!")
    else:
        print("❌ Inspection failed")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
