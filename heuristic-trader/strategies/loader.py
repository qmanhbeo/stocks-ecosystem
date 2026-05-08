"""Strategy configuration loader for heuristic-trader."""

import json
from pathlib import Path
from typing import Any

STRATEGIES_DIR = Path(__file__).parent
STRATEGIES_FILE = STRATEGIES_DIR / "strategies.json"

REQUIRED_FIELDS = [
    "name",
    "signal_type",
    "signal_col",
    "top_k",
    "rebalance_days",
    "min_hold_days",
]


def load_strategies() -> dict[str, dict]:
    """Load all strategy configs from strategies.json."""
    if not STRATEGIES_FILE.exists():
        raise FileNotFoundError(f"Strategies file not found: {STRATEGIES_FILE}")

    with open(STRATEGIES_FILE) as f:
        return json.load(f)


def load_strategy_config(name: str) -> dict[str, Any]:
    """Load and validate a single strategy config.

    Args:
        name: Strategy name (key in strategies.json)

    Returns:
        Validated strategy config dict

    Raises:
        KeyError: If strategy not found
        ValueError: If config missing required fields
    """
    strategies = load_strategies()

    if name not in strategies:
        raise KeyError(f"Strategy '{name}' not found. Available: {list(strategies.keys())}")

    config = strategies[name]

    # Validate required fields
    missing = [f for f in REQUIRED_FIELDS if f not in config]
    if missing:
        raise ValueError(f"Strategy '{name}' missing required fields: {missing}")

    return config


def list_strategies() -> list[str]:
    """List all available strategy names."""
    return list(load_strategies().keys())


if __name__ == "__main__":
    print("Available strategies:")
    for name in list_strategies():
        config = load_strategy_config(name)
        print(f"  {name}: {config.get('description', 'No description')}")