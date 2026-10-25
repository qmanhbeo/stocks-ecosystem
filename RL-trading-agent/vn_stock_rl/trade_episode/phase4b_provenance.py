"""Small content fingerprints and immutability checks for Phase 4B."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_checkpoint_manifest(entries: list[dict[str, str]]) -> dict[str, str]:
    """Hash every checkpoint and fail closed if any differs from its manifest."""

    actual_hashes: dict[str, str] = {}
    for entry in entries:
        path = Path(entry["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Frozen checkpoint is missing: {path}")
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            raise ValueError(f"Checkpoint hash mismatch: {path}")
        actual_hashes[str(path)] = actual
    return actual_hashes


def prepared_stock_fingerprint(stock) -> str:
    """Hash values actually made available to features and execution."""

    digest = hashlib.sha256()
    digest.update(stock.ticker.encode("utf-8"))
    digest.update(np.asarray(stock.dates.asi8, dtype="<i8").tobytes())
    arrays = (
        stock.opens,
        stock.closes,
        stock.market_features,
        stock.alpha_features,
        stock.daily_volatility_scale,
        stock.can_buy,
        stock.can_sell,
    )
    for values in arrays:
        array = np.ascontiguousarray(values)
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(np.asarray(array.shape, dtype="<i8").tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()
