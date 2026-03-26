from __future__ import annotations

import subprocess
from datetime import datetime

import numpy as np


def _to_jsonable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    return str(value)

def _get_git_commit_info():
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return None, None

    try:
        dirty_output = subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        is_dirty = bool(dirty_output)
    except Exception:
        is_dirty = None
    return commit, is_dirty

def _get_env_attr(env, attr_name, default=None):
    try:
        value = env.get_attr(attr_name)
        if isinstance(value, list):
            return value[0] if value else default
        return value
    except Exception:
        pass
    try:
        return env.get_wrapper_attr(attr_name)
    except Exception:
        pass
    try:
        return getattr(env, attr_name, default)
    except Exception:
        return default

def _sanitize_name_token(token) -> str:
    cleaned = "".join(ch for ch in str(token) if ch.isalnum() or ch in ("_", "-"))
    return cleaned or "NA"

def _auto_model_name(policy: str, stock: str, stocks: list, all_stocks: bool, total_timesteps: int) -> str:
    if stock:
        stock_token = _sanitize_name_token(str(stock).upper())
    elif all_stocks:
        stock_token = "ALL"
    elif stocks:
        stock_token = _sanitize_name_token(str(stocks[0]).upper()) if len(stocks) == 1 else "MULTI"
    else:
        stock_token = "UNKNOWN"

    policy_token = _sanitize_name_token(policy)
    timesteps_token = str(int(total_timesteps))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{policy_token}_{stock_token}_{timesteps_token}_{timestamp}"
