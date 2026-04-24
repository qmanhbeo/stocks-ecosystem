"""Preferred alias for the optional local Ollama probe lane."""

from __future__ import annotations

from research_pipelines.news_features.core.build_ollama_guarded_features import *  # noqa: F401,F403
from research_pipelines.news_features.core.build_ollama_guarded_features import main as _main


if __name__ == "__main__":
    _main()
