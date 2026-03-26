"""Shared CLI parsing helpers used by training and evaluation entrypoints."""

from __future__ import annotations

from vn_stock_rl.external_features import (
    all_signal_feature_columns,
    default_news_feature_columns,
    default_signal_feature_columns,
    default_tabular_news_feature_columns,
)


ENGINEERED_FEATURE_FAMILIES = (
    "volatility",
    "trend",
    "momentum",
    "volume_context",
    "drawdown",
    "relative_strength",
)
REWARD_BENCHMARKS = ("self_buy_hold",)


def parse_window_list(values, arg_name: str):
    if values is None:
        return None
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{arg_name} must be a list/tuple, got {values}")
    resolved = []
    seen = set()
    for value in values:
        window = int(value)
        if window <= 0:
            raise ValueError(f"{arg_name} must contain positive integers, got {values}")
        if window in seen:
            continue
        seen.add(window)
        resolved.append(window)
    return resolved


def parse_helper_window_list(values, arg_name: str):
    if values is None:
        return None
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{arg_name} must be a list/tuple, got {values}")
    tokens = [str(v).strip().lower() for v in values]
    if "same" in tokens:
        if len(tokens) != 1:
            raise ValueError(f"{arg_name} cannot mix 'same' with numeric windows")
        return ["same"]
    return parse_window_list(values, arg_name)


def parse_engineered_feature_families(values):
    if values is None:
        return None
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"--engineered-features must be a list/tuple, got {values}")
    seen = set()
    resolved = []
    for value in values:
        name = str(value).strip().lower()
        if name not in ENGINEERED_FEATURE_FAMILIES:
            raise ValueError(
                f"Unsupported engineered feature family '{name}'. Allowed: {list(ENGINEERED_FEATURE_FAMILIES)}"
            )
        if name in seen:
            continue
        seen.add(name)
        resolved.append(name)
    return resolved


def parse_rs_market_proxies(values):
    if values is None:
        return None
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"--rs-market-proxies must be a list/tuple, got {values}")
    out = [str(v).strip().upper() for v in values if str(v).strip()]
    return out or None


def parse_news_feature_columns(values):
    if values is None:
        return None
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"--news-columns must be a list/tuple, got {values}")

    tokens = [str(v).strip() for v in values if str(v).strip()]
    if not tokens:
        return []

    lowered = [token.lower() for token in tokens]
    if len(lowered) == 1 and lowered[0] in {"none", "off", "disable", "disabled"}:
        return []

    if len(lowered) == 1 and lowered[0] == "tabular":
        return default_tabular_news_feature_columns()
    if len(lowered) == 1 and lowered[0] == "all":
        return default_news_feature_columns()

    resolved = []
    seen = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        resolved.append(token)
    return resolved


def parse_signal_feature_columns(values):
    if values is None:
        return None
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"--signal-columns must be a list/tuple, got {values}")

    tokens = [str(v).strip() for v in values if str(v).strip()]
    if not tokens:
        return []

    lowered = [token.lower() for token in tokens]
    if len(lowered) == 1 and lowered[0] in {"none", "off", "disable", "disabled"}:
        return []

    if len(lowered) == 1 and lowered[0] == "default":
        return default_signal_feature_columns()
    if len(lowered) == 1 and lowered[0] == "all":
        return all_signal_feature_columns()

    resolved = []
    seen = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        resolved.append(token)
    return resolved


def parse_reward_benchmark(value, arg_name: str = "--reward-benchmark"):
    if value is None:
        return None
    token = str(value).strip().lower()
    if token in {"", "none", "off", "disable", "disabled"}:
        return None
    if token not in REWARD_BENCHMARKS:
        raise ValueError(
            f"{arg_name} must be one of {list(REWARD_BENCHMARKS)} (or none/off), got {value!r}"
        )
    return token
