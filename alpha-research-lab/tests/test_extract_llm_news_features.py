from __future__ import annotations

import json

from data_tools import extract_llm_news_features as llm


def _write_jsonl(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_parse_google_array_joins_all_text_parts() -> None:
    body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": '[{"id":"2026-03-13_0001","tickers":["FPT"],'},
                        {'text': '"sentiment":1,"confidence":2,"event_type":"contract_win"}]'},
                    ]
                }
            }
        ]
    }

    arr = llm._parse_google_array(body, use_json_mode=True)

    assert arr == [
        {
            "id": "2026-03-13_0001",
            "tickers": ["FPT"],
            "sentiment": 1,
            "confidence": 2,
            "event_type": "contract_win",
        }
    ]


def test_parse_openai_chat_array_reads_message_content() -> None:
    body = {
        "choices": [
            {
                "message": {
                    "content": '[{"id":"2026-03-13_0001","tickers":["FPT"],"sentiment":1}]'
                }
            }
        ]
    }

    arr = llm._parse_openai_chat_array(body)

    assert arr == [{"id": "2026-03-13_0001", "tickers": ["FPT"], "sentiment": 1}]


def test_cache_has_successful_rows_rejects_error_only_cache(tmp_path) -> None:
    cache_path = tmp_path / "2026-03-13.jsonl"
    _write_jsonl(
        cache_path,
        [
            {"id": "2026-03-13_0001", "llm_error": "ollama_timeout_or_error"},
            {"id": "2026-03-13_0002", "llm_error": "json_parse_fail"},
        ],
    )

    assert llm._cache_has_successful_rows(cache_path) is False

    _write_jsonl(
        cache_path,
        [
            {"id": "2026-03-13_0001", "llm_error": "json_parse_fail"},
            {"id": "2026-03-13_0002", "llm_error": None, "tickers": ["FPT"]},
        ],
    )

    assert llm._cache_has_successful_rows(cache_path) is True


