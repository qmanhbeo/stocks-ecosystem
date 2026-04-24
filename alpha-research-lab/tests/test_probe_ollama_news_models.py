from __future__ import annotations

from pathlib import Path

from data_tools import probe_ollama_news_models as probe


def _sample_article(expectation: probe.ArticleExpectation | None = None) -> probe.LoadedArticle:
    return probe.LoadedArticle(
        label="A1",
        date="2026-01-01",
        path=Path("data/news/cafef/raw/2026-01-01.jsonl"),
        article_id="8002e4554e3b25a6",
        title="IPA muốn huy động tối đa 608 tỷ đồng từ trái phiếu để làm gì?",
        summary="Bản tin về kế hoạch trái phiếu của IPA.",
        body_text="IPA dự kiến phát hành trái phiếu để bổ sung vốn cho các kế hoạch đầu tư.",
        published_at="2026-01-01T08:30:00+07:00",
        url="https://cafef.vn/example",
        is_financial_article=True,
        expectation=expectation,
    )


def test_parse_article_arg_accepts_optional_label() -> None:
    assert probe._parse_article_arg("2026-01-01|8002e4554e3b25a6|A1") == (
        "2026-01-01",
        "8002e4554e3b25a6",
        "A1",
    )
    assert probe._parse_article_arg("2026-01-01|8002e4554e3b25a6") == (
        "2026-01-01",
        "8002e4554e3b25a6",
        None,
    )


def test_resolve_models_merges_cli_and_file_without_duplicates(tmp_path) -> None:
    models_file = tmp_path / "models.txt"
    models_file.write_text(
        "\n".join(
            [
                "# preferred candidates",
                "phi4-mini",
                "granite3-moe:3b",
                "llama3.2:3b",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    models = probe._resolve_models("llama3.2:3b,qwen2.5-coder:3b", str(models_file))

    assert models == [
        "llama3.2:3b",
        "qwen2.5-coder:3b",
        "phi4-mini",
        "granite3-moe:3b",
    ]


def test_build_probe_prompt_includes_full_body_and_xml_anchor() -> None:
    article = _sample_article()

    prompt, meta = probe._build_probe_prompt(article, prompt_style="xml_anchor", max_body_chars=0)

    assert "Body: IPA dự kiến phát hành trái phiếu" in prompt
    assert "<article_extraction>" in prompt
    assert "Do not output the XML scaffold." in prompt
    assert meta["body_chars_in_prompt"] == len(article.body_text)
    assert meta["body_truncated"] is False


def test_parse_and_normalize_response_and_score_match_expected_fields() -> None:
    expectation = probe.ArticleExpectation(
        tickers=("IPA",),
        event_type="debt_issue",
        impact_scope="stock",
        source_authority="official",
        is_forward_looking=True,
        is_rumor=False,
    )

    normalized, meta = probe._parse_and_normalize_response(
        "8002e4554e3b25a6",
        """
        {
          "id": "8002e4554e3b25a6",
          "tickers": ["IPA"],
          "related_tickers": [],
          "sentiment": 1,
          "confidence": 2,
          "event_type": "debt_issue",
          "magnitude": 1,
          "is_forward_looking": true,
          "market_tone": 0,
          "is_rumor": false,
          "surprise_direction": 0,
          "impact_scope": "stock",
          "named_persons": [],
          "expectation_alignment": "not_applicable",
          "information_novelty": "new",
          "macro_theme": "none",
          "source_authority": "official",
          "causal_impact_label": "financing_positive"
        }
        """,
    )
    score = probe._score_article_result(normalized, expectation)

    assert meta["parse_error"] is None
    assert normalized["tickers"] == ["IPA"]
    assert normalized["event_type"] == "debt_issue"
    assert score == {
        "ticker_exact": 1,
        "event_match": 1,
        "core_trust_hits": 4,
        "core_trust_total": 4,
    }


def test_summarize_probe_runs_aggregates_parse_and_score_totals() -> None:
    summary = probe._summarize_probe_runs(
        [
            {
                "elapsed_sec": 10.0,
                "call_error": None,
                "parse_error": None,
                "normalized": {"tickers": ["IPA"]},
                "peak_ram_mib": 2100.0,
                "delta_ram_mib": 300.0,
                "peak_vram_mib": 2400.0,
                "delta_vram_mib": 900.0,
                "score": {
                    "ticker_exact": 1,
                    "event_match": 1,
                    "core_trust_hits": 4,
                    "core_trust_total": 4,
                },
            },
            {
                "elapsed_sec": 14.0,
                "call_error": "timeout",
                "parse_error": "json_parse_fail",
                "normalized": None,
                "peak_ram_mib": 2300.0,
                "delta_ram_mib": 450.0,
                "peak_vram_mib": 2500.0,
                "delta_vram_mib": 950.0,
                "score": {
                    "ticker_exact": None,
                    "event_match": None,
                    "core_trust_hits": None,
                    "core_trust_total": None,
                },
            },
        ]
    )

    assert summary == {
        "articles": 2,
        "avg_elapsed_sec": 12.0,
        "parse_failures": 1,
        "peak_ram_mib": 2300.0,
        "peak_ram_delta_mib": 450.0,
        "peak_vram_mib": 2500.0,
        "peak_vram_delta_mib": 950.0,
        "ticker_exact_hits": 1,
        "ticker_exact_total": 1,
        "event_match_hits": 1,
        "event_match_total": 1,
        "core_trust_hits": 4,
        "core_trust_total": 4,
    }
