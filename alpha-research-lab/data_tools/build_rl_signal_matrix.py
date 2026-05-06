"""
Build combined RL signal state matrix from all confirmed/candidate signals.

Assembles S1 + all promoted candidate signals (C4-C14) into a single feature
parquet for use by the RL trading agent. Handles different time columns
(time vs trading_day) and signal sparsity (C5 insider = 3.4% coverage).

Output: data/features/xs_rl_signal_matrix.parquet
  Columns:
    time, ticker              — merge keys
    s1_proba                  — S1/H93: cross-sectional momentum probability
    c4_oc_asym_5d             — C4: overnight/intraday contrast (oc_asym_5d)
    c5_ins_relative_size_5d    — C5: insider conviction (sparse, 3.4%)
    c6_contrarian_intra_5d    — C6: intra-sector mean reversion
    c7_ceiling_count_5d       — C7: price limit momentum
    c8_vol_zscore_5d          — C8: abnormal volume activity
    c9_reversal_1d            — C9: 1-day return reversal (1 - xs_ret_1d_lag_rank)
    c10_illiq_level_rank      — C10: Amihud illiquidity level
    c11_ret_60d_lag_rank      — C11: 3-month continuation / medium-term trend
    c12_gap_absorb_3          — C12: gap acceptance with intraday confirmation
    c13_compress_blowoff_2    — C13: post-compression expansion exhaustion
    c14_clv_volconf_resid_rank — C14: close-strength residual after removing C8
    c5_signal_present         — indicator: 1 if C5 fired on this (time, ticker)

Signal properties (all 2015–2025):
  S1:  IC +0.149, 11/11 yrs, corr N/A (primary signal)
  C4:  IC +0.023, 11/11 yrs, corr +0.147, coverage 100%
  C5:  IC +0.037, 10/11 yrs, corr -0.008, coverage 3.4%
  C6:  IC +0.030, 11/11 yrs, corr +0.142, coverage 100%
  C7:  IC +0.012,  8/11 yrs, corr +0.064, coverage 100%
  C8:  IC +0.011, 10/11 yrs, corr +0.068, coverage 100%
  C9:  IC +0.028, 11/11 yrs, corr +0.161, coverage 100%
  C10: IC +0.021, 10/11 yrs, corr +0.008, coverage 100%
  C11: IC +0.010, 9/11 yrs, corr +0.008, coverage 100%
  C12: IC +0.028, 11/11 yrs, corr +0.131, coverage 100%
  C13: IC +0.035, 10/11 yrs, corr +0.191, coverage 100%
  C14: IC +0.013, 11/11 yrs, corr +0.102, coverage 100%

Usage:
    conda run -n stocks python data_tools/build_rl_signal_matrix.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Callable, Mapping
from path_utils import data_path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.artifact_contract import (  # noqa: E402
    atomic_write_parquet,
    build_input_fingerprint,
    validate_required_columns,
    validate_unique_keys,
    write_manifest,
)

FEAT_DIR = data_path("features")
STOCK_DIR = data_path("stock")
OUT_PATH = FEAT_DIR / "xs_rl_signal_matrix.parquet"
RL_PARTS_DIR = FEAT_DIR / "_rl_signal_matrix_parts"
C10_CACHE_PATH = RL_PARTS_DIR / "c10_illiq.parquet"
C10_MANIFEST_PATH = RL_PARTS_DIR / "c10_illiq_manifest.json"
C11_CACHE_PATH = RL_PARTS_DIR / "c11_3m_continuation.parquet"
C11_MANIFEST_PATH = RL_PARTS_DIR / "c11_3m_continuation_manifest.json"
C12_CACHE_PATH = RL_PARTS_DIR / "c12_gap_absorption.parquet"
C12_MANIFEST_PATH = RL_PARTS_DIR / "c12_gap_absorption_manifest.json"
C13_CACHE_PATH = RL_PARTS_DIR / "c13_compress_blowoff.parquet"
C13_MANIFEST_PATH = RL_PARTS_DIR / "c13_compress_blowoff_manifest.json"
C14_CACHE_PATH = RL_PARTS_DIR / "c14_clv_resid.parquet"
C14_MANIFEST_PATH = RL_PARTS_DIR / "c14_clv_resid_manifest.json"

S1_PATH       = FEAT_DIR / "xs_barrier_vol_1d_hose_full.parquet"
S1_LIVE_PATH  = FEAT_DIR / "xs_barrier_vol_1d_hose_live_current.parquet"
C4_PATH       = FEAT_DIR / "xs_open_close_asymmetry.parquet"
C5_PATH       = FEAT_DIR / "xs_insider_quality_features.parquet"
C6_PATH       = FEAT_DIR / "xs_sector_rotation_daily.parquet"
C7_PATH       = FEAT_DIR / "xs_price_limit_daily.parquet"
C8_PATH       = FEAT_DIR / "xs_volume_zscore_daily.parquet"
C9_PATH       = FEAT_DIR / "xs_shortterm_reversal.parquet"

ILLIQ_WINDOW = 20
ILLIQ_MIN_DAYS = 10
VALUE_SCALE = 1e9
LOOKBACK_DAYS = 60
EXCLUDE = {"VNINDEX", "VN30"}


@dataclass(frozen=True)
class ComponentCacheSpec:
    label: str
    cache_path: Path
    manifest_path: Path
    value_col: str
    producer: str

    @property
    def required_columns(self) -> tuple[str, str, str]:
        return ("time", "ticker", self.value_col)


COMPONENT_SPECS: dict[str, ComponentCacheSpec] = {
    "C10": ComponentCacheSpec("C10", C10_CACHE_PATH, C10_MANIFEST_PATH, "c10_illiq_level_rank", "build_illiq_level_features"),
    "C11": ComponentCacheSpec("C11", C11_CACHE_PATH, C11_MANIFEST_PATH, "c11_ret_60d_lag_rank", "build_3m_continuation_features"),
    "C12": ComponentCacheSpec("C12", C12_CACHE_PATH, C12_MANIFEST_PATH, "c12_gap_absorb_3", "build_gap_absorption_features"),
    "C13": ComponentCacheSpec("C13", C13_CACHE_PATH, C13_MANIFEST_PATH, "c13_compress_blowoff_2", "build_compress_blowoff_features"),
    "C14": ComponentCacheSpec("C14", C14_CACHE_PATH, C14_MANIFEST_PATH, "c14_clv_volconf_resid_rank", "build_clv_resid_features"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the consolidated RL signal matrix.")
    parser.add_argument("--start-date", type=str, default=None, help="Optional inclusive signal-date lower bound.")
    parser.add_argument("--end-date", type=str, default=None, help="Optional inclusive signal-date upper bound.")
    parser.add_argument(
        "--component-cache-only",
        action="store_true",
        help="Build/reuse C10-C14 component caches without publishing the final RL matrix.",
    )
    parser.add_argument(
        "--verify-component-parity",
        action="store_true",
        help="Recompute old inline C10-C14 outputs and compare them to cached outputs.",
    )
    return parser.parse_args()


def _parse_date(value: str | pd.Timestamp | None) -> pd.Timestamp | None:
    if value is None or str(value).strip() == "":
        return None
    return pd.Timestamp(value).normalize()


def _date_token(value: pd.Timestamp | None) -> str | None:
    return None if value is None else pd.Timestamp(value).date().isoformat()


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _apply_date_window(
    frame: pd.DataFrame,
    *,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    out["time"] = pd.to_datetime(out["time"], errors="coerce").dt.normalize()
    mask = out["time"].notna()
    if start_date is not None:
        mask &= out["time"] >= pd.Timestamp(start_date)
    if end_date is not None:
        mask &= out["time"] <= pd.Timestamp(end_date)
    return out.loc[mask].copy()


def _filter_source_end(frame: pd.DataFrame, end_date: pd.Timestamp | None) -> pd.DataFrame:
    if end_date is None or frame.empty:
        return frame
    out = frame.copy()
    out["time"] = pd.to_datetime(out["time"], errors="coerce").dt.normalize()
    return out.loc[out["time"] <= pd.Timestamp(end_date)].copy()


def _frame_window(frame: pd.DataFrame) -> dict[str, str | None]:
    if frame.empty:
        return {"min_date": None, "max_date": None}
    times = pd.to_datetime(frame["time"], errors="coerce").dropna()
    if times.empty:
        return {"min_date": None, "max_date": None}
    return {
        "min_date": pd.Timestamp(times.min()).date().isoformat(),
        "max_date": pd.Timestamp(times.max()).date().isoformat(),
    }


def _assert_window_within_request(
    actual_window: Mapping[str, str | None],
    requested_window: Mapping[str, str | None],
    label: str,
) -> None:
    requested_start = requested_window.get("start_date")
    requested_end = requested_window.get("end_date")
    actual_min = actual_window.get("min_date")
    actual_max = actual_window.get("max_date")
    if requested_start and actual_min and actual_min < requested_start:
        raise ValueError(
            f"{label} cache starts at {actual_min}, before requested start_date={requested_start}"
        )
    if requested_end and actual_max and actual_max > requested_end:
        raise ValueError(
            f"{label} cache ends at {actual_max}, after requested end_date={requested_end}"
        )


def _requested_window(
    start_date: pd.Timestamp | None,
    end_date: pd.Timestamp | None,
) -> dict[str, str | None]:
    return {"start_date": _date_token(start_date), "end_date": _date_token(end_date)}


def _stock_1d_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = path.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        files.append(path)
    return files


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _component_source_metadata(component: str, *, extra_paths: list[Path] | None = None) -> dict[str, object]:
    paths = _stock_1d_files()
    if extra_paths:
        paths.extend(extra_paths)
    return {
        "component": component,
        "schema_version": 2,
        "params": {
            "illiq_window": ILLIQ_WINDOW,
            "illiq_min_days": ILLIQ_MIN_DAYS,
            "value_scale": VALUE_SCALE,
            "lookback_days": LOOKBACK_DAYS,
        },
        "paths": paths,
    }


def _component_input_fingerprint(
    *,
    source_fingerprint: dict[str, object],
    start_date: pd.Timestamp | None,
    end_date: pd.Timestamp | None,
) -> dict[str, object]:
    return build_input_fingerprint(
        {
            "source_fingerprint": source_fingerprint,
            "requested_window": _requested_window(start_date, end_date),
        }
    )


def _component_manifest_matches(
    *,
    manifest: Mapping[str, object],
    source_fingerprint: dict[str, object],
    input_fingerprint: dict[str, object],
    requested_window: dict[str, str | None],
) -> bool:
    if int(manifest.get("manifest_schema_version", 0) or 0) < 2:
        return False
    stored_source = manifest.get("source_fingerprint")
    stored_input = manifest.get("input_fingerprint")
    return (
        isinstance(stored_source, dict)
        and isinstance(stored_input, dict)
        and str(stored_source.get("digest")) == str(source_fingerprint.get("digest"))
        and str(stored_input.get("digest")) == str(input_fingerprint.get("digest"))
        and manifest.get("requested_window") == requested_window
    )


def _validate_component_frame(frame: pd.DataFrame, spec: ComponentCacheSpec, artifact_name: str) -> pd.DataFrame:
    validate_required_columns(frame, spec.required_columns, artifact_name)
    out = frame[list(spec.required_columns)].copy()
    out["time"] = pd.to_datetime(out["time"], errors="coerce").dt.normalize()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out[spec.value_col] = pd.to_numeric(out[spec.value_col], errors="coerce")
    out = out.dropna(subset=["time", "ticker", spec.value_col])
    validate_unique_keys(out, ["time", "ticker"], artifact_name)
    return out.sort_values(["time", "ticker"]).reset_index(drop=True)


def _read_component_cache(spec: ComponentCacheSpec) -> pd.DataFrame:
    try:
        frame = pd.read_parquet(spec.cache_path)
    except Exception as exc:
        raise ValueError(f"{spec.label} cached component at {spec.cache_path} is not readable") from exc
    return _validate_component_frame(frame, spec, f"{spec.label} cached RL matrix component")


def load_or_build_component_cache(
    spec: ComponentCacheSpec,
    *,
    build_fn: Callable[[], pd.DataFrame],
    source_metadata: Mapping[str, object],
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    requested_window = _requested_window(start_date, end_date)
    source_fingerprint = build_input_fingerprint(source_metadata)
    input_fingerprint = _component_input_fingerprint(
        source_fingerprint=source_fingerprint,
        start_date=start_date,
        end_date=end_date,
    )
    manifest = _read_json(spec.manifest_path)
    if (
        spec.cache_path.exists()
        and manifest
        and _component_manifest_matches(
            manifest=manifest,
            source_fingerprint=source_fingerprint,
            input_fingerprint=input_fingerprint,
            requested_window=requested_window,
        )
    ):
        cached = _read_component_cache(spec)
        actual_window = _frame_window(cached)
        if actual_window != manifest.get("actual_window"):
            raise ValueError(f"{spec.label} cache window does not match manifest at {spec.manifest_path}")
        _assert_window_within_request(actual_window, requested_window, spec.label)
        print(f"  {spec.label}: reused component cache -> {spec.cache_path}")
        return cached

    built = _validate_component_frame(
        _apply_date_window(build_fn(), start_date=start_date, end_date=end_date),
        spec,
        f"{spec.label} built RL matrix component",
    )
    actual_window = _frame_window(built)
    _assert_window_within_request(actual_window, requested_window, spec.label)
    atomic_write_parquet(built, spec.cache_path)
    write_manifest(
        spec.manifest_path,
        {
            "manifest_schema_version": 2,
            "component": spec.label,
            "artifact": str(spec.cache_path),
            "producer": spec.producer,
            "build_timestamp": _utc_timestamp(),
            "requested_window": requested_window,
            "actual_window": actual_window,
            "source_fingerprint": source_fingerprint,
            "input_fingerprint": input_fingerprint,
            "upstream_inputs": source_metadata,
            "row_count": int(len(built)),
            "column_count": int(len(built.columns)),
            "columns": list(built.columns),
        },
    )
    print(f"  {spec.label}: built component cache -> {spec.cache_path}")
    return built


def load_or_build_c10_component(
    *,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    return load_or_build_component_cache(
        COMPONENT_SPECS["C10"],
        build_fn=lambda: build_illiq_level_features(end_date=end_date),
        source_metadata=_component_source_metadata("c10_illiq_level_rank"),
        start_date=start_date,
        end_date=end_date,
    )


def load_or_build_c11_component(
    *,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    return load_or_build_component_cache(
        COMPONENT_SPECS["C11"],
        build_fn=lambda: build_3m_continuation_features(end_date=end_date),
        source_metadata=_component_source_metadata(
            "c11_ret_60d_lag_rank",
            extra_paths=[STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"],
        ),
        start_date=start_date,
        end_date=end_date,
    )


def load_or_build_c12_component(
    *,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    return load_or_build_component_cache(
        COMPONENT_SPECS["C12"],
        build_fn=lambda: build_gap_absorption_features(end_date=end_date),
        source_metadata=_component_source_metadata("c12_gap_absorb_3"),
        start_date=start_date,
        end_date=end_date,
    )


def load_or_build_c13_component(
    *,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    return load_or_build_component_cache(
        COMPONENT_SPECS["C13"],
        build_fn=lambda: build_compress_blowoff_features(end_date=end_date),
        source_metadata=_component_source_metadata("c13_compress_blowoff_2"),
        start_date=start_date,
        end_date=end_date,
    )


def load_or_build_c14_component(
    c8: pd.DataFrame,
    *,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    return load_or_build_component_cache(
        COMPONENT_SPECS["C14"],
        build_fn=lambda: build_clv_resid_features(c8, end_date=end_date),
        source_metadata=_component_source_metadata("c14_clv_volconf_resid_rank", extra_paths=[C8_PATH]),
        start_date=start_date,
        end_date=end_date,
    )


def load_s1_spine() -> pd.DataFrame:
    s1 = pd.read_parquet(S1_PATH)[["time", "ticker", "xs_proba", "actual"]]
    s1["time"] = pd.to_datetime(s1["time"])
    if S1_LIVE_PATH.exists():
        live = pd.read_parquet(S1_LIVE_PATH)[["time", "ticker", "xs_proba", "actual"]]
        live["time"] = pd.to_datetime(live["time"])
        s1 = (
            pd.concat([s1, live], ignore_index=True)
            .sort_values(["time", "ticker"])
            .drop_duplicates(["time", "ticker"], keep="last")
            .reset_index(drop=True)
        )
    return s1


def build_illiq_level_features(*, end_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Compute C10 directly from OHLCV via a vectorized pivot/rank workflow."""
    parts = []
    for f in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "close", "volume"])
        except Exception:
            continue
        df = _filter_source_end(df, end_date)
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < 50:
            continue
        df["ticker"] = ticker
        df["daily_value"] = df["close"] * df["volume"] / VALUE_SCALE
        df["ret1"] = df["close"].pct_change(1)
        df["illiq_raw"] = df["ret1"].abs() / df["daily_value"].replace(0, np.nan)
        parts.append(df[["time", "ticker", "illiq_raw"]])

    long = pd.concat(parts, ignore_index=True)

    wide = long.pivot_table(index="time", columns="ticker", values="illiq_raw")
    illiq_20d = wide.rolling(ILLIQ_WINDOW, min_periods=ILLIQ_MIN_DAYS).mean()
    xs_level = illiq_20d.rank(axis=1, method="average", ascending=True, pct=True)

    return (
        xs_level.reset_index()
        .melt(id_vars="time", var_name="ticker", value_name="c10_illiq_level_rank")
        .dropna(subset=["c10_illiq_level_rank"])
    )