def test_resolve_google_api_key_reads_repo_env(monkeypatch, tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text('GOOGLE_API_KEY="abc123"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    api_key = llm._resolve_google_api_key("")

    assert api_key == "abc123"


def test_resolve_nvidia_api_key_reads_repo_env(monkeypatch, tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text('NVIDIA_API_KEY="nv-key"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NGC_API_KEY", raising=False)

    api_key = llm._resolve_nvidia_api_key("")

    assert api_key == "nv-key"


def test_model_rate_limiter_skips_model_on_cooldown() -> None:
    limiter = llm.ModelRateLimiter(
        [
            {"name": "model_a", "rpm": 5, "rpd": 5},
            {"name": "model_b", "rpm": 5, "rpd": 5},
        ]
    )

    assert limiter.acquire(acquire_timeout=0.01) == "model_a"
    limiter.cooldown("model_a", 60.0)

    assert limiter.acquire(acquire_timeout=0.01) == "model_b"


def test_model_rate_limiter_supports_unbounded_model_pool() -> None:
    limiter = llm.ModelRateLimiter(
        [
            {"name": "model_a"},
            {"name": "model_b"},
        ]
    )

    assert limiter.acquire(acquire_timeout=0.01) == "model_a"
    limiter.cooldown("model_a", 60.0)
    assert limiter.acquire(acquire_timeout=0.01) == "model_b"


def test_process_day_retries_smaller_google_batches(monkeypatch, tmp_path) -> None:
    raw_path = tmp_path / "raw" / "2026-03-13.jsonl"
    cache_dir = tmp_path / "cache"
    _write_jsonl(
        raw_path,
        [
            {
                "title": "Co phieu FPT tang manh sau hop dong moi",
                "summary": "Doanh nghiep cong bo hop dong CNTT gia tri lon.",
                "url": "https://cafef.vn/fpt-hop-dong-moi.chn",
            },
            {
                "title": "Co phieu VCB duoc ho tro boi loi nhuan tang truong",
                "summary": "Ngan hang ghi nhan loi nhuan vuot ky vong.",
                "url": "https://cafef.vn/vcb-loi-nhuan.chn",
            },
        ],
    )
    monkeypatch.setattr(llm, "CACHE_DIR", cache_dir)

    def fake_call_google(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int):
        assert model == "gemini-2.5-flash-lite"
        if "2026-03-13_0001" in prompt and "2026-03-13_0002" in prompt:
            return []
        if "2026-03-13_0001" in prompt:
            return [
                {
                    "id": "2026-03-13_0001",
                    "tickers": ["FPT"],
                    "related_tickers": [],
                    "sentiment": 1,
                    "confidence": 2,
                    "event_type": "contract_win",
                    "magnitude": 2,
                    "is_forward_looking": True,
                    "market_tone": 1,
                    "is_rumor": False,
                    "surprise_direction": 1,
                    "impact_scope": "stock",
                    "named_persons": [],
                }
            ]
        return [
            {
                "id": "2026-03-13_0002",
                "tickers": ["VCB"],
                "related_tickers": [],
                "sentiment": 1,
                "confidence": 1,
                "event_type": "earnings_beat",
                "magnitude": 1,
                "is_forward_looking": False,
                "market_tone": 1,
                "is_rumor": False,
                "surprise_direction": 1,
                "impact_scope": "stock",
                "named_persons": [],
            }
        ]

    monkeypatch.setattr(llm, "_call_google", fake_call_google)

    stats = llm.process_day(
        raw_path,
        batch_size=2,
        provider="google",
        model="gemini-2.5-flash-lite",
        api_key="test-key",
        timeout=30,
        num_predict=8192,
        max_summary_chars=400,
        log_every_batches=1,
        rate_limiter=None,
    )

    saved_rows = [json.loads(line) for line in (cache_dir / "2026-03-13.jsonl").open()]
    assert stats["parsed_ok"] == 2
    assert stats["parse_fail"] == 0
    assert stats["timeout_fail"] == 0
    assert [row["id"] for row in saved_rows] == ["2026-03-13_0001", "2026-03-13_0002"]
    assert all(row["llm_error"] is None for row in saved_rows)


def test_process_day_supports_nvidia_provider(monkeypatch, tmp_path) -> None:
    raw_path = tmp_path / "raw" / "2026-03-14.jsonl"
    cache_dir = tmp_path / "cache"
    _write_jsonl(
        raw_path,
        [
            {
                "title": "Co phieu FPT ky hop dong lon",
                "summary": "Doanh nghiep cong bo hop dong moi voi doi tac nuoc ngoai.",
                "url": "https://cafef.vn/fpt-hop-dong.chn",
            }
        ],
    )
    monkeypatch.setattr(llm, "CACHE_DIR", cache_dir)

    def fake_call_nvidia(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int):
        assert model == "moonshotai/kimi-k2-instruct"
        assert api_key == "nv-key"
        return [
            {
                "id": "2026-03-14_0001",
                "tickers": ["FPT"],
                "related_tickers": [],
                "sentiment": 1,
                "confidence": 2,
                "event_type": "contract_win",
                "magnitude": 2,
                "is_forward_looking": True,
                "market_tone": 1,
                "is_rumor": False,
                "surprise_direction": 1,
                "impact_scope": "stock",
                "named_persons": [],
            }
        ]

    monkeypatch.setattr(llm, "_call_nvidia", fake_call_nvidia)

    stats = llm.process_day(
        raw_path,
        batch_size=1,
        provider="nvidia",
        model="moonshotai/kimi-k2-instruct",
        api_key="nv-key",
        timeout=30,
        num_predict=8192,
        max_summary_chars=400,
        log_every_batches=1,
        rate_limiter=None,
    )

    saved_rows = [json.loads(line) for line in (cache_dir / "2026-03-14.jsonl").open()]
    assert stats["parsed_ok"] == 1
    assert stats["parse_fail"] == 0
    assert stats["timeout_fail"] == 0
    assert saved_rows[0]["tickers"] == ["FPT"]
    assert saved_rows[0]["llm_error"] is None
