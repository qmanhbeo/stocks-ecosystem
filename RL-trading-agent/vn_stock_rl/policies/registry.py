"""Shared policy-name and metadata helpers."""

from __future__ import annotations

import json
from pathlib import Path

from vn_stock_rl.config import POLICY_CONFIGS


INTERNAL_POLICY_MAP = {
    "mlp": "mlp",
    "lstm": "lstm",
    "cnn": "cnn",
    "cnn-lstm": "cnn_lstm",
    "cnn-attention": "cnn_attention",
    "cnn-attention-lstm": "cnn_attention_lstm",
    "cnn-window-attention": "cnn_window_attention",
    "cnn-window-attention-lstm": "cnn_window_attention_lstm",
    "multi-cnn": "multi_cnn",
    "multi-cnn-lstm": "multi_cnn_lstm",
    "transformer": "transformer",
    "transformer-lstm": "transformer_lstm",
}
DISPLAY_POLICY_MAP = {internal: display for display, internal in INTERNAL_POLICY_MAP.items()}
RECURRENT_POLICIES = {
    "lstm",
    "cnn_lstm",
    "cnn_attention_lstm",
    "cnn_window_attention_lstm",
    "multi_cnn_lstm",
    "transformer_lstm",
}


def available_policies() -> list[str]:
    return list(INTERNAL_POLICY_MAP.keys())


def normalize_policy(policy: str) -> str:
    normalized = (policy or "").strip().lower()
    if normalized in INTERNAL_POLICY_MAP.values():
        return normalized
    if normalized in INTERNAL_POLICY_MAP:
        return INTERNAL_POLICY_MAP[normalized]
    return normalized


def policy_display_name(policy: str) -> str:
    return DISPLAY_POLICY_MAP.get(policy, policy)


def is_recurrent_policy(policy: str) -> bool:
    return normalize_policy(policy) in RECURRENT_POLICIES


def get_policy_config(policy: str) -> dict:
    normalized = normalize_policy(policy)
    if normalized not in POLICY_CONFIGS:
        raise KeyError(f"Unknown policy '{policy}'. Known keys: {sorted(POLICY_CONFIGS)}")
    return POLICY_CONFIGS[normalized]


def read_policy_from_metadata(model_path: str) -> str | None:
    meta_base = Path(model_path).with_suffix("")
    meta_path = meta_base.parent / f"{meta_base.name}_meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    raw = str(meta.get("policy", "")).strip().lower()
    if not raw:
        return None
    try:
        return policy_display_name(normalize_policy(raw))
    except Exception:
        return raw
