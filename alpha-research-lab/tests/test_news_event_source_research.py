from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.news_event_source_research import (
    build_alias_expanded_news_event_bundle,
    build_candidate_news_event_bundle,
    build_candidate_news_event_bundle_from_scan,
    build_strict_title_alias_map,
    classify_event_families,
    compute_event_density_gate,
    evaluate_title_alias_map_holdout,
    extract_title_tickers,
    scan_news_event_archive,
    summarize_recent_event_window_coverage,
    summarize_company_event_novelty_vs_v1,
)


def _write_day(path: Path, articles: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for article in articles:
            handle.write(json.dumps(article, ensure_ascii=False) + "\n")


def test_extract_title_tickers_respects_allowed_universe():
    title = "Lợi nhuận tăng mạnh tại Thép Pomina (POM) và FPT Retail (FRT)"
    assert extract_title_tickers(title) == ["FRT", "POM"]
    assert extract_title_tickers(title, allowed_tickers={"POM"}) == ["POM"]


def test_classify_event_families_detects_key_company_event_types():
    assert "earnings_company" in classify_event_families(title="BCTC quý 4: lợi nhuận tăng mạnh")
    assert "shareholder_meeting" in classify_event_families(title="ĐHĐCĐ thường niên thông qua kế hoạch")
    assert "rights_issuance" in classify_event_families(title="Doanh nghiệp chào bán quyền mua để tăng vốn")
    assert "board_management" in classify_event_families(title="HĐQT bổ nhiệm Tổng giám đốc mới")


def test_build_candidate_news_event_bundle_filters_to_company_event_articles(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    _write_day(
        raw_dir / "2023-01-03.jsonl",
        [
            {
                "article_id": "a1",
                "published_at": "2023-01-03T09:00:00Z",
                "title": "Doanh nghiệp (AAA) công bố BCTC quý 4 với lợi nhuận tăng mạnh",
                "summary": "Kết quả kinh doanh vượt kỳ vọng",
                "body_text": "",
                "url": "https://example.com/a1",
            },
            {
                "article_id": "a2",
                "published_at": "2023-01-03T10:00:00Z",
                "title": "HĐQT tại (BBB) bổ nhiệm Tổng giám đốc mới",
                "summary": "Nghị quyết vừa được công bố",
                "body_text": "",
                "url": "https://example.com/a2",
            },
            {
                "article_id": "a3",
                "published_at": "2023-01-03T11:00:00Z",
                "title": "Tin vĩ mô chung không gắn ticker",
                "summary": "VN-Index tăng điểm",
                "body_text": "",
                "url": "https://example.com/a3",
            },
        ],
    )

    bundle = build_candidate_news_event_bundle(
        raw_dir=raw_dir,
        start_date="2023-01-01",
        end_date="2023-12-31",
        allowed_tickers={"AAA", "BBB"},
    )

    assert bundle.summary["candidate_unique_tickers"] == 2
    assert bundle.summary["title_ticker_articles"] == 2
    assert bundle.summary["timestamped_title_ticker_articles"] == 2
    assert set(bundle.article_events["event_family"]) == {"earnings_company", "board_management"}
    assert set(bundle.daily_flags["ticker"]) == {"AAA", "BBB"}


def test_summarize_recent_event_window_coverage_rolls_by_ticker():
    panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2023-01-03", "2023-01-04", "2023-01-05", "2023-01-03", "2023-01-05"]),
            "ticker": ["AAA", "AAA", "AAA", "BBB", "BBB"],
        }
    )
    daily_flags = pd.DataFrame(
        {
            "time": pd.to_datetime(["2023-01-03", "2023-01-05"]),
            "ticker": ["AAA", "BBB"],
            "has_company_event_article": [1, 1],
            "earnings_company": [1, 0],
            "shareholder_meeting": [0, 0],
            "rights_issuance": [0, 1],
            "board_management": [0, 0],
            "buyback": [0, 0],
        }
    )

    summary = summarize_recent_event_window_coverage(panel=panel, daily_flags=daily_flags, windows=(1, 5))

    assert np.isclose(summary["recent_has_company_event_article_1d"], 0.4)
    assert np.isclose(summary["recent_has_company_event_article_5d"], 0.8)
    assert np.isclose(summary["recent_earnings_company_5d"], 0.6)
    assert np.isclose(summary["recent_rights_issuance_1d"], 0.2)


