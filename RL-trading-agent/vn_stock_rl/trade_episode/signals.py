from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

S1_ARTIFACT = Path("features/xs_barrier_vol_1d_hose_full.parquet")
C16_ARTIFACT = Path("features/xs_order_pressure_daily.parquet")
ALPHA_FEATURE_NAMES = [
    "alpha_s1_xs_proba",
    "alpha_s1_available",
    "alpha_c16_order_volume_ratio_rank",
    "alpha_c16_available",
]


def load_alpha_signals(
    ticker: str,
    dates,
    *,
    data_root: str | Path,
) -> pd.DataFrame:
    """Load only causal S1/C16 observations and align them to requested dates.

    S1's target label column is deliberately never requested from Parquet. Missing
    values remain NaN and availability indicators preserve their status.
    """

    requested = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    if requested.empty:
        raise ValueError("dates must contain at least one requested date")
    if requested.has_duplicates:
        raise ValueError("requested dates must be unique")
    root = Path(data_root).expanduser().resolve()
    symbol = str(ticker).strip().upper()
    if not symbol or any(character in symbol for character in "/\\"):
        raise ValueError("ticker must be a non-empty ticker symbol")
    date_filter = [
        ("ticker", "=", symbol),
        ("time", ">=", requested.min()),
        ("time", "<=", requested.max()),
    ]

    s1_path = root / S1_ARTIFACT
    c16_path = root / C16_ARTIFACT
    if not s1_path.is_file():
        raise FileNotFoundError(f"Alpha S1 artifact not found: {s1_path}")
    if not c16_path.is_file():
        raise FileNotFoundError(f"Alpha C16 artifact not found: {c16_path}")

    with s1_path.open("rb") as stream:
        s1 = pd.read_parquet(
            stream,
            columns=["time", "ticker", "xs_proba"],
            filters=date_filter,
        )
    with c16_path.open("rb") as stream:
        c16 = pd.read_parquet(
            stream,
            columns=["time", "ticker", "order_volume_ratio_rank", "order_pressure_available"],
            filters=date_filter,
        )

    for name, frame in (("S1", s1), ("C16", c16)):
        frame["time"] = pd.to_datetime(frame["time"], errors="raise").dt.normalize()
        frame["ticker"] = frame["ticker"].astype(str).str.upper()
        frame = frame.loc[
            (frame["ticker"] == symbol)
            & frame["time"].between(requested.min(), requested.max(), inclusive="both")
        ]
        if frame["time"].duplicated().any():
            raise ValueError(f"Alpha {name} artifact has duplicate {symbol} dates")
        if name == "S1":
            s1 = frame.copy()
        else:
            c16 = frame.copy()

    s1_values = pd.to_numeric(s1.set_index("time")["xs_proba"], errors="coerce")
    if ((s1_values.dropna() < 0.0) | (s1_values.dropna() > 1.0)).any():
        raise ValueError("S1 xs_proba values must be probabilities in [0, 1]")
    s1_aligned = s1_values.reindex(requested)

    c16_indexed = c16.set_index("time")
    c16_values = pd.to_numeric(c16_indexed["order_volume_ratio_rank"], errors="coerce")
    c16_published = c16_indexed["order_pressure_available"].fillna(False).astype(bool)
    c16_available = c16_published & c16_values.notna()
    if ((c16_values[c16_available] < 0.0) | (c16_values[c16_available] > 1.0)).any():
        raise ValueError("C16 order-volume ranks must be in [0, 1]")
    c16_availability = c16_available.reindex(requested)
    c16_availability_aligned = pd.Series(
        np.asarray(
            [False if pd.isna(value) else bool(value) for value in c16_availability],
            dtype=bool,
        ),
        index=requested,
    )
    c16_aligned = c16_values.reindex(requested).where(c16_availability_aligned)

    result = pd.DataFrame(index=requested)
    result.index.name = "time"
    result["alpha_s1_xs_proba"] = s1_aligned.to_numpy(dtype=np.float64)
    result["alpha_s1_available"] = s1_aligned.notna().to_numpy(dtype=np.float32)
    result["alpha_c16_order_volume_ratio_rank"] = c16_aligned.to_numpy(dtype=np.float64)
    result["alpha_c16_available"] = c16_aligned.notna().to_numpy(dtype=np.float32)
    if not np.isfinite(result["alpha_s1_available"].to_numpy()).all():
        raise ValueError("S1 availability feature contains non-finite values")
    return result
