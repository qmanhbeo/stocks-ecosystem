from __future__ import annotations

import json
import re
import sys
import threading
import time
import urllib.error
from datetime import datetime, timezone

from data_tools import extract_llm_news_features as llm
from data_tools import extract_llm_news_features_legacy as legacy


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


def test_utc_timestamp_helper_returns_z_suffixed_utc() -> None:
    ts = llm._utc_now_iso_z()

    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))

    assert ts.endswith("Z")
    assert parsed.tzinfo == timezone.utc


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


def test_parse_openai_chat_array_accepts_nested_content_text() -> None:
    body = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": '[{"id":"2026-03-13_0001",'},
                        {"type": "text", "text": '"tickers":["FPT"],"sentiment":1}]'},
                    ]
                }
            }
        ]
    }

    arr = llm._parse_openai_chat_array(body)

    assert arr == [{"id": "2026-03-13_0001", "tickers": ["FPT"], "sentiment": 1}]


def test_parse_openai_chat_array_ignores_bracket_noise() -> None:
    body = {
        "choices": [
            {
                "message": {
                    "content": 'note [ignore me] then [{"id":"2026-03-13_0001","tickers":["FPT"],"sentiment":1}] after'
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
                'GOOGLE_API_KEY_2="g-key-2"',
                'GOOGLE_API_KEY_3="g-key-3"',
                'GOOGLE_API_KEY_5="g-key-5"',
                'NVIDIA_API_KEY="nv-key"',
                'MISTRAL_API_KEY="m-key"',
                'MISTRAL_COSTRAL_API_KEY="codestral-key"',
                'HUGGINGFACE_FINEGRAINED="hf-key"',
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
        "GOOGLE_API_KEY_2",
        "GOOGLE_API_KEY_3",
        "GOOGLE_API_KEY_4",
        "GOOGLE_API_KEY_5",
        "GOOGLE_API_KEYS",
        "NVIDIA_API_KEY",
        "NGC_API_KEY",
        "MISTRAL_API_KEY",
        "MISTRAL_COSTRAL_API_KEY",
        "MISTRAL_CODESTRAL_API_KEY",
        "HUGGINGFACE_FINEGRAINED",
        "HF_TOKEN",
        "HUGGINGFACEHUB_API_TOKEN",
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
    assert llm._resolve_google_api_keys("") == ["g-key", "g-key-2", "g-key-3", "g-key-5"]
    assert llm._resolve_nvidia_api_key("") == "nv-key"
    assert llm._resolve_mistral_api_key("") == "m-key"
    assert llm._resolve_mistral_api_key("", model_name="codestral-latest") == "codestral-key"
    assert llm._resolve_huggingface_api_key("") == "hf-key"
    assert "baseten" not in llm.HOSTED_PROVIDERS
    assert "baseten" not in llm.HOSTED_PROVIDER_NAMES
    assert llm._resolve_provider_api_key("baseten", model_name="zai-org/GLM-4.7") == ""
    assert llm._resolve_provider_api_key("cerebras") == "cerebras-key"
    assert llm._resolve_provider_api_key("fireworks") == "fireworks-key"
    assert llm._resolve_provider_api_key("groq") == "groq-key"
    assert llm._resolve_provider_api_key("opencode") == "opencode-key"
    assert llm._resolve_vercel_api_key("") == "vercel-key"


def test_opencode_pool_uses_free_zen_models() -> None:
    assert [cfg["name"] for cfg in llm.OPENCODE_MODEL_POOL] == [
        "opencode/big-pickle",
        "opencode/qwen3.6-plus-free",
        "opencode/nemotron-3-super-free",
        "opencode/minimax-m2.5-free",
    ]


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


def test_hosted_scheduler_reserves_provider_during_inflight(tmp_path) -> None:
    stats_path = tmp_path / "stats.json"
    limiter = llm.HostedModelScheduler(
        [
            llm.HostedModelSpec(provider="google", name="model_a", api_key_envs=()),
            llm.HostedModelSpec(provider="google", name="model_b", api_key_envs=()),
            llm.HostedModelSpec(provider="nvidia", name="model_c", api_key_envs=()),
        ],
        stats_path=stats_path,
    )

    first = limiter.acquire_spec(acquire_timeout=0.01)
    second = limiter.acquire_spec(acquire_timeout=0.01)

    assert first is not None
    assert first.provider == "google"
    assert second is not None
    assert second.provider == "nvidia"

    limiter.record_success(first.key, 0.5)
    limiter.record_success(second.key, 0.5)


def test_hosted_scheduler_cools_provider_after_429(tmp_path) -> None:
    stats_path = tmp_path / "stats.json"
    limiter = llm.HostedModelScheduler(
        [
            llm.HostedModelSpec(provider="nvidia", name="fast-model", api_key_envs=()),
            llm.HostedModelSpec(provider="nvidia", name="backup-model", api_key_envs=()),
            llm.HostedModelSpec(provider="google", name="fallback-model", api_key_envs=()),
        ],
        stats_path=stats_path,
    )

    first = limiter.acquire_spec(acquire_timeout=0.01)
    assert first is not None
    assert first.provider == "nvidia"

    limiter.record_failure(first.key, cooldown_seconds=60.0, provider_cooldown_seconds=900.0)

    second = limiter.acquire_spec(acquire_timeout=0.01)
    assert second is not None
    assert second.provider == "google"


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


def test_hosted_scheduler_prefers_stable_tier_over_fallback(tmp_path) -> None:
    stats_path = tmp_path / "stats.json"
    limiter = llm.HostedModelScheduler(
        [
            llm.HostedModelSpec(provider="google", name="stable-model", api_key_envs=(), seed_latency=10.0, priority_tier=0),
            llm.HostedModelSpec(provider="fireworks", name="fallback-model", api_key_envs=(), seed_latency=1.0, priority_tier=1),
        ],
        stats_path=stats_path,
    )

    first = limiter.acquire_spec(acquire_timeout=0.01)
    assert first is not None
    assert first.provider == "google"

    limiter.record_success(first.key, 1.0)
    limiter.cooldown(first.key, 60.0)

    second = limiter.acquire_spec(acquire_timeout=0.01)
    assert second is not None
    assert second.provider == "fireworks"


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
        "nvidia:deepseek-ai/deepseek-v3_2",
    ]


def test_select_hosted_model_pool_auto_includes_configured_providers(monkeypatch) -> None:
    allowed = {"google", "nvidia", "huggingface", "vercel", "cerebras", "groq", "opencode"}

    def fake_resolve(provider: str, cli_value: str = "", model_name: str = "") -> str:
        return "key" if provider in allowed else ""

    monkeypatch.setattr(llm, "_resolve_provider_api_key", fake_resolve)

    pool = llm._select_hosted_model_pool("auto", "")

    assert pool
    assert {spec.provider for spec in pool} == allowed


def test_select_hosted_model_pool_huggingface_uses_router_models() -> None:
    pool = llm._select_hosted_model_pool("huggingface", "")

    assert pool
    assert {spec.provider for spec in pool} == {"huggingface"}
    assert [spec.name for spec in pool] == [
        "meta-llama/Llama-3.1-8B-Instruct:cerebras",
        "CohereLabs/tiny-aya-global:cohere",
        "meta-llama/Llama-3.1-8B-Instruct:featherless-ai",
        "zai-org/GLM-5:fireworks-ai",
        "meta-llama/Llama-3.1-8B-Instruct:groq",
        "google/gemma-2-2b-it:hf-inference",
        "deepseek-ai/DeepSeek-R1:hyperbolic",
        "moonshotai/Kimi-K2-Thinking:novita",
        "meta-llama/Llama-3.1-8B-Instruct:nscale",
        "meta-llama/Llama-3.1-8B-Instruct:ovhcloud",
        "allenai/Olmo-3.1-32B-Think:publicai",
        "deepseek-ai/DeepSeek-R1:sambanova",
        "meta-llama/Llama-3.1-8B-Instruct:scaleway",
        "zai-org/GLM-5:together",
        "zai-org/GLM-5:zai-org",
    ]


def test_vercel_and_nvidia_pools_use_current_model_slugs() -> None:
    vercel_names = [cfg["name"] for cfg in llm.VERCEL_MODEL_POOL]
    nvidia_names = [cfg["name"] for cfg in llm.NVIDIA_MODEL_POOL]

    assert "deepseek/deepseek-v3.2" in vercel_names
    assert "mistral/mistral-large-3" in vercel_names
    assert "moonshotai/kimi-k2.5" in vercel_names
    assert "moonshotai/kimi-k2.5" in nvidia_names
    assert "google/gemma-4-31b-it" in nvidia_names
    assert "nvidia/nemotron-3-super-120b-a12b" in nvidia_names
    assert "minimax-ai/minimax-m25" in nvidia_names
    assert "deepseek-ai/deepseek-v3_2" in nvidia_names


def test_nvidia_aliases_include_minimax_m25() -> None:
    assert llm._normalize_nvidia_model_name("minimax-m2.5") == "minimax-ai/minimax-m25"


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


def test_process_day_rotates_google_keys_after_429(monkeypatch, tmp_path, capsys) -> None:
    raw_path = tmp_path / "raw" / "2026-03-19.jsonl"
    cache_dir = tmp_path / "cache"
    _write_jsonl(
        raw_path,
        [
            {
                "title": "Co phieu FPT tang sau hop dong moi",
                "summary": "Doanh nghiep cong bo hop dong CNTT gia tri lon.",
                "url": "https://cafef.vn/fpt-hop-dong-moi.chn",
            }
        ],
    )
    monkeypatch.setattr(llm, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(llm, "HOSTED_MODEL_STATS_PATH", tmp_path / "stats.json")

    calls: list[tuple[str, str]] = []

    def fake_call_google(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int):
        calls.append((model, api_key))
        if api_key == "g-key":
            raise urllib.error.HTTPError(
                url="https://example.com",
                code=429,
                msg="Too Many Requests",
                hdrs=None,
                fp=None,
            )
        return [
            {
                "id": "2026-03-19_0001",
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

    monkeypatch.setattr(llm, "_call_google", fake_call_google)

    stats = llm.process_day(
        raw_path,
        batch_size=1,
        provider="google",
        model="gemini-2.5-flash-lite,gemini-2.5-flash",
        api_key="g-key,g-key-2",
        timeout=30,
        num_predict=8192,
        max_summary_chars=400,
        log_every_batches=1,
    )

    output = capsys.readouterr().out
    assert stats["parsed_ok"] == 1
    assert calls == [
        ("gemini-2.5-flash-lite", "g-key"),
        ("gemini-2.5-flash", "g-key-2"),
    ]
    assert "api_key=1st/2" in output
    assert "api_key=2nd/2" in output


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
    monkeypatch.setattr(legacy, "CACHE_DIR", cache_dir)

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

    monkeypatch.setattr(legacy, "_call_nvidia", fake_call_nvidia)

    stats = legacy.process_day(
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
    monkeypatch.setattr(legacy, "CACHE_DIR", cache_dir)

    scheduler = legacy.HostedModelScheduler(
        [
            legacy.HostedModelSpec(provider="google", name="slow-model", api_key_envs=("GOOGLE_API_KEY",)),
            legacy.HostedModelSpec(provider="nvidia", name="fast-model", api_key_envs=("NVIDIA_API_KEY",)),
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

    monkeypatch.setattr(legacy, "_call_hosted_model", fake_call_hosted_model)

    stats = legacy.process_day(
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
    monkeypatch.setattr(legacy, "CACHE_DIR", cache_dir)
    scheduler = legacy.HostedModelScheduler(
        [
            legacy.HostedModelSpec(provider="google", name="fast-model", api_key_envs=("GOOGLE_API_KEY",)),
            legacy.HostedModelSpec(provider="nvidia", name="backup-model", api_key_envs=("NVIDIA_API_KEY",)),
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

    monkeypatch.setattr(legacy, "_call_hosted_model", fake_call_hosted_model)

    stats = legacy.process_day(
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
    monkeypatch.setattr(legacy, "CACHE_DIR", cache_dir)
    scheduler = legacy.HostedModelScheduler(
        [
            legacy.HostedModelSpec(provider="google", name="fast-model", api_key_envs=("GOOGLE_API_KEY",)),
            legacy.HostedModelSpec(provider="nvidia", name="backup-model", api_key_envs=("NVIDIA_API_KEY",)),
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

    monkeypatch.setattr(legacy, "_call_hosted_model", fake_call_hosted_model)

    stats = legacy.process_day(
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


def test_process_day_uses_batch_workers_within_day(monkeypatch, tmp_path) -> None:
    raw_path = tmp_path / "raw" / "2026-03-18.jsonl"
    cache_dir = tmp_path / "cache"
    _write_jsonl(
        raw_path,
        [
            {
                "title": "Co phieu FPT tang sau hop dong moi",
                "summary": "Doanh nghiep cong bo hop dong CNTT gia tri lon.",
                "url": "https://cafef.vn/fpt-hop-dong-moi.chn",
            },
            {
                "title": "Co phieu VCB duoc ho tro boi loi nhuan tang truong",
                "summary": "Ngan hang ghi nhan loi nhuan vuot ky vong.",
                "url": "https://cafef.vn/vcb-loi-nhuan.chn",
            },
            {
                "title": "Co phieu HPG co dong luc tang gia",
                "summary": "Doanh nghiep thep duoc ho tro boi cau chuyen san xuat.",
                "url": "https://cafef.vn/hpg-tang-gia.chn",
            },
            {
                "title": "Co phieu SSI doi mat bien dong",
                "summary": "Cong ty chung khoan cap nhat tin moi ve thi truong.",
                "url": "https://cafef.vn/ssi-bien-dong.chn",
            },
        ],
    )
    monkeypatch.setattr(legacy, "CACHE_DIR", cache_dir)

    inflight = 0
    max_inflight = 0
    lock = threading.Lock()

    def fake_call_ollama(prompt: str, model: str, timeout: int, num_predict: int) -> str:
        nonlocal inflight, max_inflight
        match = re.search(r"\d{4}-\d{2}-\d{2}_\d{4}", prompt)
        assert match is not None
        rid = match.group(0)
        with lock:
            inflight += 1
            max_inflight = max(max_inflight, inflight)
        time.sleep(0.1)
        with lock:
            inflight -= 1
        return json.dumps(
            [
                {
                    "id": rid,
                    "tickers": ["FPT"],
                    "sentiment": 1,
                    "confidence": 1,
                    "event_type": "contract_win",
                    "impact_scope": "stock",
                }
            ]
        )

    monkeypatch.setattr(legacy, "_call_ollama", fake_call_ollama)

    stats = legacy.process_day(
        raw_path,
        batch_size=1,
        workers=2,
        provider="ollama",
        model="qwen3.5:4b",
        api_key="",
        timeout=30,
        num_predict=256,
        max_summary_chars=400,
        log_every_batches=1,
    )

    saved_rows = [json.loads(line) for line in (cache_dir / "2026-03-18.jsonl").open(encoding="utf-8")]
    assert stats["parsed_ok"] == 4
    assert max_inflight == 2
    assert [row["id"] for row in saved_rows] == [
        "2026-03-18_0001",
        "2026-03-18_0002",
        "2026-03-18_0003",
        "2026-03-18_0004",
    ]


def test_main_processes_days_serially(monkeypatch, tmp_path) -> None:
    cache_dir = tmp_path / "cache"
    days = [tmp_path / "2026-03-18.jsonl", tmp_path / "2026-03-19.jsonl"]
    monkeypatch.setattr(llm, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(llm, "_iter_dates", lambda date_from, date_to: days)

    inflight = 0
    max_inflight = 0
    seen: list[str] = []
    lock = threading.Lock()

    def fake_process_day(path, **kwargs):
        nonlocal inflight, max_inflight
        with lock:
            inflight += 1
            max_inflight = max(max_inflight, inflight)
        time.sleep(0.1)
        with lock:
            inflight -= 1
        seen.append(path.stem)
        return {
            "date": path.stem,
            "articles_total": 1,
            "articles_filtered": 1,
            "parsed_ok": 1,
            "parse_fail": 0,
            "timeout_fail": 0,
            "pool_exhausted": False,
            "out_path": str(cache_dir / f"{path.stem}.jsonl"),
            "elapsed_sec": 0.1,
        }

    monkeypatch.setattr(llm, "process_day", fake_process_day)
    monkeypatch.setattr(llm, "_resolve_google_api_key", lambda cli_value: "test-key")
    monkeypatch.setattr(sys, "argv", [
        "extract_llm_news_features.py",
        "--provider",
        "google",
        "--workers",
        "2",
        "--date-from",
        "2026-03-18",
        "--date-to",
        "2026-03-19",
    ])

    llm.main()

    assert max_inflight == 1
    assert seen == ["2026-03-18", "2026-03-19"]


def test_google_scheduler_applies_cooldown_for_403(tmp_path) -> None:
    """A 403 (auth failure, cooldown=21600s) must apply a model-level cooldown
    even though provider_cooldown_seconds=0 and 21600 is not in the legacy
    rate-limit set {180, 300, 900}.  Bug: the old code gated both model and key
    cooldown behind `should_rotate_key`, so 403s were silently swallowed."""
    import urllib.error

    stats_path = tmp_path / "stats.json"
    specs = [
        llm.HostedModelSpec(provider="google", name="model_a", api_key_envs=(), rpm=10, seed_latency=2.0),
        llm.HostedModelSpec(provider="google", name="model_b", api_key_envs=(), rpm=10, seed_latency=3.0),
    ]
    api_keys = {specs[0].key: "key1", specs[1].key: "key1"}
    scheduler = llm.GoogleKeyRotationScheduler(specs, api_keys, stats_path=stats_path)

    spec = scheduler.acquire_spec(acquire_timeout=0.1)
    assert spec is not None

    # Simulate 403: cooldown_seconds=21600, provider_cooldown_seconds=0
    scheduler.record_failure(spec.key, cooldown_seconds=21600.0, provider_cooldown_seconds=0.0)

    # model_a should now be on a long cooldown; only model_b available
    next_spec = scheduler.acquire_spec(acquire_timeout=0.1)
    assert next_spec is not None
    assert next_spec.key != spec.key, "403 should have cooled model_a, forcing fallback to model_b"


def test_google_scheduler_persists_api_key_cooldowns_with_fingerprints(tmp_path) -> None:
    stats_path = tmp_path / "stats.json"
    specs = [
        llm.HostedModelSpec(provider="google", name="model_a", api_key_envs=(), rpm=10, seed_latency=2.0),
    ]
    api_keys = {specs[0].key: "secret-key-1"}
    scheduler = llm.GoogleKeyRotationScheduler(specs, api_keys, stats_path=stats_path)

    scheduler.record_failure(specs[0].key, cooldown_seconds=300.0, provider_cooldown_seconds=300.0)

    saved = json.loads(stats_path.read_text(encoding="utf-8"))
    persisted = saved.get("api_key_cooldowns", {})
    fingerprint = scheduler._api_key_fingerprint("secret-key-1")

    assert "secret-key-1" not in persisted
    assert fingerprint in persisted
    assert float(persisted[fingerprint]) > time.time()


def test_google_scheduler_loads_legacy_raw_key_cooldowns(tmp_path) -> None:
    stats_path = tmp_path / "stats.json"
    cooldown_until = time.time() + 60.0
    stats_path.write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-04-08T00:00:00Z",
                "api_key_cooldowns": {"legacy-raw-key": cooldown_until},
                "models": {},
            }
        ),
        encoding="utf-8",
    )
    specs = [
        llm.HostedModelSpec(provider="google", name="model_a", api_key_envs=(), rpm=10, seed_latency=2.0),
    ]
    api_keys = {specs[0].key: "legacy-raw-key"}

    scheduler = llm.GoogleKeyRotationScheduler(specs, api_keys, stats_path=stats_path)

    assert scheduler._api_key_cooldown_until["legacy-raw-key"] == cooldown_until


def test_google_scheduler_excludes_high_streak_models(tmp_path) -> None:
    """Models with failure_streak >= HIGH_STREAK_THRESHOLD must be excluded from
    selection so workers wait cheaply rather than burning 30 s on a doomed timeout."""
    stats_path = tmp_path / "stats.json"
    _write_stats(
        stats_path,
        {
            "google:bad-model": {
                "success_count": 0,
                "failure_count": 14,
                "failure_streak": 14,
                "recent_latencies": [],
            }
        },
    )
    specs = [
        llm.HostedModelSpec(provider="google", name="bad-model", api_key_envs=(), rpm=30, seed_latency=2.0),
        llm.HostedModelSpec(provider="google", name="good-model", api_key_envs=(), rpm=30, seed_latency=5.0),
    ]
    api_keys = {s.key: "key1" for s in specs}
    scheduler = llm.GoogleKeyRotationScheduler(specs, api_keys, stats_path=stats_path)

    # Should pick good-model despite its higher seed_latency, because bad-model is streak-excluded
    spec = scheduler.acquire_spec(acquire_timeout=0.1)
    assert spec is not None
    assert spec.key == "google:good-model", "High-streak model must be skipped"


def test_expand_google_specs_across_keys_fans_out_single_healthy_model(tmp_path) -> None:
    stats_path = tmp_path / "stats.json"
    _write_stats(
        stats_path,
        {
            "google:gemini-2.5-flash-lite": {
                "success_count": 61,
                "failure_count": 32,
                "failure_streak": 12,
                "recent_latencies": [1.2, 1.4],
            },
            "google:gemini-3.1-flash-lite-preview": {
                "success_count": 1267,
                "failure_count": 78,
                "failure_streak": 0,
                "recent_latencies": [16.0, 18.0],
            },
        },
    )
    specs = [
        llm.HostedModelSpec(provider="google", name="gemini-2.5-flash-lite", api_key_envs=(), rpm=10),
        llm.HostedModelSpec(provider="google", name="gemini-3.1-flash-lite-preview", api_key_envs=(), rpm=15),
    ]

    expanded, api_keys = llm._expand_google_specs_across_keys(
        specs,
        ["key-1", "key-2", "key-3"],
        stats_path=stats_path,
    )

    expanded_keys = [spec.key for spec in expanded]

    assert "google:gemini-2.5-flash-lite" in expanded_keys
    assert expanded_keys.count("google:gemini-3.1-flash-lite-preview@gk1") == 1
    assert expanded_keys.count("google:gemini-3.1-flash-lite-preview@gk2") == 1
    assert expanded_keys.count("google:gemini-3.1-flash-lite-preview@gk3") == 1
    assert {
        api_keys["google:gemini-3.1-flash-lite-preview@gk1"],
        api_keys["google:gemini-3.1-flash-lite-preview@gk2"],
        api_keys["google:gemini-3.1-flash-lite-preview@gk3"],
    } == {"key-1", "key-2", "key-3"}
