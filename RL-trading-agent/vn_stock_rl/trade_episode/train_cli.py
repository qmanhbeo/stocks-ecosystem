from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from vn_stock_rl.trade_episode.config import (
    DEFAULT_OUTPUT_ROOT,
    WORKSPACE_ROOT,
    TradeEpisodePaths,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the isolated stock trade-episode RL run")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    data_root = args.data_root or Path(os.environ.get("STOCKS_DATA_ROOT", WORKSPACE_ROOT / "data"))
    output_root = args.output_root or Path(
        os.environ.get("STOCK_RL_TRADE_EPISODE_OUTPUT_ROOT", DEFAULT_OUTPUT_ROOT)
    )
    output_paths = TradeEpisodePaths(root=output_root)
    matplotlib_cache = output_paths.cache / "matplotlib"
    matplotlib_cache.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(matplotlib_cache)

    # Delay importing SB3/Torch until after output/cache paths are configured.
    from vn_stock_rl.trade_episode.training import train_trade_episode

    result = train_trade_episode(
        args.config,
        data_root=data_root,
        output_root=output_root,
        smoke=args.smoke,
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