def build_3m_continuation_features(*, end_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Compute C11 directly from OHLCV via a vectorized pivot/rank workflow."""
    vni = pd.read_parquet(STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet", columns=["time", "close"])
    vni = _filter_source_end(vni, end_date)
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time")
    vni["vni_ret60"] = vni["close"].pct_change(LOOKBACK_DAYS)
    vni = vni[["time", "vni_ret60"]]

    parts = []
    for f in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "close"])
        except Exception:
            continue
        df = _filter_source_end(df, end_date)
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < LOOKBACK_DAYS + 10:
            continue
        df["ticker"] = ticker
        df["ret60"] = df["close"].pct_change(LOOKBACK_DAYS)
        parts.append(df[["time", "ticker", "ret60"]])

    long = pd.concat(parts, ignore_index=True)
    long = long.merge(vni, on="time", how="left")
    long["excess60"] = long["ret60"] - long["vni_ret60"]

    wide = long.pivot_table(index="time", columns="ticker", values="excess60")
    xs_rank = wide.rank(axis=1, method="average", ascending=True, pct=True).shift(1)
    return (
        xs_rank.reset_index()
        .melt(id_vars="time", var_name="ticker", value_name="c11_ret_60d_lag_rank")
        .dropna(subset=["c11_ret_60d_lag_rank"])
    )


def build_gap_absorption_features(*, end_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Compute C12 directly from OHLCV using confirmed-gap acceptance."""
    parts = []
    for f in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "open", "high", "low", "close"])
        except Exception:
            continue
        df = _filter_source_end(df, end_date)
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < 50:
            continue
        df["ticker"] = ticker
        parts.append(df[["time", "ticker", "open", "high", "low", "close"]])

    long = pd.concat(parts, ignore_index=True)
    wide_open = long.pivot_table(index="time", columns="ticker", values="open").sort_index()
    wide_high = long.pivot_table(index="time", columns="ticker", values="high").sort_index()
    wide_low = long.pivot_table(index="time", columns="ticker", values="low").sort_index()
    wide_close = long.pivot_table(index="time", columns="ticker", values="close").sort_index()

    gap = wide_open.div(wide_close.shift(1)) - 1.0
    intraday = wide_close.div(wide_open.replace(0, np.nan)) - 1.0
    intraday_positive = (intraday > 0).astype(float)
    denom = wide_high - wide_low
    clv = (wide_close - wide_low).div(denom.replace(0, np.nan)).mask(denom == 0, 0.5)

    xs_gap_absorb_3 = (gap * intraday_positive * clv).rank(
        axis=1, method="average", ascending=True, pct=True
    )
    return (
        xs_gap_absorb_3.reset_index()
        .melt(id_vars="time", var_name="ticker", value_name="c12_gap_absorb_3")
        .dropna(subset=["c12_gap_absorb_3"])
    )


