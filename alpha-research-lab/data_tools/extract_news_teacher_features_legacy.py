"""
Preferred alias for the compatibility-heavy teacher extractor surface.

The legacy entrypoint keeps the older hosted-provider pool and local Ollama
path. This alias exists only to make the teacher role explicit without
breaking imports or historical commands that still use the old file name.
"""

from __future__ import annotations

try:  # pragma: no cover - import style depends on script vs package execution
    from .extract_llm_news_features_legacy import *  # noqa: F401,F403
    from .extract_llm_news_features_legacy import main as _main
except ImportError:  # pragma: no cover
    from extract_llm_news_features_legacy import *  # type: ignore # noqa: F401,F403
    from extract_llm_news_features_legacy import main as _main  # type: ignore


if __name__ == "__main__":
    _main()
