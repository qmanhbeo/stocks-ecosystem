"""Reusable IO helpers for the news feature pipeline."""

from __future__ import annotations

import json
import re
from hashlib import md5
from pathlib import Path
import tempfile
from typing import Dict, Iterable, List, Optional

import pandas as pd
import yaml

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config


STOCK_FILENAME_PATTERN = re.compile(r"^gia_lich_su_(?P<ticker>[A-Za-z0-9]+)_(?P<timeframe>[A-Za-z0-9]+)\.parquet$")


def load_yaml_file(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def dump_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_parquet_atomic(df: pd.DataFrame, path: Path, **kwargs: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".parquet", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        df.to_parquet(temp_path, **kwargs)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def read_json(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    rows: List[Dict[str, object]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl_records(path: Path, rows: Iterable[Dict[str, object]], append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def update_manifest(config: Optional[NewsFeaturesConfig] = None, **updates: object) -> Dict[str, object]:
    config = config or get_default_config()
    current = read_json(config.manifest_path)
    current.update(updates)
    dump_json(config.manifest_path, current)
    return current


def update_source_manifest(source: str, payload: Dict[str, object], config: Optional[NewsFeaturesConfig] = None) -> None:
    config = config or get_default_config()
    dump_json(config.source_manifest_path(source), payload)


def canonicalize_url(url: str) -> str:
    value = str(url).strip()
    value = value.replace("http://", "https://")
    if "?" in value:
        value = value.split("?", 1)[0]
    return value.rstrip("/")


def make_article_id(source: str, url: str) -> str:
    normalized = canonicalize_url(url)
    return md5(f"{source.lower()}::{normalized}".encode("utf-8")).hexdigest()[:16]


def list_raw_news_files(source: str | None = None, config: Optional[NewsFeaturesConfig] = None) -> List[Path]:
    config = config or get_default_config()
    root = config.source_raw_dir(source)
    return sorted(path for path in root.glob("*.jsonl") if path.is_file())


def load_raw_news_dataframe(
    source: str | None = None,
    config: Optional[NewsFeaturesConfig] = None,
    log_progress: bool = False,
    progress_every_files: int = 100,
) -> pd.DataFrame:
    config = config or get_default_config()
    paths = list_raw_news_files(source=source, config=config)
    rows: List[Dict[str, object]] = []
    total_files = len(paths)
    progress_interval = max(int(progress_every_files), 1)
    for index, path in enumerate(paths, start=1):
        file_rows = read_jsonl(path)
        rows.extend(file_rows)
        if log_progress and (
            index == 1
            or index % progress_interval == 0
            or index == total_files
        ):
            print(
                f"Loaded raw news file {index}/{total_files}: {path.name} "
                f"(rows_in_file={len(file_rows)}, accumulated_rows={len(rows)})",
                flush=True,
            )
    return pd.DataFrame(rows)


def load_feature_spec(config: Optional[NewsFeaturesConfig] = None) -> Dict[str, object]:
    config = config or get_default_config()
    defaults: Dict[str, object] = {
        "rolling_windows": config.rolling_windows,
        "sentiment": {
            "positive_keywords": ["tang truong", "loi nhuan", "mo rong", "but pha", "tich cuc"],
            "negative_keywords": ["thua lo", "suy giam", "rui ro", "ap luc", "tieu cuc"],
        },
    }
    loaded = load_yaml_file(config.feature_spec_path())
    if not loaded:
        return defaults
    merged = dict(defaults)
    merged.update(loaded)
    if "sentiment" in loaded:
        merged["sentiment"] = dict(defaults["sentiment"])
        merged["sentiment"].update(loaded["sentiment"])
    return merged


def load_source_specs(config: Optional[NewsFeaturesConfig] = None) -> Dict[str, object]:
    config = config or get_default_config()
    defaults = {
        "cafef": {
            "base_url": "https://cafef.vn",
            "sitemap_index_url": "https://cafef.vn/sitemap.xml",
            "category_url": "https://cafef.vn/thi-truong-chung-khoan.chn",
            "rss_url": "https://cafef.vn/thi-truong-chung-khoan.rss",
            "user_agent": "Mozilla/5.0 (compatible; VN-Stock-RL-NewsFetcher/1.0)",
        }
    }
    loaded = load_yaml_file(config.source_config_path())
    if not loaded:
        return defaults
    merged = dict(defaults)
    merged.update(loaded)
    return merged


def discover_stock_tickers(stock_dir: Optional[Path] = None, config: Optional[NewsFeaturesConfig] = None) -> List[str]:
    config = config or get_default_config()
    root = Path(stock_dir or config.raw_stock_dir)
    tickers: List[str] = []
    for path in root.glob("*.parquet"):
        match = STOCK_FILENAME_PATTERN.match(path.name)
        if not match:
            continue
        tickers.append(match.group("ticker").upper())
    return sorted(dict.fromkeys(tickers))


def normalize_date_strings(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce").dt.strftime("%Y-%m-%d")


def describe_path(path: Path, config: Optional[NewsFeaturesConfig] = None) -> str:
    config = config or get_default_config()
    candidates = [
        config.repo_root.parent,
        config.repo_root,
    ]
    for root in candidates:
        try:
            return str(path.relative_to(root))
        except ValueError:
            continue
    return str(path)
