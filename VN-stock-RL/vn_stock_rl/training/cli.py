from __future__ import annotations

from typing import Optional

from vn_stock_rl.training.args import namespace_to_train_kwargs, parse_args
from vn_stock_rl.training.runner import train


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    train(**namespace_to_train_kwargs(args))
    return 0


__all__ = ["main", "train"]


if __name__ == "__main__":
    raise SystemExit(main())
