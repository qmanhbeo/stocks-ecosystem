from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.deterministic_portfolio import compute_strategy_scores
from src.live_recommendation import build_live_recommendation
from src.recommendation_adapters import SignalBlendAdapter
from src.recommendation_policies import LatestLiveOverlayPolicy
from shared_recommendation.contracts import RecommendationContext, RecommendationRequest


def test_signal_blend_adapter_matches_deterministic_portfolio_scores():
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-03-27", "2026-03-27"]),
            "ticker": ["AAA", "BBB"],
            "actual": [1.0, 0.0],
            "s1_proba": [0.9, 0.1],
            "c10_illiq_level_rank": [0.2, 0.8],
            "c11_ret_60d_lag_rank": [0.7, 0.3],
            "c12_gap_absorb_3": [0.6, 0.4],
            "c13_compress_blowoff_2": [0.8, 0.2],
            "c14_clv_volconf_resid_rank": [0.5, 0.1],
        }
    )
    adapter = SignalBlendAdapter(strategy_name="recent_core")
    request = RecommendationRequest(
        profile_name="adapter_test",
        adapter=adapter,
        universe_source_key="lab_signal_matrix",
    )
    context = RecommendationContext(request=request, as_of_date=pd.Timestamp("2026-03-27"), resolved_artifacts={})

    scored = adapter.score(frame, context=context)
    expected = compute_strategy_scores(frame, {"recent_core": [
        "s1_proba",
        "c10_illiq_level_rank",
        "c11_ret_60d_lag_rank",
        "c12_gap_absorb_3",
        "c13_compress_blowoff_2",
        "c14_clv_volconf_resid_rank",
    ]})

    assert scored["score_raw"].tolist() == expected["score__recent_core"].tolist()


def test_latest_live_overlay_policy_blocks_when_activation_is_off(tmp_path):
    summary_path = tmp_path / "latest_portfolio_live_activation_overlay.json"
    summary_path.write_text(
        json.dumps(
            {
                "summary": {
                    "selector": "full_library",
                    "stale_signal_matrix": False,
                    "next_open_recommendation": {
                        "signal_date": "2026-03-27",
                        "activation_on": False,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    candidates = pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-03-27"]),
            "ticker": ["AAA"],
            "score_raw": [0.9],
        }
    )
    request = RecommendationRequest(
        profile_name="policy_test",
        adapter=SignalBlendAdapter(),
        universe_source_key="lab_signal_matrix",
    )
    context = RecommendationContext(request=request, as_of_date=pd.Timestamp("2026-03-27"), resolved_artifacts={})
    policy = LatestLiveOverlayPolicy(summary_path=summary_path, expected_selector="full_library")

    applied = policy.apply(candidates, context=context)

    assert bool(applied.loc[0, "eligible"]) is False
    assert applied.loc[0, "activation_state"] == "off"
    assert applied.loc[0, "_blocked_reasons"] == ["activation_off"]


def test_build_live_recommendation_writes_candidates(monkeypatch, tmp_path):
    matrix_path = tmp_path / "matrix.parquet"
    tradability_path = tmp_path / "tradability.parquet"
    overlay_path = tmp_path / "overlay.json"
    output_root = tmp_path / "recommendations"

    pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-03-27", "2026-03-27"]),
            "ticker": ["AAA", "BBB"],
            "actual": [1.0, 0.0],
            "s1_proba": [0.9, 0.2],
            "c4_oc_asym_5d": [0.3, 0.1],
            "c5_ins_relative_size_5d": [0.0, 0.0],
            "c5_signal_present": [0.0, 0.0],
            "c6_contrarian_intra_5d": [0.5, 0.3],
            "c7_ceiling_count_5d": [0.7, 0.2],
            "c8_vol_zscore_5d": [0.4, 0.3],
            "c9_reversal_1d": [0.6, 0.5],
            "c10_illiq_level_rank": [0.2, 0.8],
            "c11_ret_60d_lag_rank": [0.8, 0.3],
            "c12_gap_absorb_3": [0.6, 0.1],
            "c13_compress_blowoff_2": [0.7, 0.1],
            "c14_clv_volconf_resid_rank": [0.6, 0.2],
        }
    ).to_parquet(matrix_path, index=False)
    pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-03-27", "2026-03-27"]),
            "ticker": ["AAA", "BBB"],
            "can_buy_next_open": [True, False],
        }
    ).to_parquet(tradability_path, index=False)
    overlay_path.write_text(
        json.dumps(
            {
                "summary": {
                    "selector": "full_library",
                    "stale_signal_matrix": False,
                    "next_open_recommendation": {
                        "signal_date": "2026-03-27",
                        "activation_on": True,
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    result = build_live_recommendation(
        profile_name="alpha_full_library_live",
        strategy="full_library",
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        as_of_date="2026-03-27",
        output_root=output_root,
        apply_live_overlay_gate=True,
        overlay_summary_path=overlay_path,
        allow_stale_inputs=False,
        allow_stale_overlay=False,
        allow_overlay_signal_date_mismatch=False,
    )

    assert result.candidate_path.exists()
    saved = pd.read_parquet(result.candidate_path).sort_values("ticker").reset_index(drop=True)
    assert saved["eligible"].tolist() == [True, False]
    assert json.loads(saved.loc[1, "blocked_reasons_json"]) == ["cannot_buy_next_open"]
