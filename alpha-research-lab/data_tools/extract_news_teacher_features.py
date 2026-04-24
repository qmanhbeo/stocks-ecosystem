"""
Preferred alias for the hosted CafeF teacher-feature extractor.

This keeps the existing `extract_llm_news_features.py` entrypoint stable while
giving operators a clearer command name for the teacher lane that feeds local
PhoBERT distillation.
"""

from __future__ import annotations

try:  # pragma: no cover - import style depends on script vs package execution
    from .extract_llm_news_features import *  # noqa: F401,F403
    from .extract_llm_news_features import main as _main
except ImportError:  # pragma: no cover
    from extract_llm_news_features import *  # type: ignore # noqa: F401,F403
    from extract_llm_news_features import main as _main  # type: ignore


if __name__ == "__main__":
    _main()