def build_compress_blowoff_features(*, end_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Compute C13 directly from OHLCV using the validated H133 formulation."""
    parts = []
    for f in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "high", "low", "close", "volume"])
        except Exception:
            continue
        df = _filter_source_end(df, end_date)
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < 80:
            continue
        df["ticker"] = ticker
        parts.append(df[["time", "ticker", "high", "low", "close", "volume"]])

    long = pd.concat(parts, ignore_index=True)
    wide_high = long.pivot_table(index="time", columns="ticker", values="high").sort_index()
    wide_low = long.pivot_table(index="time", columns="ticker", values="low").sort_index()
    wide_close = long.pivot_table(index="time", columns="ticker", values="close").sort_index()
    wide_volume = long.pivot_table(index="time", columns="ticker", values="volume").sort_index()

    range_pct = (wide_high - wide_low).div(wide_close.shift(1))
    compress_10 = range_pct.rolling(10, min_periods=5).mean()
    range_expansion = range_pct.div(range_pct.rolling(10, min_periods=5).mean())
    denom = wide_high - wide_low
    close_strength = (wide_close - wide_low).div(denom.replace(0, np.nan)).mask(denom == 0, 0.5)
    vol_confirmation = wide_volume.div(wide_volume.rolling(20, min_periods=10).mean())

    compress_10_rank = 1.0 - compress_10.rank(axis=1, method="average", ascending=True, pct=True)
    expansion_rank = range_expansion.rank(axis=1, method="average", ascending=True, pct=True)
    close_rank = close_strength.rank(axis=1, method="average", ascending=True, pct=True)
    vol_rank = vol_confirmation.rank(axis=1, method="average", ascending=True, pct=True)

    breakout_2 = (compress_10_rank * expansion_rank * close_rank * vol_rank).rank(
        axis=1, method="average", ascending=True, pct=True
    )
    blowoff_2 = 1.0 - breakout_2
    return (
        blowoff_2.reset_index()
        .melt(id_vars="time", var_name="ticker", value_name="c13_compress_blowoff_2")
        .dropna(subset=["c13_compress_blowoff_2"])
    )


def build_clv_resid_features(c8: pd.DataFrame, *, end_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Compute C14 directly from OHLCV after residualizing against C8."""
    parts = []
    for f in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "high", "low", "close", "volume"])
        except Exception:
            continue
        df = _filter_source_end(df, end_date)
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < 80:
            continue
        df["ticker"] = ticker
        parts.append(df[["time", "ticker", "high", "low", "close", "volume"]])

    long = pd.concat(parts, ignore_index=True)
    wide_high = long.pivot_table(index="time", columns="ticker", values="high").sort_index()
    wide_low = long.pivot_table(index="time", columns="ticker", values="low").sort_index()
    wide_close = long.pivot_table(index="time", columns="ticker", values="close").sort_index()
    wide_volume = long.pivot_table(index="time", columns="ticker", values="volume").sort_index()

    denom = wide_high - wide_low
    clv = (wide_close - wide_low).div(denom.replace(0, np.nan)).mask(denom == 0, 0.5)
    vol_mean = wide_volume.rolling(60, min_periods=20).mean()
    vol_std = wide_volume.rolling(60, min_periods=20).std(ddof=0)
    vol_zscore_1d = (wide_volume - vol_mean).div(vol_std.replace(0, np.nan))
    clv_volconf_5d = (clv * vol_zscore_1d).rolling(5, min_periods=3).mean().rank(
        axis=1, method="average", ascending=True, pct=True
    )

    c8_wide = (
        _filter_source_end(c8, end_date)
        .rename(columns={"c8_vol_zscore_5d": "xs_vol_zscore_5d"})
        .pivot_table(index="time", columns="ticker", values="xs_vol_zscore_5d")
        .sort_index()
    )
    common_index = clv_volconf_5d.index.intersection(c8_wide.index)
    clv_volconf_5d = clv_volconf_5d.reindex(common_index)
    c8_wide = c8_wide.reindex(common_index)

    resid = pd.DataFrame(index=common_index, columns=clv_volconf_5d.columns, dtype=float)
    for date in common_index:
        frame = pd.concat(
            [
                clv_volconf_5d.loc[date].rename("target"),
                c8_wide.loc[date].rename("control"),
            ],
            axis=1,
        ).dropna()
        if len(frame) < 20:
            continue
        x = np.column_stack([np.ones(len(frame), dtype=float), frame["control"].to_numpy(dtype=float)])
        y = frame["target"].to_numpy(dtype=float)
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        resid.loc[date, frame.index] = y - x @ beta

    resid_rank = resid.rank(axis=1, method="average", ascending=True, pct=True)
    return (
        resid_rank.reset_index()
        .melt(id_vars="time", var_name="ticker", value_name="c14_clv_volconf_resid_rank")
        .dropna(subset=["c14_clv_volconf_resid_rank"])
    )


