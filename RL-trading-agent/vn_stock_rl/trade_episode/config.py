from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[3]


def _common_checkout_root() -> Path:
    git_file = WORKTREE_ROOT / ".git"
    if not git_file.is_file():
        return WORKTREE_ROOT
    content = git_file.read_text(encoding="utf-8").strip()
    if not content.startswith("gitdir:"):
        return WORKTREE_ROOT
    git_dir = Path(content.split(":", 1)[1].strip())
    if not git_dir.is_absolute():
        git_dir = WORKTREE_ROOT / git_dir
    common_dir_file = git_dir.resolve() / "commondir"
    if not common_dir_file.is_file():
        return WORKTREE_ROOT
    common_dir = (git_dir.resolve() / common_dir_file.read_text(encoding="utf-8").strip()).resolve()
    return common_dir.parent if common_dir.name == ".git" else WORKTREE_ROOT


WORKSPACE_ROOT = _common_checkout_root()
DEFAULT_OUTPUT_ROOT = Path("/home/manh/stocks-ecosystem-runs/rl-trade-episode")


@dataclass(frozen=True)
class TradeEpisodeConfig:
    """Environment and first-run settings; this does not launch a trainer."""

    min_holding_intervals: int = 3
    annualization_intervals: int = 252
    annual_benchmark: float = 0.07
    gamma: float = 1.0
    max_episode_steps: int = 252
    max_wait_steps: int = 252
    max_holding_intervals: int = 252
    algorithm: str = "MaskablePPO"
    policy: str = "MlpPolicy"

    def __post_init__(self) -> None:
        if self.min_holding_intervals < 1:
            raise ValueError("min_holding_intervals must be positive")
        if self.annualization_intervals < 1:
            raise ValueError("annualization_intervals must be positive")
        if self.annual_benchmark <= -1.0:
            raise ValueError("annual_benchmark must be greater than -1")
        if self.gamma != 1.0:
            raise ValueError("The initial trade-episode experiment requires gamma=1.0")
        if min(self.max_episode_steps, self.max_wait_steps, self.max_holding_intervals) < 1:
            raise ValueError("Episode, waiting, and holding horizons must be positive")
        if self.algorithm != "MaskablePPO":
            raise ValueError("The initial discrete masked-action setup requires MaskablePPO")


@dataclass(frozen=True)
class TradeEpisodePaths:
    """Isolated output locations; directories are created only by ensure_created()."""

    root: Path | None = None

    def __post_init__(self) -> None:
        configured = self.root or Path(
            os.environ.get("STOCK_RL_TRADE_EPISODE_OUTPUT_ROOT", DEFAULT_OUTPUT_ROOT)
        )
        resolved = Path(configured).expanduser().resolve()
        data_root = (
            Path(os.environ.get("STOCKS_DATA_ROOT", WORKSPACE_ROOT / "data")).expanduser().resolve()
        )
        if resolved == WORKSPACE_ROOT or resolved.is_relative_to(WORKSPACE_ROOT):
            raise ValueError(
                "Trade-episode outputs must be outside the shared workspace/repositories"
            )
        if resolved == WORKTREE_ROOT or resolved.is_relative_to(WORKTREE_ROOT):
            raise ValueError("Trade-episode outputs must be outside the experimental worktree")
        if resolved == data_root or resolved.is_relative_to(data_root):
            raise ValueError("Trade-episode outputs must not be inside the shared data root")
        object.__setattr__(self, "root", resolved)

    @property
    def models(self) -> Path:
        return self.root / "models"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def evaluations(self) -> Path:
        return self.root / "evaluations"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    @property
    def configs(self) -> Path:
        return self.root / "configs"

    @property
    def temporary(self) -> Path:
        return self.root / "tmp"

    def ensure_created(self) -> None:
        for path in (
            self.models,
            self.logs,
            self.evaluations,
            self.cache,
            self.configs,
            self.temporary,
        ):
            path.mkdir(parents=True, exist_ok=True)
