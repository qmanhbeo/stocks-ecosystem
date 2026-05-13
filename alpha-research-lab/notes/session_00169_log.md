# Session 169

Date: 2026-04-24

## Goal

Reduce the visible news-extractor command sprawl without changing outputs,
status files, or compatibility imports.

## Changes

- added clearer operator aliases for the teacher lane:
  - `data_tools/extract_news_teacher_features.py`
  - `data_tools/extract_news_teacher_features_legacy.py`
- added clearer preferred aliases inside the news feature pipeline:
  - `research_pipelines/news_features/core/build_ollama_probe_features.py`
  - `research_pipelines/news_features/core/publish_phobert_forward_looking_features.py`
- kept the older command names in place as compatibility surfaces
- updated the main operator docs to describe the active path as:
  - PhoBERT sentiment + PhoBERT forward-looking for local production
  - hosted teacher extraction as the teacher/cache lane
  - Ollama as an optional probe lane rather than a peer mainline

## Verification

- `python -m py_compile alpha-research-lab/data_tools/extract_news_teacher_features.py alpha-research-lab/data_tools/extract_news_teacher_features_legacy.py alpha-research-lab/research_pipelines/news_features/core/build_ollama_probe_features.py alpha-research-lab/research_pipelines/news_features/core/publish_phobert_forward_looking_features.py`
- `python -m pytest alpha-research-lab/tests/test_extract_llm_news_features.py alpha-research-lab/research_pipelines/news_features/tests/test_feature_builders.py`

## Notes

- no data paths, dataset names, or job-status file names changed
- old names remain valid for tests, historical notes, and operator muscle memory