def load_c8_feature(
    *,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    c8 = pd.read_parquet(C8_PATH)[["time", "ticker", "xs_vol_zscore_5d"]]
    c8["time"] = pd.to_datetime(c8["time"])
    c8 = c8.rename(columns={"xs_vol_zscore_5d": "c8_vol_zscore_5d"})
    return _apply_date_window(c8, start_date=start_date, end_date=end_date)


def load_or_build_dense_components(
    c8: pd.DataFrame,
    *,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> dict[str, pd.DataFrame]:
    return {
        "C10": load_or_build_c10_component(start_date=start_date, end_date=end_date),
        "C11": load_or_build_c11_component(start_date=start_date, end_date=end_date),
        "C12": load_or_build_c12_component(start_date=start_date, end_date=end_date),
        "C13": load_or_build_c13_component(start_date=start_date, end_date=end_date),
        "C14": load_or_build_c14_component(c8, start_date=start_date, end_date=end_date),
    }


def _sorted_component(frame: pd.DataFrame, spec: ComponentCacheSpec) -> pd.DataFrame:
    return _validate_component_frame(frame, spec, f"{spec.label} parity frame")


def assert_component_parity(
    spec: ComponentCacheSpec,
    *,
    inline_frame: pd.DataFrame,
    cached_frame: pd.DataFrame,
    tolerance: float = 1e-12,
) -> dict[str, object]:
    inline = _sorted_component(inline_frame, spec)
    cached = _sorted_component(cached_frame, spec)
    if len(inline) != len(cached):
        raise AssertionError(f"{spec.label} row-count mismatch: inline={len(inline):,}, cached={len(cached):,}")

    inline_keys = inline[["time", "ticker"]].reset_index(drop=True)
    cached_keys = cached[["time", "ticker"]].reset_index(drop=True)
    if not inline_keys.equals(cached_keys):
        inline_only = len(inline_keys.merge(cached_keys, on=["time", "ticker"], how="left", indicator=True).query("_merge == 'left_only'"))
        cached_only = len(cached_keys.merge(inline_keys, on=["time", "ticker"], how="left", indicator=True).query("_merge == 'left_only'"))
        raise AssertionError(f"{spec.label} key coverage mismatch: inline_only={inline_only:,}, cached_only={cached_only:,}")

    diff = (inline[spec.value_col].to_numpy(dtype=float) - cached[spec.value_col].to_numpy(dtype=float))
    max_abs_diff = float(np.nanmax(np.abs(diff))) if diff.size else 0.0
    if not np.isfinite(max_abs_diff) or max_abs_diff > float(tolerance):
        raise AssertionError(f"{spec.label} value mismatch: max_abs_diff={max_abs_diff:g}, tolerance={tolerance:g}")

    return {
        "component": spec.label,
        "rows": int(len(inline)),
        "keys": int(len(inline_keys)),
        "max_abs_diff": max_abs_diff,
        "window": _frame_window(cached),
    }


def verify_component_cache_parity(
    c8: pd.DataFrame,
    *,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
    tolerance: float = 1e-12,
) -> list[dict[str, object]]:
    old_inline_builds: dict[str, Callable[[], pd.DataFrame]] = {
        "C10": lambda: build_illiq_level_features(end_date=end_date),
        "C11": lambda: build_3m_continuation_features(end_date=end_date),
        "C12": lambda: build_gap_absorption_features(end_date=end_date),
        "C13": lambda: build_compress_blowoff_features(end_date=end_date),
        "C14": lambda: build_clv_resid_features(c8, end_date=end_date),
    }
    cached_builds: dict[str, Callable[[], pd.DataFrame]] = {
        "C10": lambda: load_or_build_c10_component(start_date=start_date, end_date=end_date),
        "C11": lambda: load_or_build_c11_component(start_date=start_date, end_date=end_date),
        "C12": lambda: load_or_build_c12_component(start_date=start_date, end_date=end_date),
        "C13": lambda: load_or_build_c13_component(start_date=start_date, end_date=end_date),
        "C14": lambda: load_or_build_c14_component(c8, start_date=start_date, end_date=end_date),
    }

    results: list[dict[str, object]] = []
    for label in ("C10", "C11", "C12", "C13", "C14"):
        spec = COMPONENT_SPECS[label]
        inline = _apply_date_window(old_inline_builds[label](), start_date=start_date, end_date=end_date)
        cached = cached_builds[label]()
        result = assert_component_parity(spec, inline_frame=inline, cached_frame=cached, tolerance=tolerance)
        print(f"  {label}: parity ok rows={result['rows']:,} max_abs_diff={result['max_abs_diff']:.3g}")
        results.append(result)
    return results


def main():
    args = parse_args()
    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    print("Building RL signal matrix...")

    if start_date or end_date:
        print(f"  Requested window: {_date_token(start_date) or '-inf'} -> {_date_token(end_date) or '+inf'}")

    c8 = load_c8_feature(start_date=start_date, end_date=end_date)
    components = load_or_build_dense_components(c8, start_date=start_date, end_date=end_date)
    if args.verify_component_parity:
        verify_component_cache_parity(c8, start_date=start_date, end_date=end_date)
    if args.component_cache_only:
        print("Component-cache-only run complete.")
        return

    # S1 — primary signal spine (394 tickers, 2015–2025)
    s1 = load_s1_spine()
    s1 = _apply_date_window(s1, start_date=start_date, end_date=end_date)
    print(
        f"  S1:  {len(s1):,} rows, {s1['ticker'].nunique()} tickers, "
        f"{s1['time'].min().date()} -> {s1['time'].max().date()}"
    )

    # C4 — open/close asymmetry
    c4 = pd.read_parquet(C4_PATH)[["time", "ticker", "oc_asym_5d"]]
    c4["time"] = pd.to_datetime(c4["time"])
    c4 = c4.rename(columns={"oc_asym_5d": "c4_oc_asym_5d"})
    c4 = _apply_date_window(c4, start_date=start_date, end_date=end_date)

    # C5 — insider quality (sparse; time column is 'trading_day')
    c5_raw = pd.read_parquet(C5_PATH)[["trading_day", "ticker", "xs_ins_relative_size_5d"]]
    c5_raw = c5_raw.rename(columns={"trading_day": "time", "xs_ins_relative_size_5d": "c5_ins_relative_size_5d"})
    c5_raw["time"] = pd.to_datetime(c5_raw["time"])
    c5_raw["c5_signal_present"] = (c5_raw["c5_ins_relative_size_5d"].notna() & (c5_raw["c5_ins_relative_size_5d"] != 0)).astype(float)
    c5_raw = _apply_date_window(c5_raw, start_date=start_date, end_date=end_date)

    # C6 — contrarian intra-sector (computed on the fly)
    c6_raw = pd.read_parquet(C6_PATH)[["time", "ticker", "xs_sector_mom_5d_rank", "xs_intra_sector_rank"]]
    c6_raw["time"] = pd.to_datetime(c6_raw["time"])
    c6_raw["c6_contrarian_intra_5d"] = (
        c6_raw["xs_sector_mom_5d_rank"] * (1.0 - c6_raw["xs_intra_sector_rank"])
    )
    c6 = c6_raw[["time", "ticker", "c6_contrarian_intra_5d"]]
    c6 = _apply_date_window(c6, start_date=start_date, end_date=end_date)

    # C7 — price limit count
    c7 = pd.read_parquet(C7_PATH)[["time", "ticker", "xs_ceiling_count_5d"]]
    c7["time"] = pd.to_datetime(c7["time"])
    c7 = c7.rename(columns={"xs_ceiling_count_5d": "c7_ceiling_count_5d"})
    c7 = _apply_date_window(c7, start_date=start_date, end_date=end_date)

    # C9 — short-term reversal
    c9 = pd.read_parquet(C9_PATH)[["time", "ticker", "xs_reversal_1d"]]
    c9["time"] = pd.to_datetime(c9["time"])
    c9 = c9.rename(columns={"xs_reversal_1d": "c9_reversal_1d"})
    c9 = _apply_date_window(c9, start_date=start_date, end_date=end_date)

    # Merge everything on (time, ticker) — left join to S1 spine
    result = s1.copy()
    for name, df in [
        ("C4", c4),
        ("C5", c5_raw[["time", "ticker", "c5_ins_relative_size_5d", "c5_signal_present"]]),
        ("C6", c6),
        ("C7", c7),
        ("C8", c8),
        ("C9", c9),
        ("C10", components["C10"]),
        ("C11", components["C11"]),
        ("C12", components["C12"]),
        ("C13", components["C13"]),
        ("C14", components["C14"]),
    ]:
        result = result.merge(df, on=["time", "ticker"], how="left")
        print(f"  After {name}: {result.shape}")

    # Rename S1 column
    result = result.rename(columns={"xs_proba": "s1_proba"})

    signal_cols = ["s1_proba", "c4_oc_asym_5d", "c5_ins_relative_size_5d", "c5_signal_present",
                   "c6_contrarian_intra_5d", "c7_ceiling_count_5d", "c8_vol_zscore_5d",
                   "c9_reversal_1d", "c10_illiq_level_rank", "c11_ret_60d_lag_rank",
                   "c12_gap_absorb_3", "c13_compress_blowoff_2", "c14_clv_volconf_resid_rank"]

    print("\nCoverage summary:")
    for col in signal_cols:
        nz = result[col].notna().sum()
        print(f"  {col:<32s}: {nz:,} ({100*nz/len(result):.1f}%)")

    atomic_write_parquet(result, OUT_PATH)
    print(f"\nSaved -> {OUT_PATH}")
    print(f"Shape: {result.shape}")


if __name__ == "__main__":
    main()
