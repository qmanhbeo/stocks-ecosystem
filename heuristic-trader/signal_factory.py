"""
Shared strategy signal preparation for heuristic-trader.
"""

from __future__ import annotations

import pandas as pd

import signals as s


def prepare_signal_df_from_config(
    config: dict,
    start_date: str,
    end_date: str,
    allow_2026: bool = False,
) -> pd.DataFrame:
    """Prepare signal DataFrame from strategy config.

    Returns a frame with columns: time, ticker, <signal_col>.
    """
    signal_type = config["signal_type"]
    s1 = s.load_rl_signal_matrix(start=start_date, end=end_date, allow_2026=allow_2026)
    active_rank_threshold = float(config.get("active_rank_threshold", 0.2))
    low_breadth_percentile = float(config.get("low_breadth_percentile", 0.25))

    if signal_type == "s1_only":
        return s1[["time", "ticker", "s1_proba"]].copy()
    if signal_type == "c16_only":
        c16 = s.load_order_pressure(start=start_date, end=end_date, allow_2026=allow_2026)
        return c16[["time", "ticker", "order_volume_ratio_rank"]].copy()
    if signal_type == "c17_only":
        c17 = s.load_order_pressure_raw(start=start_date, end=end_date, allow_2026=allow_2026)
        return c17[["time", "ticker", "order_volume_ratio"]].copy()
    if signal_type == "c17_active_boost":
        c17 = s.load_order_pressure_c17_active_boost(
            start=start_date,
            end=end_date,
            allow_2026=allow_2026,
            active_rank_threshold=active_rank_threshold,
            boost_strength=float(config.get("c17_boost_strength", 0.35)),
            delta_weight=float(config.get("c17_delta_weight", 0.20)),
        )
        return c17[["time", "ticker", "c17_active_boost"]].copy()
    if signal_type == "c18_only":
        c18 = s.load_order_pressure_delta(start=start_date, end=end_date, allow_2026=allow_2026)
        return c18[["time", "ticker", "order_volume_ratio_rank_delta"]].copy()
    if signal_type == "s1_low_breadth":
        breadth = s.load_low_breadth_regime(
            start=start_date,
            end=end_date,
            allow_2026=allow_2026,
            active_rank_threshold=active_rank_threshold,
            low_breadth_percentile=low_breadth_percentile,
        )
        df = s1[["time", "ticker", "s1_proba"]].merge(
            breadth[["time", "is_low_breadth"]],
            on="time",
            how="inner",
        )
        return df[df["is_low_breadth"] == 1][["time", "ticker", "s1_proba"]].copy()
    if signal_type == "s1_active_low_breadth":
        c16 = s.load_order_pressure(start=start_date, end=end_date, allow_2026=allow_2026)
        breadth = s.load_low_breadth_regime(
            start=start_date,
            end=end_date,
            allow_2026=allow_2026,
            active_rank_threshold=active_rank_threshold,
            low_breadth_percentile=low_breadth_percentile,
        )
        df = (
            s1[["time", "ticker", "s1_proba"]]
            .merge(
                c16[["time", "ticker", "order_volume_ratio_rank"]],
                on=["time", "ticker"],
                how="inner",
            )
            .merge(
                breadth[["time", "is_low_breadth"]],
                on="time",
                how="inner",
            )
        )
        mask = (df["order_volume_ratio_rank"] < active_rank_threshold) & (df["is_low_breadth"] == 1)
        return df[mask][["time", "ticker", "s1_proba"]].copy()
    if signal_type in ("blend_70_30", "blend_50_50"):
        c16 = s.load_order_pressure(start=start_date, end=end_date, allow_2026=allow_2026)
        df = s1[["time", "ticker", "s1_proba"]].merge(
            c16[["time", "ticker", "order_volume_ratio_rank"]],
            on=["time", "ticker"],
        )
        if signal_type == "blend_70_30":
            df["blend"] = df["s1_proba"] * 0.7 + df["order_volume_ratio_rank"] * 0.3
        else:
            df["blend"] = df["s1_proba"] * 0.5 + df["order_volume_ratio_rank"] * 0.5
        return df[["time", "ticker", "blend"]]
    if signal_type == "blend_70_30_low_breadth":
        c16 = s.load_order_pressure(start=start_date, end=end_date, allow_2026=allow_2026)
        breadth = s.load_low_breadth_regime(
            start=start_date,
            end=end_date,
            allow_2026=allow_2026,
            active_rank_threshold=active_rank_threshold,
            low_breadth_percentile=low_breadth_percentile,
        )
        df = s1[["time", "ticker", "s1_proba"]].merge(
            c16[["time", "ticker", "order_volume_ratio_rank"]],
            on=["time", "ticker"],
            how="inner",
        )
        df["blend"] = df["s1_proba"] * 0.7 + df["order_volume_ratio_rank"] * 0.3
        df = df.merge(breadth[["time", "is_low_breadth"]], on="time", how="inner")
        return df[df["is_low_breadth"] == 1][["time", "ticker", "blend"]].copy()
    if signal_type == "surface_col":
        source_surface = str(config.get("source_surface", "rl_signal_matrix"))
        source_col = str(config.get("source_col", config["signal_col"]))
        signal_col = str(config["signal_col"])
        return s.load_surface_signal(
            source_surface=source_surface,
            source_col=source_col,
            start=start_date,
            end=end_date,
            allow_2026=allow_2026,
            output_col=signal_col,
        )
    if signal_type == "s1_surface_blend":
        source_surface = str(config.get("source_surface", "rl_signal_matrix"))
        source_col = str(config.get("source_col"))
        if not source_col:
            raise ValueError("s1_surface_blend requires config.source_col")
        signal_col = str(config["signal_col"])
        w_s1 = float(config.get("w_s1", 0.7))
        w_surface = float(config.get("w_surface", 0.3))
        surface = s.load_surface_signal(
            source_surface=source_surface,
            source_col=source_col,
            start=start_date,
            end=end_date,
            allow_2026=allow_2026,
            output_col="surface_component",
        )
        df = s1[["time", "ticker", "s1_proba"]].merge(
            surface,
            on=["time", "ticker"],
            how="inner",
        )
        df[signal_col] = df["s1_proba"] * w_s1 + df["surface_component"] * w_surface
        return df[["time", "ticker", signal_col]].copy()

    raise ValueError(f"Unknown signal_type: {signal_type}")

