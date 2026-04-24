"""Preferred alias for publishing the trained forward-looking PhoBERT lane."""

from __future__ import annotations

from research_pipelines.news_features.core.publish_phobert_forward_looking_exports import *  # noqa: F401,F403
from research_pipelines.news_features.core.publish_phobert_forward_looking_exports import main as _main


if __name__ == "__main__":
    _main()
