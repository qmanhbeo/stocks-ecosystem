from __future__ import annotations

import json

import pandas as pd

from data_tools import build_llm_news_features as builder


def _write_jsonl(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_builder_handles_old_and_new_cache_fields(monkeypatch, tmp_path) -> None:
    feature_dir = tmp_path / "features"
    cache_dir = tmp_path / "llm_cache"
    grid_path = feature_dir / "xs_barrier_vol_1d_hose_full.parquet"
    sector_path = feature_dir / "sector_classification.parquet"

    feature_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-04-01", "2026-04-02"]),
            "ticker": ["AAA", "AAA"],
        }
    ).to_parquet(grid_path, index=False)

    pd.DataFrame(
        {
            "symbol": ["AAA"],
            "icb_name2": ["Ngân hàng"],
            "icb_name3": ["Ngân hàng"],
            "icb_name4": ["Ngân hàng"],
        }
    ).to_parquet(sector_path, index=False)

    _write_jsonl(
        cache_dir / "2026-04-01.jsonl",
        [
            {
                "id": "2026-04-01_0001",
                "tickers": ["AAA"],
                "related_tickers": ["BBB"],
                "sentiment": 1,
                "confidence": 2,
                "event_type": "contract_win",
                "magnitude": 2,
                "is_forward_looking": False,
                "market_tone": 1,
                "is_rumor": False,
                "surprise_direction": 1,
                "impact_scope": "stock",
                "named_persons": ["CEO A"],
                "expectation_alignment": "beats",
                "information_novelty": "new",
                "macro_theme": "banking",
                "source_authority": "official",
                "causal_impact_label": "revenue_positive",
                "published_at": "2026-04-01T08:15:00",
                "source_domain": "cafef.vn",
                "event_time_type": "pre_market",
                "article_text_length": 123,
                "article_has_numbers": True,
                "article_mentions_percent": False,
            }
        ],
    )
    _write_jsonl(
        cache_dir / "2026-04-02.jsonl",
        [
            {
                "id": "2026-04-02_0001",
                "tickers": ["AAA"],
                "sentiment": -1,
                "confidence": 1,
                "event_type": "legal_issue",
                "magnitude": 1,
                "is_forward_looking": True,
                "market_tone": -1,
                "is_rumor": True,
                "surprise_direction": -1,
                "impact_scope": "market",
            }
        ],
    )

    monkeypatch.setattr(builder, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(builder, "FEATURE_DIR", feature_dir)
    monkeypatch.setattr(builder, "GRID_PATH", grid_path)
    monkeypatch.setattr(builder, "SECTOR_PATH", sector_path)

    llm = builder._load_llm_cache("", "")
    ticker_day = builder._build_ticker_day(llm, builder._load_grid())
    market_day = builder._build_market_daily(llm, builder._load_grid())

    assert {"expectation_alignment", "information_novelty", "macro_theme", "source_authority", "causal_impact_label"}.issubset(llm.columns)
    assert "llm_expectation_beats_5d" in ticker_day.columns
    assert "llm_theme_banking_5d" in ticker_day.columns
    assert "frac_expectation_beats" in market_day.columns
    assert "frac_causal_financing_negative" in market_day.columns

    day1 = ticker_day.loc[ticker_day["time"] == pd.Timestamp("2026-04-01")].iloc[0]
    day2 = ticker_day.loc[ticker_day["time"] == pd.Timestamp("2026-04-02")].iloc[0]
    assert day1["llm_expectation_beats_5d"] == 1.0
    assert day1["llm_official_source_5d"] == 1.0
    assert day1["llm_theme_banking_5d"] == 1.0
    assert day2["llm_expectation_beats_5d"] == 1.0
    assert day2["llm_followup_info_5d"] == 0.0

    market1 = market_day.loc[market_day["time"] == pd.Timestamp("2026-04-01")].iloc[0]
    assert market1["frac_expectation_beats"] == 1.0
    assert market1["frac_official_source"] == 1.0
    assert market1["frac_regulation_theme"] == 0.0
