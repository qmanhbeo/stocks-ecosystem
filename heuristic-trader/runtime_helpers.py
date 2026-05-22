"""Shared runtime helpers for heuristic-trader operator scripts."""

from __future__ import annotations

from typing import Any

import constraints as cn


def load_backtest_caches(bt_module: Any) -> tuple[dict, dict, dict]:
    """Load precomputed backtest caches from a configured backtest module."""
    liquid_lookup = bt_module.load_liquid_lookup()
    trad_lookup = bt_module.load_trad_lookup()
    price_cache = bt_module.load_price_cache()
    return liquid_lookup, trad_lookup, price_cache


def compute_vnindex_total_return(start_date: str, end_date: str) -> float | None:
    """Return VNINDEX total return over [start_date, end_date], net of simple fees."""
    try:
        vn = cn.load_vnindex(start=start_date, end=end_date)
    except Exception:
        return None

    if vn is None or len(vn) == 0:
        return None

    start_open = float(vn["open"].iloc[0])
    end_open = float(vn["open"].iloc[-1])
    shares = int(100_000_000 / start_open)
    cost = shares * start_open * 1.001
    initial_cash = 100_000_000 - cost
    proceeds = shares * end_open * 0.9984
    final_value = initial_cash + proceeds
    return float((final_value / 100_000_000) - 1.0)


def benchmark_payload(start_date: str, end_date: str) -> dict | None:
    total_return = compute_vnindex_total_return(start_date, end_date)
    if total_return is None:
        return None
    return {"total_return": total_return, "name": "VNINDEX"}
