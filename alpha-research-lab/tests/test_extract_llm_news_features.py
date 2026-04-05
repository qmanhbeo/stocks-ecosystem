from __future__ import annotations

import json
import urllib.error

from data_tools import extract_llm_news_features as llm


def _write_jsonl(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_stats(path, models: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": "2026-04-04T00:00:00Z",
        "models": models,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


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


def test_parse_openai_chat_array_accepts_single_object_content() -> None:
    body = {
        "choices": [
            {
                "message": {
                    "content": '{"id":"2026-03-13_0001","tickers":["FPT"],"sentiment":1}'
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


def test_resolve_provider_api_keys_read_repo_env(monkeypatch, tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                'GOOGLE_API_KEY="g-key"',
                'NVIDIA_API_KEY="nv-key"',
                'MISTRAL_API_KEY="m-key"',
                'MISTRAL_COSTRAL_API_KEY="codestral-key"',
                'HUGGINGFACE_FINEGRAINED="hf-key"',
                'BASETEN_GLM_47_API_KEY="baseten-glm-key"',
                'BASETEN_NEMOTRON_API_KEY="baseten-nemotron-key"',
                'CEREBRAS_API_KEY="cerebras-key"',
                'FIREWORKS_API_KEY="fireworks-key"',
                'GROQ_API_KEY="groq-key"',
                'OPENCODE_ZEN_API_KEY="opencode-key"',
                'VERCEL_AI_GATEWAY_API_KEY="vercel-key"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm, "REPO_ROOT", tmp_path)
    for env_name in [
        "GOOGLE_API_KEY",
        "NVIDIA_API_KEY",
        "NGC_API_KEY",
        "MISTRAL_API_KEY",
        "MISTRAL_COSTRAL_API_KEY",
        "MISTRAL_CODESTRAL_API_KEY",
        "HUGGINGFACE_FINEGRAINED",
        "HF_TOKEN",
        "HUGGINGFACEHUB_API_TOKEN",
        "BASETEN_GLM_47_API_KEY",
        "BASETEN_NEMOTRON_API_KEY",
        "BASETEN_API_KEY",
        "CEREBRAS_API_KEY",
        "FIREWORKS_API_KEY",
        "GROQ_API_KEY",
        "OPENCODE_ZEN_API_KEY",
        "OPENCODE_API_KEY",
        "VERCEL_AI_GATEWAY_API_KEY",
        "AI_GATEWAY_API_KEY",
        "VERCEL_OIDC_TOKEN",
    ]:
        monkeypatch.delenv(env_name, raising=False)

    assert llm._resolve_google_api_key("") == "g-key"
    assert llm._resolve_nvidia_api_key("") == "nv-key"
    assert llm._resolve_mistral_api_key("") == "m-key"
    assert llm._resolve_mistral_api_key("", model_name="codestral-latest") == "codestral-key"
    assert llm._resolve_huggingface_api_key("") == "hf-key"
    assert llm._resolve_provider_api_key("baseten", model_name="zai-org/GLM-4.7") == "baseten-glm-key"
    assert llm._resolve_provider_api_key("baseten", model_name="nvidia/nemotron-mini-4b-instruct") == "baseten-nemotron-key"
    assert llm._resolve_provider_api_key("cerebras") == "cerebras-key"
    assert llm._resolve_provider_api_key("fireworks") == "fireworks-key"
    assert llm._resolve_provider_api_key("groq") == "groq-key"
    assert llm._resolve_provider_api_key("opencode") == "opencode-key"
    assert llm._resolve_vercel_api_key("") == "vercel-key"


def test_hosted_scheduler_skips_model_on_cooldown(tmp_path) -> None:
    stats_path = tmp_path / "stats.json"
    limiter = llm.HostedModelScheduler(
        [
            llm.HostedModelSpec(provider="google", name="model_a", api_key_envs=()),
            llm.HostedModelSpec(provider="nvidia", name="model_b", api_key_envs=()),
        ],
        stats_path=stats_path,
    )

    assert limiter.acquire(acquire_timeout=0.01) == "model_a"
    limiter.cooldown("google:model_a", 60.0)

    assert limiter.acquire(acquire_timeout=0.01) == "model_b"


def test_hosted_scheduler_prefers_fastest_model_from_saved_stats(tmp_path) -> None:
    stats_path = tmp_path / "stats.json"
    _write_stats(
        stats_path,
        {
            "google:slow-model": {
                "success_count": 3,
                "failure_count": 0,
                "failure_streak": 0,
                "recent_latencies": [9.0, 10.0],
            },
            "nvidia:fast-model": {
                "success_count": 4,
                "failure_count": 0,
                "failure_streak": 0,
                "recent_latencies": [1.5, 1.8],
            },
        },
    )
    limiter = llm.HostedModelScheduler(
        [
            llm.HostedModelSpec(provider="google", name="slow-model", api_key_envs=()),
            llm.HostedModelSpec(provider="nvidia", name="fast-model", api_key_envs=()),
        ],
        stats_path=stats_path,
    )

    spec = limiter.acquire_spec(acquire_timeout=0.01)

    assert spec is not None
    assert spec.key == "nvidia:fast-model"

    limiter.record_success(spec.key, 1.2)
    saved = json.loads(stats_path.read_text(encoding="utf-8"))
    assert saved["models"]["nvidia:fast-model"]["success_count"] == 5


def test_select_hosted_model_pool_auto_filters_configured_providers(monkeypatch) -> None:
    def fake_resolve(provider: str, cli_value: str = "", model_name: str = "") -> str:
        return "key" if provider in {"google", "vercel"} else ""

    monkeypatch.setattr(llm, "_resolve_provider_api_key", fake_resolve)

    pool = llm._select_hosted_model_pool("auto", "")

    assert pool
    assert {spec.provider for spec in pool} == {"google", "vercel"}


def test_select_hosted_model_pool_auto_accepts_qualified_subset() -> None:
    pool = llm._select_hosted_model_pool(
        "auto",
        "google:gemini-2.5-flash-lite,nvidia:deepseek-v3.2",
    )

    assert [spec.key for spec in pool] == [
        "google:gemini-2.5-flash-lite",
        "nvidia:deepseek-ai/deepseek-v3.2",
    ]


def test_select_hosted_model_pool_auto_includes_new_hosted_providers(monkeypatch) -> None:
    allowed = {"google", "nvidia", "mistral", "huggingface", "vercel", "baseten", "cerebras", "fireworks", "groq", "opencode"}

    def fake_resolve(provider: str, cli_value: str = "", model_name: str = "") -> str:
        return "key" if provider in allowed else ""

    monkeypatch.setattr(llm, "_resolve_provider_api_key", fake_resolve)

    pool = llm._select_hosted_model_pool("auto", "")

    assert {spec.provider for spec in pool} == allowed


def test_article_enrichment_uses_published_at_and_url_only() -> None:
    article = {
        "title": "AAA cong bo ke hoach loi nhuan",
        "summary": "Doanh nghiep vuot ke hoach nam nay.",
        "body_text": "Thong tin them 15h30 va 2026.",
        "published_at": "2026-04-04T08:10:00",
        "url": "https://cafef.vn/aaa-hop-dong-moi.chn",
    }

    enriched = llm._article_enrichment(article)

    assert enriched["event_time_type"] == "pre_market"
    assert enriched["source_domain"] == "cafef.vn"
    assert enriched["article_text_length"] > 0
    assert enriched["article_has_numbers"] is True
    assert enriched["article_mentions_percent"] is False


def test_normalize_record_accepts_new_enum_fields() -> None:
    raw = {
        "id": "2026-04-04_0001",
        "tickers": ["AAA"],
        "related_tickers": ["BBB"],
        "sentiment": 1,
        "confidence": 2,
        "event_type": "contract_win",
        "magnitude": 2,
        "is_forward_looking": True,
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
    }

    norm = llm._normalize_record(raw, "fallback")

    assert norm["expectation_alignment"] == "beats"
    assert norm["information_novelty"] == "new"
    assert norm["macro_theme"] == "banking"
    assert norm["source_authority"] == "official"
    assert norm["causal_impact_label"] == "revenue_positive"


def test_normalize_record_accepts_kimi_style_label_outputs() -> None:
    raw = {
        "id": "2026-04-04_0002",
        "tickers": ["vnpt"],
        "related_tickers": [],
        "sentiment": "neutral",
        "confidence": 0.7,
        "event_type": "management_change",
        "magnitude": "low",
        "is_forward_looking": False,
        "market_tone": "neutral",
        "is_rumor": False,
        "surprise_direction": "none",
        "impact_scope": "company",
        "named_persons": ["Đặng Anh Sơn"],
        "expectation_alignment": "not_applicable",
        "information_novelty": "new",
        "macro_theme": "none",
        "source_authority": "official",
        "causal_impact_label": "none",
    }

    norm = llm._normalize_record(raw, "fallback")

    assert norm["sentiment"] == 0
    assert norm["confidence"] == 2
    assert norm["magnitude"] == 0
    assert norm["market_tone"] == 0
    assert norm["surprise_direction"] == 0
    assert norm["impact_scope"] == "stock"


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
    )

    saved_rows = [json.loads(line) for line in (cache_dir / "2026-03-13.jsonl").open(encoding="utf-8")]
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
    )

    saved_rows = [json.loads(line) for line in (cache_dir / "2026-03-14.jsonl").open(encoding="utf-8")]
    assert stats["parsed_ok"] == 1
    assert stats["parse_fail"] == 0
    assert stats["timeout_fail"] == 0
    assert saved_rows[0]["tickers"] == ["FPT"]
    assert saved_rows[0]["llm_error"] is None


def test_process_day_auto_uses_fastest_hosted_model_first(monkeypatch, tmp_path) -> None:
    raw_path = tmp_path / "raw" / "2026-03-15.jsonl"
    cache_dir = tmp_path / "cache"
    stats_path = tmp_path / "stats.json"
    _write_jsonl(
        raw_path,
        [
            {
                "title": "Co phieu FPT tang sau tin hop dong",
                "summary": "Cong ty cong bo hop dong cong nghe lon voi doi tac moi.",
                "url": "https://cafef.vn/fpt-hop-dong-tuong-lai.chn",
            }
        ],
    )
    _write_stats(
        stats_path,
        {
            "google:slow-model": {
                "success_count": 2,
                "failure_count": 0,
                "failure_streak": 0,
                "recent_latencies": [9.0, 10.0],
            },
            "nvidia:fast-model": {
                "success_count": 2,
                "failure_count": 0,
                "failure_streak": 0,
                "recent_latencies": [1.1, 1.3],
            },
        },
    )
    monkeypatch.setattr(llm, "CACHE_DIR", cache_dir)

    scheduler = llm.HostedModelScheduler(
        [
            llm.HostedModelSpec(provider="google", name="slow-model", api_key_envs=("GOOGLE_API_KEY",)),
            llm.HostedModelSpec(provider="nvidia", name="fast-model", api_key_envs=("NVIDIA_API_KEY",)),
        ],
        stats_path=stats_path,
    )
    calls: list[str] = []

    def fake_call_hosted_model(*, prompt: str, spec: llm.HostedModelSpec, api_key: str, timeout: int, max_output_tokens: int):
        calls.append(spec.key)
        assert api_key == "shared-key"
        return [
            {
                "id": "2026-03-15_0001",
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

    monkeypatch.setattr(llm, "_call_hosted_model", fake_call_hosted_model)

    stats = llm.process_day(
        raw_path,
        batch_size=1,
        provider="auto",
        model="",
        api_key="",
        timeout=30,
        num_predict=8192,
        max_summary_chars=400,
        log_every_batches=1,
        rate_limiter=scheduler,
        api_keys={
            "google:slow-model": "shared-key",
            "nvidia:fast-model": "shared-key",
        },
    )

    assert stats["parsed_ok"] == 1
    assert calls == ["nvidia:fast-model"]


def test_process_day_auto_falls_back_after_single_item_failure(monkeypatch, tmp_path) -> None:
    raw_path = tmp_path / "raw" / "2026-03-16.jsonl"
    cache_dir = tmp_path / "cache"
    stats_path = tmp_path / "stats.json"
    _write_jsonl(
        raw_path,
        [
            {
                "title": "Co phieu FPT tang sau tin hop dong",
                "summary": "Cong ty cong bo hop dong cong nghe lon voi doi tac moi.",
                "url": "https://cafef.vn/fpt-hop-dong-tuong-lai.chn",
            }
        ],
    )
    _write_stats(
        stats_path,
        {
            "google:fast-model": {
                "success_count": 2,
                "failure_count": 0,
                "failure_streak": 0,
                "recent_latencies": [1.0, 1.1],
            },
            "nvidia:backup-model": {
                "success_count": 2,
                "failure_count": 0,
                "failure_streak": 0,
                "recent_latencies": [2.0, 2.2],
            },
        },
    )
    monkeypatch.setattr(llm, "CACHE_DIR", cache_dir)
    scheduler = llm.HostedModelScheduler(
        [
            llm.HostedModelSpec(provider="google", name="fast-model", api_key_envs=("GOOGLE_API_KEY",)),
            llm.HostedModelSpec(provider="nvidia", name="backup-model", api_key_envs=("NVIDIA_API_KEY",)),
        ],
        stats_path=stats_path,
    )
    calls: list[str] = []

    def fake_call_hosted_model(*, prompt: str, spec: llm.HostedModelSpec, api_key: str, timeout: int, max_output_tokens: int):
        calls.append(spec.key)
        if spec.key == "google:fast-model":
            raise TimeoutError("timed out")
        return [
            {
                "id": "2026-03-16_0001",
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

    monkeypatch.setattr(llm, "_call_hosted_model", fake_call_hosted_model)

    stats = llm.process_day(
        raw_path,
        batch_size=1,
        provider="auto",
        model="",
        api_key="",
        timeout=30,
        num_predict=8192,
        max_summary_chars=400,
        log_every_batches=1,
        rate_limiter=scheduler,
        api_keys={
            "google:fast-model": "shared-key",
            "nvidia:backup-model": "shared-key",
        },
    )

    assert stats["parsed_ok"] == 1
    assert calls == ["google:fast-model", "nvidia:backup-model"]


def test_process_day_auto_falls_back_after_429(monkeypatch, tmp_path) -> None:
    raw_path = tmp_path / "raw" / "2026-03-17.jsonl"
    cache_dir = tmp_path / "cache"
    stats_path = tmp_path / "stats.json"
    _write_jsonl(
        raw_path,
        [
            {
                "title": "Co phieu FPT tang sau tin hop dong",
                "summary": "Cong ty cong bo hop dong cong nghe lon voi doi tac moi.",
                "url": "https://cafef.vn/fpt-hop-dong-tuong-lai.chn",
            }
        ],
    )
    _write_stats(
        stats_path,
        {
            "google:fast-model": {
                "success_count": 2,
                "failure_count": 0,
                "failure_streak": 0,
                "recent_latencies": [1.0, 1.1],
            },
            "nvidia:backup-model": {
                "success_count": 2,
                "failure_count": 0,
                "failure_streak": 0,
                "recent_latencies": [2.0, 2.2],
            },
        },
    )
    monkeypatch.setattr(llm, "CACHE_DIR", cache_dir)
    scheduler = llm.HostedModelScheduler(
        [
            llm.HostedModelSpec(provider="google", name="fast-model", api_key_envs=("GOOGLE_API_KEY",)),
            llm.HostedModelSpec(provider="nvidia", name="backup-model", api_key_envs=("NVIDIA_API_KEY",)),
        ],
        stats_path=stats_path,
    )
    calls: list[str] = []

    def fake_call_hosted_model(*, prompt: str, spec: llm.HostedModelSpec, api_key: str, timeout: int, max_output_tokens: int):
        calls.append(spec.key)
        if spec.key == "google:fast-model":
            raise urllib.error.HTTPError(
                url="https://example.com",
                code=429,
                msg="Too Many Requests",
                hdrs=None,
                fp=None,
            )
        return [
            {
                "id": "2026-03-17_0001",
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

    monkeypatch.setattr(llm, "_call_hosted_model", fake_call_hosted_model)

    stats = llm.process_day(
        raw_path,
        batch_size=1,
        provider="auto",
        model="",
        api_key="",
        timeout=30,
        num_predict=8192,
        max_summary_chars=400,
        log_every_batches=1,
        rate_limiter=scheduler,
        api_keys={
            "google:fast-model": "shared-key",
            "nvidia:backup-model": "shared-key",
        },
    )

    assert stats["parsed_ok"] == 1
    assert calls == ["google:fast-model", "nvidia:backup-model"]