def test_scan_archive_seed_bundle_matches_direct_builder(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    _write_day(
        raw_dir / "2023-05-10.jsonl",
        [
            {
                "article_id": "s1",
                "published_at": "2023-05-10T09:00:00Z",
                "title": "Doanh nghiệp (AAA) công bố BCTC quý 1",
                "summary": "Lợi nhuận tăng",
                "body_text": "",
                "url": "https://example.com/s1",
            },
            {
                "article_id": "s2",
                "published_at": "2023-05-10T10:00:00Z",
                "title": "Tin vĩ mô không có ticker",
                "summary": "",
                "body_text": "",
                "url": "https://example.com/s2",
            },
        ],
    )

    direct = build_candidate_news_event_bundle(
        raw_dir=raw_dir,
        start_date="2023-01-01",
        end_date="2023-12-31",
        allowed_tickers={"AAA"},
    )
    scan = scan_news_event_archive(
        raw_dir=raw_dir,
        start_date="2023-01-01",
        end_date="2023-12-31",
        allowed_tickers={"AAA"},
    )
    from_scan = build_candidate_news_event_bundle_from_scan(scan)

    assert direct.summary["candidate_unique_articles"] == from_scan.summary["candidate_unique_articles"]
    assert direct.summary["candidate_unique_tickers"] == from_scan.summary["candidate_unique_tickers"]
    assert set(from_scan.article_events["linkage_mode"]) == {"title_ticker"}


def test_strict_alias_map_holdout_and_expansion(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    _write_day(
        raw_dir / "2023-01-03.jsonl",
        [
            {
                "article_id": "a1",
                "published_at": "2023-01-03T09:00:00Z",
                "title": "The Gioi Di Dong (MWG) cong bo BCTC quy 4",
                "summary": "Loi nhuan tang",
                "body_text": "",
                "url": "https://example.com/a1",
            },
            {
                "article_id": "a2",
                "published_at": "2023-03-05T09:00:00Z",
                "title": "The Gioi Di Dong (MWG) bo nhiem tong giam doc moi",
                "summary": "Nghi quyet HDQT",
                "body_text": "",
                "url": "https://example.com/a2",
            },
            {
                "article_id": "a3",
                "published_at": "2024-07-08T09:00:00Z",
                "title": "The Gioi Di Dong (MWG) trinh co dong phuong an tang von",
                "summary": "",
                "body_text": "",
                "url": "https://example.com/a3",
            },
        ],
    )
    _write_day(
        raw_dir / "2025-01-10.jsonl",
        [
            {
                "article_id": "h1",
                "published_at": "2025-01-10T09:00:00Z",
                "title": "The Gioi Di Dong (MWG) bao lãi quý 4 tăng mạnh",
                "summary": "Ket qua kinh doanh tot",
                "body_text": "",
                "url": "https://example.com/h1",
            },
            {
                "article_id": "u1",
                "published_at": "2025-01-10T10:00:00Z",
                "title": "The Gioi Di Dong bao lãi quý 4 tăng mạnh",
                "summary": "Ket qua kinh doanh tot",
                "body_text": "",
                "url": "https://example.com/u1",
            },
        ],
    )

    scan = scan_news_event_archive(
        raw_dir=raw_dir,
        start_date="2023-01-01",
        end_date="2025-12-31",
        allowed_tickers={"MWG"},
    )
    alias_map = build_strict_title_alias_map(
        scan,
        train_start_date="2023-01-01",
        train_end_date="2024-12-31",
        min_support=3,
        min_dominance=0.9,
    )
    holdout_df, holdout_summary = evaluate_title_alias_map_holdout(
        scan,
        alias_map,
        holdout_start_date="2025-01-01",
        holdout_end_date="2025-12-31",
    )
    expanded_bundle, assignments = build_alias_expanded_news_event_bundle(scan, alias_map)

    assert "the gioi di dong" in set(alias_map["alias"])
    assert holdout_summary["assigned_rows"] == 1
    assert np.isclose(holdout_summary["assigned_precision"], 1.0)
    assert set(assignments["ticker"]) == {"MWG"}
    assert "title_alias" in set(expanded_bundle.article_events["linkage_mode"])
    assert "u1" in set(assignments["article_id"])
    assert holdout_df.loc[holdout_df["article_id"] == "h1", "predicted_ticker"].iloc[0] == "MWG"


def test_summarize_company_event_novelty_vs_v1_tracks_new_rows():
    daily_flags = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-01-10", "2025-01-11"]),
            "ticker": ["AAA", "AAA"],
            "has_company_event_article": [1, 1],
            "earnings_company": [1, 0],
            "shareholder_meeting": [0, 1],
            "rights_issuance": [0, 0],
            "board_management": [0, 0],
            "buyback": [0, 0],
        }
    )
    event_surface_v1 = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-01-10", "2025-01-11"]),
            "ticker": ["AAA", "AAA"],
            "dividend_window_pre_20d": [0.0, 1.0],
            "dividend_window_post_5d": [0.0, 0.0],
            "issuance_window_pre_20d": [0.0, 0.0],
            "issuance_window_post_5d": [0.0, 0.0],
            "recent_insider_filing_5d": [0.0, 0.0],
            "recent_insider_filing_20d": [0.0, 0.0],
            "recent_major_holder_filing_5d": [0.0, 0.0],
            "recent_major_holder_filing_20d": [0.0, 0.0],
            "recent_any_filing_5d": [0.0, 0.0],
            "recent_any_filing_20d": [0.0, 0.0],
        }
    )

    summary = summarize_company_event_novelty_vs_v1(daily_flags=daily_flags, event_surface_v1=event_surface_v1)

    assert summary["candidate_daily_rows"] == 2
    assert summary["novel_daily_rows_vs_v1"] == 1
    assert np.isclose(summary["novel_daily_share_vs_v1"], 0.5)
    assert summary["family_novelty"]["earnings_company"]["novel_rows"] == 1


def test_compute_event_density_gate_counts_recent_events():
    daily_flags = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-01-05", "2025-01-06", "2025-01-07"]),
            "ticker": ["AAA", "AAA", "AAA"],
            "has_company_event_article": [1, 1, 1],
            "earnings_company": [1, 1, 1],
            "shareholder_meeting": [0, 0, 0],
            "rights_issuance": [0, 0, 0],
            "board_management": [0, 0, 0],
            "buyback": [0, 0, 0],
        }
    )
    panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-01-05", "2025-01-06", "2025-01-07"]),
            "ticker": ["AAA", "AAA", "AAA"],
        }
    )
    gate = compute_event_density_gate(
        daily_flags=daily_flags,
        panel=panel,
        window=2,
        threshold=2,
    )
    assert gate["candidate_rows"] == 3
    assert gate["gating_rows"] > 0
    assert np.isclose(gate["coverage"], gate["gating_rows"] / gate["candidate_rows"])
