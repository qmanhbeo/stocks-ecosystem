"""Adapt the consolidated lab RL matrix into RL-consumable per-ticker signal exports."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from vn_stock_rl.external_features import (
    default_lab_signal_matrix_path,
    default_lab_signal_prediction_dir,
)


RESERVED_COLUMNS = {"time", "ticker", "actual"}


def _resolve_signal_columns(columns: Iterable[str]) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for column in columns:
        name = str(column).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        resolved.append(name)
    return resolved


def _signal_prediction_filename(ticker: str) -> str:
    return f"{str(ticker).upper()}_signal_predictions.parquet"


def export_lab_signal_matrix(
    matrix_path: str | Path,
    output_dir: str | Path,
    signal_columns: Iterable[str] | None = None,
    tickers: Iterable[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    matrix_path = Path(matrix_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()

    if not matrix_path.exists():
        raise FileNotFoundError(f"Lab signal matrix not found: {matrix_path}")

    matrix = pd.read_parquet(matrix_path)
    missing_required = {"time", "ticker"} - set(matrix.columns)
    if missing_required:
        raise ValueError(
            f"Lab signal matrix is missing required columns: {sorted(missing_required)}"
        )

    matrix = matrix.copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce")
    if matrix["time"].isna().any():
        raise ValueError("Lab signal matrix contains non-datetime 'time' values")

    if signal_columns is None:
        signal_columns = [column for column in matrix.columns if column not in RESERVED_COLUMNS]
    resolved_signal_columns = _resolve_signal_columns(signal_columns)
    if not resolved_signal_columns:
        raise ValueError("No lab signal columns were selected for export")
    reserved_requested = [
        column for column in resolved_signal_columns if column in RESERVED_COLUMNS
    ]
    if reserved_requested:
        raise ValueError(
            f"Reserved lab matrix columns cannot be exported as RL features: "
            f"{reserved_requested}"
        )

    missing_signal_columns = [
        column for column in resolved_signal_columns if column not in matrix.columns
    ]
    if missing_signal_columns:
        raise ValueError(
            f"Requested lab signal columns are missing from matrix: {missing_signal_columns}"
        )

    if tickers:
        allowed_tickers = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
        matrix = matrix.loc[matrix["ticker"].astype(str).str.upper().isin(allowed_tickers)].copy()

    if start_date is not None:
        matrix = matrix.loc[matrix["time"] >= pd.Timestamp(start_date)].copy()
    if end_date is not None:
        matrix = matrix.loc[matrix["time"] <= pd.Timestamp(end_date)].copy()

    if matrix.empty:
        raise ValueError("No lab signal rows remain after applying ticker/date filters")

    export_frame = matrix[["time", "ticker", *resolved_signal_columns]].copy()
    export_frame["ticker"] = export_frame["ticker"].astype(str).str.upper()
    export_frame["date"] = export_frame["time"].dt.strftime("%Y-%m-%d")
    if export_frame.duplicated(subset=["ticker", "date"]).any():
        duplicates = export_frame.loc[
            export_frame.duplicated(subset=["ticker", "date"]),
            ["ticker", "date"],
        ]
        sample = duplicates.head(5).to_dict("records")
        raise ValueError(f"Duplicate ticker/date rows found in lab signal matrix export: {sample}")

    output_dir.mkdir(parents=True, exist_ok=True)
    existing_prediction_files = {
        path.name: path
        for path in output_dir.glob("*_signal_predictions.parquet")
        if path.is_file()
    }
    file_count = 0
    rows_written = 0
    tickers_written: list[str] = []
    written_filenames: set[str] = set()
    for ticker, ticker_df in export_frame.groupby("ticker", sort=True):
        file_count += 1
        rows_written += int(len(ticker_df))
        tickers_written.append(str(ticker))
        filename = _signal_prediction_filename(str(ticker))
        written_filenames.add(filename)
        out = (
            ticker_df[["date", *resolved_signal_columns]]
            .sort_values("date")
            .reset_index(drop=True)
        )
        out.to_parquet(output_dir / filename, index=False)

    stale_files_removed: list[str] = []
    for filename, path in sorted(existing_prediction_files.items()):
        if filename in written_filenames:
            continue
        path.unlink()
        stale_files_removed.append(filename)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "matrix_path": str(matrix_path),
        "output_dir": str(output_dir),
        "signal_columns": list(resolved_signal_columns),
        "reserved_columns_excluded": sorted(RESERVED_COLUMNS),
        "tickers_exported": tickers_written,
        "ticker_count": len(tickers_written),
        "rows_written": rows_written,
        "files_written": file_count,
        "date_min": export_frame["date"].min(),
        "date_max": export_frame["date"].max(),
        "stale_files_removed": stale_files_removed,
    }
    with (output_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export data/features/xs_rl_signal_matrix.parquet into RL per-ticker "
            "signal parquet files."
        )
    )
    parser.add_argument(
        "--matrix-path",
        type=str,
        default=str(default_lab_signal_matrix_path()),
        help="Path to the consolidated lab RL signal matrix parquet.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(default_lab_signal_prediction_dir()),
        help="Directory to write RL-consumable per-ticker signal parquet exports.",
    )
    parser.add_argument(
        "--signal-columns",
        type=str,
        nargs="+",
        default=None,
        help=(
            "Optional explicit lab signal columns to export. Defaults to all "
            "non-key, non-target columns."
        ),
    )
    parser.add_argument(
        "--tickers",
        type=str,
        nargs="+",
        default=None,
        help="Optional subset of tickers to export.",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Optional inclusive lower date bound (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Optional inclusive upper date bound (YYYY-MM-DD).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = export_lab_signal_matrix(
        matrix_path=args.matrix_path,
        output_dir=args.output_dir,
        signal_columns=args.signal_columns,
        tickers=args.tickers,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(f"matrix_path: {manifest['matrix_path']}")
    print(f"output_dir: {manifest['output_dir']}")
    print(f"files_written: {manifest['files_written']}")
    print(f"ticker_count: {manifest['ticker_count']}")
    print(f"rows_written: {manifest['rows_written']}")
    print(f"signal_columns: {', '.join(manifest['signal_columns'])}")
    print(f"date_range: {manifest['date_min']} -> {manifest['date_max']}")


if __name__ == "__main__":
    main()
