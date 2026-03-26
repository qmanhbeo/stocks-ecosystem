"""Reward-shaping helpers used by the package."""

from __future__ import annotations


def drawdown_penalty_config(enabled: bool, lambda_: float, train_only: bool) -> dict[str, float | bool]:
    return {"enabled": bool(enabled), "lambda": float(lambda_), "train_only": bool(train_only)}
